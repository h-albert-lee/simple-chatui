from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from my_chatbot.core.config import settings
from .api import router as api_router

app = FastAPI(
    title="Chatbot Service Backend",
    version="1.0.0",
    description="A backend service to proxy chat requests to an OpenAI-compatible API.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 라우터를 버전 관리와 함께 포함
app.include_router(api_router, prefix="/api/v1")

@app.get("/health", summary="Health Check")
def health_check():
    """Perform a health check on the service."""
    return {"status": "ok"}