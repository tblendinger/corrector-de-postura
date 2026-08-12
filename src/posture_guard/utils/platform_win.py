"""Windows-specific platform utilities.

Provides functions for:
- Auto-start via Windows Registry
- Fullscreen application detection (for gaming mode)
- Application data directory management
"""

from __future__ import annotations

import ctypes
import logging
import sys
from pathlib import Path

from posture_guard.utils.constants import (
    APP_DATA_DIR,
    APP_NAME,
    REGISTRY_APP_NAME,
    REGISTRY_RUN_KEY,
)

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Shell notification states (for fullscreen detection)
# ──────────────────────────────────────────────
QUNS_NOT_PRESENT = 1
QUNS_BUSY = 2
QUNS_RUNNING_D3D_FULL_SCREEN = 3
QUNS_PRESENTATION_MODE = 4
QUNS_ACCEPTS_NOTIFICATIONS = 5
QUNS_QUIET_TIME = 6
QUNS_APP = 7

# Shell window class names to exclude from fullscreen check
_SHELL_CLASSES = frozenset({
    "Progman",
    "WorkerW",
    "Shell_TrayWnd",
    "Shell_SecondaryTrayWnd",
})


def ensure_app_data_dir() -> Path:
    """Create the application data directory if it doesn't exist."""
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return APP_DATA_DIR


def get_autostart_enabled() -> bool:
    """Check if PostureGuard is set to auto-start with Windows."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            REGISTRY_RUN_KEY,
            0,
            winreg.KEY_READ,
        )
        try:
            winreg.QueryValueEx(key, REGISTRY_APP_NAME)
            return True
        except FileNotFoundError:
            return False
        finally:
            winreg.CloseKey(key)
    except Exception as e:
        logger.warning("Could not check autostart registry: %s", e)
        return False


def set_autostart(enabled: bool) -> bool:
    """Enable or disable auto-start with Windows.

    Returns:
        True if the operation succeeded.
    """
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            REGISTRY_RUN_KEY,
            0,
            winreg.KEY_SET_VALUE,
        )
        try:
            if enabled:
                # Use the Python executable path + module
                exe_path = sys.executable
                command = f'"{exe_path}" -m posture_guard'
                winreg.SetValueEx(
                    key,
                    REGISTRY_APP_NAME,
                    0,
                    winreg.REG_SZ,
                    command,
                )
                logger.info("Auto-start enabled: %s", command)
            else:
                try:
                    winreg.DeleteValue(key, REGISTRY_APP_NAME)
                    logger.info("Auto-start disabled")
                except FileNotFoundError:
                    pass  # Already not set
            return True
        finally:
            winreg.CloseKey(key)
    except Exception as e:
        logger.error("Could not set autostart registry: %s", e)
        return False


def is_fullscreen_d3d() -> bool:
    """Check if the system is in a D3D fullscreen state via Shell API.

    Detects exclusive fullscreen DirectX/Vulkan applications.
    """
    try:
        state = ctypes.c_int(0)
        hr = ctypes.windll.shell32.SHQueryUserNotificationState(
            ctypes.byref(state)
        )
        if hr == 0:  # S_OK
            return state.value in (
                QUNS_BUSY,
                QUNS_RUNNING_D3D_FULL_SCREEN,
                QUNS_PRESENTATION_MODE,
            )
    except Exception as e:
        logger.debug("Shell fullscreen check failed: %s", e)
    return False


def is_foreground_fullscreen() -> bool:
    """Check if the foreground window covers the entire screen.

    Detects borderless windowed fullscreen (common in modern games).
    """
    try:
        import win32gui

        user32 = ctypes.windll.user32
        # Ensure DPI-aware measurements
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass

        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return False

        rect = win32gui.GetWindowRect(hwnd)
        screen_w = user32.GetSystemMetrics(0)
        screen_h = user32.GetSystemMetrics(1)

        width = rect[2] - rect[0]
        height = rect[3] - rect[1]

        if rect[0] <= 0 and rect[1] <= 0 and width >= screen_w and height >= screen_h:
            # Filter out desktop/shell false positives
            try:
                class_name = win32gui.GetClassName(hwnd)
                title = win32gui.GetWindowText(hwnd)
                if class_name in _SHELL_CLASSES or not title:
                    return False
            except Exception:
                pass
            return True
    except Exception as e:
        logger.debug("Geometric fullscreen check failed: %s", e)
    return False


def is_fullscreen_app_running() -> bool:
    """Combined fullscreen detection using Shell API + geometric check.

    Returns True if a fullscreen application (like a game) is running.
    Uses two complementary methods:
    1. Shell API — catches exclusive D3D fullscreen
    2. Geometric check — catches borderless windowed fullscreen
    """
    return is_fullscreen_d3d() or is_foreground_fullscreen()
