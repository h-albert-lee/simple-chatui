import uvicorn
from chatbot.core.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "my_chatbot.backend.main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        log_level=settings.LOG_LEVEL.lower(),
        reload=True  # 개발 중에는 코드가 변경될 때마다 서버가 재시작됩니다.
    )