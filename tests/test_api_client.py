import pytest
import requests
from unittest.mock import Mock, patch


def _call_stream(messages, **kwargs):
    from chatbot.frontend.api_client import stream_chat_completion

    return list(stream_chat_completion(messages, **kwargs))


def test_stream_chat_completion_success(monkeypatch, tmp_path):
    """Test successful streaming chat completion."""
    monkeypatch.setenv("UPSTREAM_API_BASE", "http://upstream.test")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test.db")

    from importlib import reload
    from chatbot.core import config

    reload(config)

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.iter_lines.return_value = [
        "data: {\"choices\": [{\"delta\": {\"content\": \"Hello\"}}]}",
        "data: {\"choices\": [{\"delta\": {\"content\": \" world\"}}]}",
        "data: [DONE]",
    ]

    with patch("requests.post") as mock_post:
        mock_post.return_value.__enter__.return_value = mock_response

        messages = [{"role": "user", "content": "Hi"}]
        chunks = _call_stream(messages, model="gpt-3.5-turbo", token="abc")

        assert chunks == ["Hello", " world"]
        mock_post.assert_called_once()


def test_stream_chat_completion_with_invalid_json():
    """Test streaming with invalid JSON data."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.iter_lines.return_value = [
        "data: invalid json",
        "data: [DONE]",
    ]

    with patch("requests.post") as mock_post:
        mock_post.return_value.__enter__.return_value = mock_response

        messages = [{"role": "user", "content": "Hi"}]
        chunks = _call_stream(messages, model="gpt-3.5-turbo", token="abc")

        assert chunks == ["invalid json"]


def test_stream_chat_completion_with_empty_delta():
    """Test streaming with empty delta content."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.iter_lines.return_value = [
        "data: {\"choices\": [{\"delta\": {}}]}",
        "data: {\"choices\": [{\"delta\": {\"content\": \"Hello\"}}]}",
        "data: [DONE]",
    ]

    with patch("requests.post") as mock_post:
        mock_post.return_value.__enter__.return_value = mock_response

        messages = [{"role": "user", "content": "Hi"}]
        chunks = _call_stream(messages, model="gpt-3.5-turbo", token="abc")

        assert chunks == ["Hello"]


def test_stream_chat_completion_http_error():
    """Test streaming with HTTP error."""
    mock_response = Mock()
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = requests.HTTPError("Server Error")

    with patch("requests.post") as mock_post:
        mock_post.return_value.__enter__.return_value = mock_response

        messages = [{"role": "user", "content": "Hi"}]

        with pytest.raises(requests.HTTPError):
            _call_stream(messages, model="gpt-3.5-turbo", token="abc")


def test_stream_chat_completion_request_payload():
    """Test that the request payload is correctly formatted."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.iter_lines.return_value = ["data: [DONE]"]

    with patch("requests.post") as mock_post:
        mock_post.return_value.__enter__.return_value = mock_response

        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "How are you?"},
        ]

        _call_stream(messages, model="gpt-4", token="abc")

        call_args = mock_post.call_args
        assert call_args[1]["json"]["messages"] == messages
        assert call_args[1]["json"]["model"] == "gpt-4"
        assert call_args[1]["json"]["stream"] is True
        assert call_args[1]["headers"]["Authorization"] == "Bearer abc"
        assert call_args[1]["stream"] is True


def test_stream_chat_completion_with_non_data_lines():
    """Test streaming ignores non-data lines."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.iter_lines.return_value = [
        "",
        "event: start",
        "data: {\"choices\": [{\"delta\": {\"content\": \"Hello\"}}]}",
        ": comment line",
        "data: [DONE]",
    ]

    with patch("requests.post") as mock_post:
        mock_post.return_value.__enter__.return_value = mock_response

        messages = [{"role": "user", "content": "Hi"}]
        chunks = _call_stream(messages, model="gpt-3.5-turbo", token="abc")

        assert chunks == ["Hello"]
