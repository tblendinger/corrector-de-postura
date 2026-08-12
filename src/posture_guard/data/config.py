"""Configuration manager for PostureGuard."""

import json
import logging
from pathlib import Path
from typing import Optional

from posture_guard.utils import constants
from posture_guard.data.models import UserConfig

logger = logging.getLogger(__name__)

class ConfigManager:
    """Manages loading and saving of user configuration."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or constants.CONFIG_PATH

    def load(self) -> UserConfig:
        """Load configuration from JSON, merging with current defaults.

        Any fields missing from the saved file get their default value.
        This ensures config schema changes are picked up automatically.
        """
        if not self.config_path.exists():
            return UserConfig()

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Start from defaults, then overlay saved values
            # (handles new fields added after first run)
            default = UserConfig()
            default_dict = default.to_dict()
            default_dict.update({k: v for k, v in data.items() if k in default_dict})
            config = UserConfig.from_dict(default_dict)

            # Clamp processing_interval_ms in case old value was too slow
            if config.processing_interval_ms > constants.MAX_PROCESSING_INTERVAL_MS:
                config.processing_interval_ms = constants.DEFAULT_PROCESSING_INTERVAL_MS
            elif config.processing_interval_ms < constants.MIN_PROCESSING_INTERVAL_MS:
                config.processing_interval_ms = constants.MIN_PROCESSING_INTERVAL_MS

            return config
        except (json.JSONDecodeError, OSError, KeyError) as e:
            logger.warning("Failed to load config, returning defaults: %s", e)
            return UserConfig()

    def save(self, config: UserConfig):
        """Saves configuration to JSON file."""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                f.write(config.to_json())
        except OSError as e:
            logger.error("Failed to save config: %s", e)

    def reset(self) -> UserConfig:
        """Resets configuration to defaults and saves."""
        config = UserConfig()
        self.save(config)
        return config
