"""Tests for configuration loading."""

from pathlib import Path

from gcg.config import (
    Config,
    DEFAULT_BOOK_PATH,
    DEFAULT_BASE_CURRENCY,
    DEFAULT_FX_LOOKBACK_DAYS,
    get_xdg_config_home,
    get_xdg_cache_home,
    get_xdg_state_home,
    load_config,
)


class TestXDGPaths:
    """Tests for XDG path resolution."""

    def test_xdg_config_home_default(self, monkeypatch):
        """Default XDG config home should be ~/.config."""
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        result = get_xdg_config_home()
        assert result == Path.home() / ".config"

    def test_xdg_config_home_custom(self, monkeypatch):
        """Custom XDG_CONFIG_HOME should be respected."""
        monkeypatch.setenv("XDG_CONFIG_HOME", "/custom/config")
        result = get_xdg_config_home()
        assert result == Path("/custom/config")

    def test_xdg_cache_home_default(self, monkeypatch):
        """Default XDG cache home should be ~/.cache."""
        monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
        result = get_xdg_cache_home()
        assert result == Path.home() / ".cache"

    def test_xdg_state_home_default(self, monkeypatch):
        """Default XDG state home should be ~/.local/state."""
        monkeypatch.delenv("XDG_STATE_HOME", raising=False)
        result = get_xdg_state_home()
        assert result == Path.home() / ".local" / "state"


class TestConfigDefaults:
    """Tests for configuration defaults."""

    def test_config_default_values(self):
        """Config should have correct default values."""
        config = Config()
        assert config.base_currency == DEFAULT_BASE_CURRENCY
        assert config.fx_lookback_days == DEFAULT_FX_LOOKBACK_DAYS
        assert config.output_format == "table"
        assert config.show_header is True
        assert config.currency_mode == "auto"
        assert config.cache_enabled is True

    def test_config_derived_paths(self):
        """Config should set derived paths in __post_init__."""
        config = Config()
        assert config.cache_path is not None
        assert config.history_path is not None
        assert "gcg" in str(config.cache_path)
        assert "gcg" in str(config.history_path)


class TestConfigResolution:
    """Tests for book path resolution."""

    def test_resolve_book_path_from_config(self, monkeypatch):
        """Book path set in config should be used."""
        monkeypatch.delenv("GCG_BOOK", raising=False)
        config = Config(book_path=Path("/custom/book.gnucash"))
        result = config.resolve_book_path()
        assert result == Path("/custom/book.gnucash")

    def test_resolve_book_path_from_env(self, monkeypatch):
        """GCG_BOOK env var should override default."""
        monkeypatch.setenv("GCG_BOOK", "/env/book.gnucash")
        config = Config()  # No book_path set
        result = config.resolve_book_path()
        assert result == Path("/env/book.gnucash")

    def test_resolve_book_path_config_overrides_env(self, monkeypatch):
        """Config book_path should override GCG_BOOK env."""
        monkeypatch.setenv("GCG_BOOK", "/env/book.gnucash")
        config = Config(book_path=Path("/config/book.gnucash"))
        result = config.resolve_book_path()
        assert result == Path("/config/book.gnucash")

    def test_resolve_book_path_default(self, monkeypatch):
        """Default book path should be used when nothing set."""
        monkeypatch.delenv("GCG_BOOK", raising=False)
        config = Config()
        result = config.resolve_book_path()
        assert result == DEFAULT_BOOK_PATH.expanduser().resolve()


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_config_cli_overrides(self):
        """CLI arguments should override defaults."""
        config = load_config(
            book_path="/cli/book.gnucash",
            base_currency="USD",
            fx_lookback_days=60,
            output_format="json",
        )
        assert config.book_path == Path("/cli/book.gnucash")
        assert config.base_currency == "USD"
        assert config.fx_lookback_days == 60
        assert config.output_format == "json"

    def test_load_config_partial_overrides(self):
        """Partial CLI args should leave other defaults."""
        config = load_config(output_format="csv")
        assert config.output_format == "csv"
        assert config.base_currency == DEFAULT_BASE_CURRENCY
        assert config.fx_lookback_days == DEFAULT_FX_LOOKBACK_DAYS
