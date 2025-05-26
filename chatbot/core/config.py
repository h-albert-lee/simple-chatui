from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    # .env 파일을 읽도록 설정
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    # Backend
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8888
    LOG_LEVEL: str = "INFO"

    # vLLM
    VLLM_API_URL: str

    # Frontend
    FRONTEND_BACKEND_URL: str

    # CORS
    CORS_ORIGINS_STR: str = "http://localhost:8501"

    @property
    def CORS_ORIGINS(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS_STR.split(',')]

# 설정 객체 인스턴스화 (싱글톤처럼 사용)
settings = Settings()