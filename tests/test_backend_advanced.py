"""Advanced tests for backend API functionality."""

import json
import pytest
import httpx
from httpx import ASGITransport
import respx
from chatbot.backend.models import ChatCompletionRequest, ChatMessage


@pytest.fixture(autouse=True)
def reload_modules(monkeypatch, tmp_path):
    """Reload modules with test configuration."""
    monkeypatch.setenv("UPSTREAM_API_BASE", "http://upstream.test")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path/'backend.db'}")
    monkeypatch.setenv("BACKEND_API_URL", "http://localhost:8000/api/v1/chat/completions")
    
    from importlib import reload
    from chatbot.core import config
    from chatbot.backend import api, main
    
    reload(config)
    reload(api)
    reload(main)
    yield


@pytest.mark.asyncio
async def test_chat_completions_with_custom_model():
    """Test chat completions with custom model parameter."""
    from chatbot.backend.main import app
    
    with respx.mock() as respx_mock:
        route = respx_mock.post("http://upstream.test/v1/chat/completions").mock(
            return_value=httpx.Response(
                status_code=200,
                text="data: {\"choices\": [{\"delta\": {\"content\": \"Custom model response\"}}]}\n\ndata: [DONE]\n\n",
                headers={"Content-Type": "text/event-stream"},
            )
        )
        
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/v1/chat/completions",
                json={
                    "messages": [{"role": "user", "content": "Hi"}],
                    "model": "custom-model-name"
                },
            )
            
            assert response.status_code == 200
            body = "".join([chunk async for chunk in response.aiter_text()])
            assert "Custom model response" in body
            
            # Verify the upstream request used the custom model
            upstream_request = route.calls.last.request
            payload = json.loads(upstream_request.content.decode("utf-8"))
            assert payload["model"] == "custom-model-name"


@pytest.mark.asyncio
async def test_chat_completions_with_temperature():
    """Test chat completions with temperature parameter."""
    from chatbot.backend.main import app
    
    with respx.mock() as respx_mock:
        route = respx_mock.post("http://upstream.test/v1/chat/completions").mock(
            return_value=httpx.Response(
                status_code=200,
                text="data: [DONE]\n\n",
                headers={"Content-Type": "text/event-stream"},
            )
        )
        
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/v1/chat/completions",
                json={
                    "messages": [{"role": "user", "content": "Hi"}],
                    "temperature": 0.7,
                    "top_p": 0.9
                },
            )
            
            assert response.status_code == 200
            
            # Verify parameters were passed through
            upstream_request = route.calls.last.request
            payload = json.loads(upstream_request.content.decode("utf-8"))
            assert payload["temperature"] == 0.7
            assert payload["top_p"] == 0.9


@pytest.mark.asyncio
async def test_chat_completions_empty_messages():
    """Test chat completions with empty messages list."""
    from chatbot.backend.main import app
    
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/chat/completions",
            json={"messages": []},
        )
        
        assert response.status_code == 400
        error_data = response.json()
        assert "at least one message" in error_data["detail"]


@pytest.mark.asyncio
async def test_chat_completions_upstream_error():
    """Test handling of upstream API errors."""
    from chatbot.backend.main import app
    
    with respx.mock() as respx_mock:
        respx_mock.post("http://upstream.test/v1/chat/completions").mock(
            return_value=httpx.Response(
                status_code=500,
                text="Internal Server Error",
            )
        )
        
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/v1/chat/completions",
                json={"messages": [{"role": "user", "content": "Hi"}]},
            )
            
            assert response.status_code == 200  # Still returns 200 for streaming
            body = "".join([chunk async for chunk in response.aiter_text()])
            assert "500" in body  # Error should be in the stream


@pytest.mark.asyncio
async def test_chat_completions_network_error():
    """Test handling of network errors to upstream API."""
    from chatbot.backend.main import app
    
    with respx.mock() as respx_mock:
        respx_mock.post("http://upstream.test/v1/chat/completions").mock(
            side_effect=httpx.ConnectError("Connection failed")
        )
        
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/v1/chat/completions",
                json={"messages": [{"role": "user", "content": "Hi"}]},
            )
            
            assert response.status_code == 200  # Still returns 200 for streaming
            body = "".join([chunk async for chunk in response.aiter_text()])
            assert "Failed to reach upstream API" in body


@pytest.mark.asyncio
async def test_chat_completions_with_api_key():
    """Test that API key is properly forwarded to upstream."""
    from chatbot.backend.main import app
    
    # Mock settings with API key
    import chatbot.core.config as config_module
    original_settings = config_module.settings
    
    class MockSettings:
        UPSTREAM_API_BASE = "http://upstream.test"
        UPSTREAM_API_KEY = "sk-test-key-123"
        DEFAULT_MODEL = "gpt-3.5-turbo"
    
    config_module.settings = MockSettings()
    
    try:
        with respx.mock() as respx_mock:
            route = respx_mock.post("http://upstream.test/v1/chat/completions").mock(
                return_value=httpx.Response(
                    status_code=200,
                    text="data: [DONE]\n\n",
                    headers={"Content-Type": "text/event-stream"},
                )
            )
            
            transport = ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.post(
                    "/api/v1/chat/completions",
                    json={"messages": [{"role": "user", "content": "Hi"}]},
                )
                
                assert response.status_code == 200
                
                # Verify Authorization header was set
                upstream_request = route.calls.last.request
                assert upstream_request.headers["Authorization"] == "Bearer sk-test-key-123"
    
    finally:
        config_module.settings = original_settings


@pytest.mark.asyncio
async def test_health_endpoint():
    """Test the health check endpoint."""
    from chatbot.backend.main import app
    
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health")
        
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_cors_headers():
    """Test that CORS headers are properly set."""
    from chatbot.backend.main import app
    
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Test preflight request
        response = await client.options(
            "/api/v1/chat/completions",
            headers={
                "Origin": "http://localhost:8501",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            }
        )
        
        assert response.status_code == 200
        assert "Access-Control-Allow-Origin" in response.headers


def test_chat_message_model_validation():
    """Test ChatMessage model validation."""
    # Valid message
    msg = ChatMessage(role="user", content="Hello")
    assert msg.role == "user"
    assert msg.content == "Hello"
    
    # Invalid role
    with pytest.raises(ValueError):
        ChatMessage(role="invalid", content="Hello")


def test_chat_completion_request_model():
    """Test ChatCompletionRequest model validation."""
    messages = [ChatMessage(role="user", content="Hello")]
    
    # Valid request
    req = ChatCompletionRequest(messages=messages)
    assert req.messages == messages
    assert req.stream is True  # default
    assert req.model is None  # default
    
    # With optional parameters
    req = ChatCompletionRequest(
        messages=messages,
        model="gpt-4",
        temperature=0.5,
        top_p=0.8,
        stream=False
    )
    assert req.model == "gpt-4"
    assert req.temperature == 0.5
    assert req.top_p == 0.8
    assert req.stream is False
    
    # Invalid temperature
    with pytest.raises(ValueError):
        ChatCompletionRequest(messages=messages, temperature=3.0)
    
    # Invalid top_p
    with pytest.raises(ValueError):
        ChatCompletionRequest(messages=messages, top_p=1.5)