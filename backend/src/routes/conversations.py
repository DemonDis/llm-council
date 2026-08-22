"""Роутер: конфигурация API и CRUD разговоров."""
import uuid
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Request
import storage
import staff
from config import OPENROUTER_API_KEY, OPENROUTER_API_URL, COUNCIL_ROLES
from schemas import CreateConversationRequest, Conversation, ConversationMetadata
from utils import get_client_ip

router = APIRouter()

@router.get("/api/config")
async def get_config():
    """Возвращает, какие настройки API заданы в .env (ключ не раскрывается)."""
    return {
        "api_key_configured": bool(OPENROUTER_API_KEY),
        "api_url_configured": bool(OPENROUTER_API_URL),
        "api_url": OPENROUTER_API_URL or "",
        "roles": list(COUNCIL_ROLES.keys()),
    }

@router.get("/api/staff")
async def list_staff(group: str):
    """
    Имена профилей одной группы из backend/person/staff/.

    group='personnel' — сотрудники (страница «Командный штаб»),
    group='leaders' — руководители (страница «Диалог с руководителем»).
    """
    if group not in staff.GROUPS:
        raise HTTPException(status_code=400, detail="Unknown staff group")
    return staff.load_staff_profiles(group)

@router.get("/api/conversations", response_model=List[ConversationMetadata])
async def list_conversations(request: Request, mode: Optional[str] = None):
    """
    Список разговоров текущего компьютера (только метаданные).

    Возвращаются только разговоры, созданные с этого же сетевого IP.
    Параметр mode ('ensemble' | 'roleplay') фильтрует по режиму разговора.
    """
    client_ip = get_client_ip(request)
    return [
        c
        for c in storage.list_conversations(mode=mode)
        if c.get("device_ip") == client_ip
    ]

@router.post("/api/conversations", response_model=Conversation)
async def create_conversation(request: CreateConversationRequest, http_request: Request):
    """Создание нового разговора."""
    conversation_id = str(uuid.uuid4())
    conversation = storage.create_conversation(
        conversation_id,
        device_id=request.device_id,
        device_ip=get_client_ip(http_request),
        mode=request.mode
    )
    return conversation

@router.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, http_request: Request):
    """
    Удаление разговора.

    Разговор можно удалить только с компьютера, с которого он был создан
    (совпадение сетевого IP). Разговоры без информации об устройстве
    (созданные до появления этой функции) удалять разрешено.
    """
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conv_device_ip = conversation.get("device_ip")
    if conv_device_ip and conv_device_ip != get_client_ip(http_request):
        raise HTTPException(status_code=403, detail="Cannot delete another computer's conversation")

    storage.delete_conversation(conversation_id)
    return {"status": "deleted", "id": conversation_id}

@router.get("/api/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str):
    """Получение конкретного разговора со всеми сообщениями."""
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation