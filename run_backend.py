"""Run the FastAPI backend using Uvicorn."""

import uvicorn

from chatbot.core.config import settings


if __name__ == "__main__":
    uvicorn.run(
        "chatbot.backend.main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        log_level=settings.LOG_LEVEL.lower(),
        reload=False,
    )
