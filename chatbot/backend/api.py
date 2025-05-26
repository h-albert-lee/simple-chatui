import httpx
import logging
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from my_chatbot.core.config import settings
from .models import ChatRequest

# 로거 설정
logging.basicConfig(level=settings.LOG_LEVEL.upper())
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/chat/stream", summary="Chat stream endpoint")
async def stream_chat(chat_request: ChatRequest):
    """
    Receives a chat request from the frontend, forwards it to the vLLM server,
    and streams the response back.
    """
    request_data = chat_request.model_dump()
    logger.info(f"Forwarding request to vLLM for model: {request_data.get('model')}")
    logger.debug(f"Request payload: {request_data}")

    async def stream_generator():
        async with httpx.AsyncClient(timeout=None) as client:
            try:
                async with client.stream("POST", settings.VLLM_API_URL, json=request_data) as response:
                    response.raise_for_status()
                    async for chunk in response.aiter_bytes():
                        yield chunk
            except httpx.HTTPStatusError as e:
                err_msg = f"Error from vLLM server: {e.response.status_code} - {e.response.text}"
                logger.error(err_msg)
                # 클라이언트에 에러를 스트림 형식으로 전달
                yield f"data: {{\"error\": \"{err_msg}\"}}\n\n".encode('utf-8')
            except httpx.RequestError as e:
                err_msg = f"Could not connect to vLLM server at {settings.VLLM_API_URL}: {e}"
                logger.error(err_msg)
                yield f"data: {{\"error\": \"{err_msg}\"}}\n\n".encode('utf-8')

    return StreamingResponse(stream_generator(), media_type="text/event-stream")