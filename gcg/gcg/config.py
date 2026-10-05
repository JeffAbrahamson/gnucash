"""
Configuration management for gcg.

Handles loading configuration from multiple sources with precedence:
1. Command-line arguments (highest)
2. Environment variables (GCG_BOOK, etc.)
3. XDG config file (~/.config/gcg/config.toml)
4. Built-in defaults (lowest)
"""

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Use tomli for Python < 3.11, tomllib for 3.11+
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def get_xdg_config_home() -> Path:
    """Return XDG_CONFIG_HOME or default ~/.config"""
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))


def get_xdg_cache_home() -> Path:
    """Return XDG_CACHE_HOME or default ~/.cache"""
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))


def get_xdg_state_home() -> Path:
    """Return XDG_STATE_HOME or default ~/.local/state"""
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))


# Default book path as specified in spec
DEFAULT_BOOK_PATH = (
    Path.home() / "work/finance/gnucash/current/compta-perso.gnucash"
)

# Default base currency
DEFAULT_BASE_CURRENCY = "EUR"

# Default FX lookback window in days
DEFAULT_FX_LOOKBACK_DAYS = 30


@dataclass
class Config:
    """Configuration container for gcg."""

    book_path: Optional[Path] = None
    base_currency: str = DEFAULT_BASE_CURRENCY
    fx_lookback_days: int = DEFAULT_FX_LOOKBACK_DAYS

    # Output settings
    output_format: str = "table"
    show_header: bool = True
    currency_mode: str = "auto"

    # Cache settings
    cache_enabled: bool = True
    cache_path: Optional[Path] = None

    # REPL history
    history_path: Optional[Path] = None

    # Derived paths (set in __post_init__)
    _config_dir: Path = field(default_factory=get_xdg_config_home)

    def __post_init__(self):
        """Set derived paths after initialization."""
        if self.cache_path is None:
            self.cache_path = get_xdg_cache_home() / "gcg" / "cache.sqlite"
        if self.history_path is None:
            self.history_path = get_xdg_state_home() / "gcg" / "history"

    def resolve_book_path(self) -> Path:
        """
        Resolve the book path using precedence rules.

        Returns the first valid path from:
        1. self.book_path (set from CLI --book)
        2. GCG_BOOK environment variable
        3. config file book path
        4. DEFAULT_BOOK_PATH
        """
        if self.book_path is not None:
            return Path(self.book_path).expanduser().resolve()

        env_path = os.environ.get("GCG_BOOK")
        if env_path:
            return Path(env_path).expanduser().resolve()

        return DEFAULT_BOOK_PATH.expanduser().resolve()


def load_config_file() -> dict:
    """
    Load configuration from XDG config file.

    Returns an empty dict if the file doesn't exist.
    """
    config_file = get_xdg_config_home() / "gcg" / "config.toml"
    if not config_file.exists():
        return {}

    try:
        with open(config_file, "rb") as f:
            return tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as e:
        # Log warning but don't fail
        print(
            f"Warning: Could not load config file {config_file}: {e}",
            file=sys.stderr,
        )
        return {}


def load_config(
    book_path: Optional[str] = None,
    base_currency: Optional[str] = None,
    fx_lookback_days: Optional[int] = None,
    output_format: Optional[str] = None,
    show_header: Optional[bool] = None,
    currency_mode: Optional[str] = None,
) -> Config:
    """
    Load configuration with CLI overrides.

    CLI arguments take precedence over environment variables,
    which take precedence over config file values.
    """
    file_config = load_config_file()

    # Start with defaults
    config = Config()

    # Apply config file values
    if "book" in file_config:
        config.book_path = Path(file_config["book"])

    if "currency" in file_config:
        currency_config = file_config["currency"]
        if "base" in currency_config:
            config.base_currency = currency_config["base"]
        if "fx_lookback_days" in currency_config:
            config.fx_lookback_days = currency_config["fx_lookback_days"]
        if "mode" in currency_config:
            config.currency_mode = currency_config["mode"]

    if "output" in file_config:
        output_config = file_config["output"]
        if "format" in output_config:
            config.output_format = output_config["format"]
        if "header" in output_config:
            config.show_header = output_config["header"]

    if "cache" in file_config:
        cache_config = file_config["cache"]
        if "enabled" in cache_config:
            config.cache_enabled = cache_config["enabled"]
        if "path" in cache_config:
            config.cache_path = Path(cache_config["path"])

    # Apply CLI overrides (highest precedence)
    if book_path is not None:
        config.book_path = Path(book_path)
    if base_currency is not None:
        config.base_currency = base_currency
    if fx_lookback_days is not None:
        config.fx_lookback_days = fx_lookback_days
    if output_format is not None:
        config.output_format = output_format
    if show_header is not None:
        config.show_header = show_header
    if currency_mode is not None:
        config.currency_mode = currency_mode

    return config
