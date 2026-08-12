"""PostureGuard entry point.

Usage:
    python -m posture_guard

Initializes logging, ensures single instance, creates the
QApplication, and launches the PostureGuardApp coordinator.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# Suppress noisy TFLite / MediaPipe C++ internal log spam before any imports.
# TF_CPP_MIN_LOG_LEVEL: 0=DEBUG 1=INFO 2=WARNING 3=ERROR
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
# Suppress MediaPipe GLOG (W0000 lines)
os.environ.setdefault("GLOG_minloglevel", "3")

from posture_guard.utils.constants import APP_NAME, APP_DATA_DIR, LOG_PATH
from posture_guard.utils.platform_win import ensure_app_data_dir


def setup_logging() -> None:
    """Configure logging to both console and file."""
    ensure_app_data_dir()

    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stdout),
    ]

    try:
        file_handler = logging.FileHandler(
            str(LOG_PATH), encoding="utf-8", mode="a"
        )
        handlers.append(file_handler)
    except Exception:
        pass  # File logging is best-effort

    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=date_format,
        handlers=handlers,
    )


def check_single_instance() -> bool:
    """Ensure only one instance of PostureGuard is running.

    Uses a named mutex on Windows. Returns True if this is the
    first instance, False if another instance is already running.
    """
    try:
        import ctypes
        mutex_name = f"Global\\{APP_NAME}_SingleInstance"
        handle = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
        last_error = ctypes.windll.kernel32.GetLastError()
        ERROR_ALREADY_EXISTS = 183
        if last_error == ERROR_ALREADY_EXISTS:
            return False
        return True
    except Exception:
        # If mutex check fails, allow running anyway
        return True


def main() -> None:
    """Main entry point for PostureGuard."""
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("=" * 50)
    logger.info("PostureGuard starting up")
    logger.info("=" * 50)

    # Single instance check
    if not check_single_instance():
        logger.warning("Another instance of PostureGuard is already running. Exiting.")
        sys.exit(0)

    # Import PySide6 after logging is set up
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont

    # Enable High-DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # Set Windows AppUserModelID so Taskbar uses custom logo
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                f"{APP_NAME}.{APP_NAME}.App.1.0"
            )
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setDesktopFileName(APP_NAME)

    from PySide6.QtGui import QIcon
    from posture_guard.utils.constants import LOGO_PATH
    if LOGO_PATH.exists():
        app.setWindowIcon(QIcon(str(LOGO_PATH)))

    # Set default font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # Create the application coordinator
    from posture_guard.app import PostureGuardApp
    posture_app = PostureGuardApp(app)

    # Run
    exit_code = app.exec()

    # Cleanup
    posture_app.cleanup()
    logger.info("PostureGuard terminated with exit code %d", exit_code)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
