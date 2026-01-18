"""Configuration management for UK OSINT Nexus."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Try to load from .env if python-dotenv is available
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


@dataclass
class Config:
    """Application configuration."""

    # API Keys
    companies_house_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("COMPANIES_HOUSE_API_KEY")
    )
    mot_history_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("MOT_HISTORY_API_KEY")
    )

    # Rate limits (requests per second)
    companies_house_rate_limit: float = 2.0
    mot_history_rate_limit: float = 1.0
    bailii_rate_limit: float = 1.0
    contracts_finder_rate_limit: float = 2.0

    # Cache settings
    cache_enabled: bool = True
    cache_ttl_seconds: int = 3600  # 1 hour default
    cache_dir: Path = field(default_factory=lambda: Path.home() / ".cache" / "uk-osint-nexus")

    # Database
    database_path: Path = field(
        default_factory=lambda: Path.home() / ".local" / "share" / "uk-osint-nexus" / "osint.db"
    )

    # Export settings
    export_dir: Path = field(default_factory=lambda: Path.cwd() / "osint_exports")

    def __post_init__(self):
        """Ensure directories exist."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

    def has_companies_house_key(self) -> bool:
        """Check if Companies House API key is configured."""
        return bool(self.companies_house_api_key)

    def has_mot_history_key(self) -> bool:
        """Check if MOT History API key is configured."""
        return bool(self.mot_history_api_key)


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def set_config(config: Config) -> None:
    """Set the global configuration instance."""
    global _config
    _config = config
