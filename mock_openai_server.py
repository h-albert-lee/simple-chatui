#!/usr/bin/env python3
"""Mock OpenAI API server for testing purposes."""

import json
import time
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

app = FastAPI()

class Message(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[Message]
    stream: Optional[bool] = False
    temperature: Optional[float] = 1.0
    max_tokens: Optional[int] = None

def generate_mock_response(messages: List[Message], stream: bool = False):
    """Generate a mock response based on the last user message."""
    last_message = messages[-1].content if messages else "안녕하세요!"
    
    # Simple mock responses
    if "안녕" in last_message:
        response = "안녕하세요! 저는 테스트용 AI 어시스턴트입니다. 무엇을 도와드릴까요?"
    elif "API" in last_message:
        response = "네, API 서버가 정상적으로 작동하고 있습니다! 멀티턴 대화가 가능합니다."
    elif "테스트" in last_message:
        response = "테스트가 성공적으로 진행되고 있습니다. 다른 질문이 있으시면 언제든 말씀해주세요!"
    else:
        response = f"'{last_message}'에 대한 응답입니다. 이것은 테스트용 mock 응답입니다."
    
    if stream:
        return generate_stream_response(response)
    else:
        return {
            "id": "chatcmpl-test123",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "gpt-3.5-turbo",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": len(response.split()),
                "total_tokens": 10 + len(response.split())
            }
        }

def generate_stream_response(content: str):
    """Generate streaming response chunks."""
    words = content.split()
    
    # Start chunk
    yield f"data: {json.dumps({'id': 'chatcmpl-test123', 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': 'gpt-3.5-turbo', 'choices': [{'index': 0, 'delta': {'role': 'assistant'}, 'finish_reason': None}]})}\n\n"
    
    # Content chunks
    for i, word in enumerate(words):
        chunk_content = word + (" " if i < len(words) - 1 else "")
        chunk = {
            "id": "chatcmpl-test123",
            "object": "chat.completion.chunk", 
            "created": int(time.time()),
            "model": "gpt-3.5-turbo",
            "choices": [{
                "index": 0,
                "delta": {"content": chunk_content},
                "finish_reason": None
            }]
        }
        yield f"data: {json.dumps(chunk)}\n\n"
        time.sleep(0.05)  # Simulate streaming delay
    
    # End chunk
    end_chunk = {
        "id": "chatcmpl-test123",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": "gpt-3.5-turbo", 
        "choices": [{
            "index": 0,
            "delta": {},
            "finish_reason": "stop"
        }]
    }
    yield f"data: {json.dumps(end_chunk)}\n\n"
    yield "data: [DONE]\n\n"

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """Mock OpenAI chat completions endpoint."""
    if request.stream:
        return StreamingResponse(
            generate_stream_response(generate_mock_response(request.messages)["choices"][0]["message"]["content"]),
            media_type="text/plain"
        )
    else:
        return generate_mock_response(request.messages, stream=False)

@app.get("/v1/models")
async def list_models():
    """Mock models endpoint."""
    return {
        "object": "list",
        "data": [
            {
                "id": "gpt-3.5-turbo",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "openai"
            }
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)