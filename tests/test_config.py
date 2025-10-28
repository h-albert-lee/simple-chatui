"""Tests for configuration management."""

import pytest
from pathlib import Path
from pydantic import ValidationError


def test_config_validation_with_valid_settings(monkeypatch, tmp_path):
    """Test configuration validation with valid settings."""
    monkeypatch.setenv("UPSTREAM_API_BASE", "https://api.openai.com")
    monkeypatch.setenv("UPSTREAM_API_KEY", "sk-test123")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    
    from importlib import reload
    from chatbot.core import config
    reload(config)
    
    settings = config.get_settings()
    # AnyHttpUrl adds trailing slash automatically
    assert str(settings.UPSTREAM_API_BASE) == "https://api.openai.com/"
    assert settings.UPSTREAM_API_KEY == "sk-test123"
    assert settings.DEFAULT_MODEL == "gpt-3.5-turbo"


def test_config_validation_with_invalid_database_url(monkeypatch):
    """Test configuration validation with invalid database URL."""
    monkeypatch.setenv("UPSTREAM_API_BASE", "https://api.openai.com")
    monkeypatch.setenv("DATABASE_URL", "postgresql://invalid")
    
    from importlib import reload
    from chatbot.core import config
    
    with pytest.raises(ValidationError) as exc_info:
        reload(config)
        config.get_settings()
    
    assert "Only sqlite:/// URLs are supported" in str(exc_info.value)


def test_config_cors_origins_parsing():
    """Test CORS origins parsing from string."""
    from chatbot.core.config import Settings
    
    # Test the validator directly
    result = Settings.split_cors_origins("http://localhost:8501,https://example.com")
    assert result == ["http://localhost:8501", "https://example.com"]
    
    # Test with spaces
    result = Settings.split_cors_origins("http://localhost:8501, https://example.com , http://test.com")
    assert result == ["http://localhost:8501", "https://example.com", "http://test.com"]
    
    # Test with empty string
    result = Settings.split_cors_origins("")
    assert result == []
    
    # Test with list input (should pass through)
    input_list = ["http://localhost:8501", "https://example.com"]
    result = Settings.split_cors_origins(input_list)
    assert result == input_list


def test_database_path_property(monkeypatch, tmp_path):
    """Test database path property conversion."""
    db_path = tmp_path / "chat.db"
    monkeypatch.setenv("UPSTREAM_API_BASE", "https://api.openai.com")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    
    from importlib import reload
    from chatbot.core import config
    reload(config)
    
    settings = config.get_settings()
    assert settings.database_path == db_path
    assert isinstance(settings.database_path, Path)


def test_missing_required_upstream_api_base(monkeypatch, tmp_path):
    """Test that missing UPSTREAM_API_BASE raises validation error."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    monkeypatch.delenv("UPSTREAM_API_BASE", raising=False)
    
    from importlib import reload
    from chatbot.core import config
    
    with pytest.raises(ValidationError) as exc_info:
        reload(config)
        config.get_settings()
    
    assert "UPSTREAM_API_BASE" in str(exc_info.value)