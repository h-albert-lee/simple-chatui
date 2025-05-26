import requests
from my_chatbot.core.config import settings

def stream_chat_to_backend(messages: list):
    """
    Sends chat messages to the backend and streams the response.
    Raises an exception if the request fails.
    """
    payload = {"messages": messages}
    # `settings` 객체에서 백엔드 URL을 직접 사용
    response = requests.post(settings.FRONTEND_BACKEND_URL, json=payload, stream=True, timeout=180)
    response.raise_for_status() # HTTP 오류 발생 시 예외 발생
    return response