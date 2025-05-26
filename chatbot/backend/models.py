from pydantic import BaseModel
from typing import List, Dict

class ChatRequest(BaseModel):
    messages: List[Dict[str, str]]
    model: str = "default-model" # 필요시 vLLM에서 사용하는 모델 이름으로 변경
    stream: bool = True