"""Application entry-point for the FastAPI backend."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from chatbot.core.config import settings

from .api import router as api_router

app = FastAPI(
    title="Simple ChatUI Backend",
    version="1.0.0",
    description="Proxy service for forwarding chat requests to an OpenAI-compatible API.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin) for origin in settings.CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
def health_check() -> dict[str, str]:
    """Simple health endpoint."""

    return {"status": "ok"}
