"""Pydantic-модели запросов и ответов API."""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class CreateConversationRequest(BaseModel):
    """Запрос на создание нового разговора."""
    device_id: Optional[str] = None
    mode: str = "ensemble"

class SendMessageRequest(BaseModel):
    """Запрос на отправку сообщения в разговоре."""
    content: str
    mode: str = "ensemble"
    # Ключ и URL API, введённые на фронтенде (используются, если не заданы в .env)
    api_key: Optional[str] = None
    api_url: Optional[str] = None
    # Идентификатор устройства, с которого отправлено сообщение
    device_id: Optional[str] = None

class ConversationMetadata(BaseModel):
    """Метаданные разговора для списка."""
    id: str
    created_at: str
    title: str
    mode: str = "ensemble"
    message_count: int
    device_id: Optional[str] = None
    device_ip: Optional[str] = None

class Conversation(BaseModel):
    """Полный разговор со всеми сообщениями."""
    id: str
    created_at: str
    title: str
    messages: List[Dict[str, Any]]