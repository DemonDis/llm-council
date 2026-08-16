"""FastAPI бэкенд для LLM Council."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uuid
import json
import asyncio

from . import storage
from .config import OPENROUTER_API_KEY, OPENROUTER_API_URL
from .council import run_full_council, generate_conversation_title, stage1_collect_responses, stage2_collect_rankings, stage3_synthesize_final, calculate_aggregate_rankings

app = FastAPI(title="LLM Council API")

# Включаем CORS для локальной разработки
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreateConversationRequest(BaseModel):
    """Запрос на создание нового разговора."""
    device_id: Optional[str] = None


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
    message_count: int
    device_id: Optional[str] = None
    device_ip: Optional[str] = None


class Conversation(BaseModel):
    """Полный разговор со всеми сообщениями."""
    id: str
    created_at: str
    title: str
    messages: List[Dict[str, Any]]


@app.get("/")
async def root():
    """Конечная точка проверки состояния."""
    return {"status": "ok", "service": "LLM Council API"}


@app.get("/api/config")
async def get_config():
    """Возвращает, какие настройки API заданы в .env (ключ не раскрывается)."""
    return {
        "api_key_configured": bool(OPENROUTER_API_KEY),
        "api_url_configured": bool(OPENROUTER_API_URL),
        "api_url": OPENROUTER_API_URL or "",
    }


@app.get("/api/conversations", response_model=List[ConversationMetadata])
async def list_conversations():
    """Список всех разговоров (только метаданные)."""
    return storage.list_conversations()


@app.post("/api/conversations", response_model=Conversation)
async def create_conversation(request: CreateConversationRequest, http_request: Request):
    """Создание нового разговора."""
    conversation_id = str(uuid.uuid4())
    conversation = storage.create_conversation(
        conversation_id,
        device_id=request.device_id,
        device_ip=http_request.client.host if http_request.client else None
    )
    return conversation


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, device_id: str):
    """
    Удаление разговора.

    Разговор можно удалить только с устройства, на котором он был создан.
    Разговоры, созданные до появления этой функции (без device_id), удалять разрешено.
    """
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conv_device_id = conversation.get("device_id")
    if conv_device_id and conv_device_id != device_id:
        raise HTTPException(status_code=403, detail="Cannot delete another device's conversation")

    storage.delete_conversation(conversation_id)
    return {"status": "deleted", "id": conversation_id}


@app.get("/api/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str):
    """Получение конкретного разговора со всеми сообщениями."""
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.post("/api/conversations/{conversation_id}/message")
async def send_message(conversation_id: str, request: SendMessageRequest, http_request: Request):
    """
    Отправка сообщения и запуск трёхэтапного процесса совета.
    Возвращает полный ответ со всеми этапами.
    """
    # Проверяем, существует ли разговор
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Проверяем, первое ли это сообщение
    is_first_message = len(conversation["messages"]) == 0

    # Отмечаем устройство для разговоров без информации о нём
    if request.device_id:
        storage.set_device_info(
            conversation_id,
            request.device_id,
            http_request.client.host if http_request.client else None
        )

    # Добавляем сообщение пользователя
    storage.add_user_message(conversation_id, request.content)

    # Если это первое сообщение, генерируем заголовок
    if is_first_message:
        title = await generate_conversation_title(
            request.content,
            api_key=request.api_key,
            api_url=request.api_url
        )
        storage.update_conversation_title(conversation_id, title)

    # Запускаем трёхэтапный процесс совета
    stage1_results, stage2_results, stage3_result, metadata = await run_full_council(
        request.content,
        request.mode,
        request.api_key,
        request.api_url
    )

    # Добавляем сообщение ассистента со всеми этапами
    storage.add_assistant_message(
        conversation_id,
        stage1_results,
        stage2_results,
        stage3_result
    )

    # Возвращаем полный ответ с метаданными
    return {
        "stage1": stage1_results,
        "stage2": stage2_results,
        "stage3": stage3_result,
        "metadata": metadata
    }


@app.post("/api/conversations/{conversation_id}/message/stream")
async def send_message_stream(conversation_id: str, request: SendMessageRequest, http_request: Request):
    """
    Отправка сообщения с потоковой передачей трёхэтапного процесса совета.
    Возвращает Server-Sent Events по мере завершения каждого этапа.
    """
    # Проверяем, существует ли разговор
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Проверяем, первое ли это сообщение
    is_first_message = len(conversation["messages"]) == 0

    # Отмечаем устройство для разговоров без информации о нём
    if request.device_id:
        storage.set_device_info(
            conversation_id,
            request.device_id,
            http_request.client.host if http_request.client else None
        )

    async def event_generator():
        try:
            # Добавляем сообщение пользователя
            storage.add_user_message(conversation_id, request.content)

            # Запускаем генерацию заголовка параллельно (не ожидаем сразу)
            title_task = None
            if is_first_message:
                title_task = asyncio.create_task(
                    generate_conversation_title(
                        request.content,
                        api_key=request.api_key,
                        api_url=request.api_url
                    )
                )

            # Этап 1: сбор ответов
            yield f"data: {json.dumps({'type': 'stage1_start'})}\n\n"
            stage1_results = await stage1_collect_responses(
                request.content, request.mode,
                api_key=request.api_key, api_url=request.api_url
            )
            yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results})}\n\n"

            # Этап 2: сбор рейтингов
            yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"
            stage2_results, label_to_model = await stage2_collect_rankings(
                request.content, stage1_results, request.mode,
                api_key=request.api_key, api_url=request.api_url
            )
            aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
            yield f"data: {json.dumps({'type': 'stage2_complete', 'data': stage2_results, 'metadata': {'mode': request.mode, 'label_to_model': label_to_model, 'aggregate_rankings': aggregate_rankings}})}\n\n"

            # Этап 3: синтез итогового ответа
            yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
            stage3_result = await stage3_synthesize_final(
                request.content, stage1_results, stage2_results, request.mode,
                api_key=request.api_key, api_url=request.api_url
            )
            yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result})}\n\n"

            # Ожидаем завершения генерации заголовка, если она была запущена
            if title_task:
                title = await title_task
                storage.update_conversation_title(conversation_id, title)
                yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"

            # Сохраняем полное сообщение ассистента
            storage.add_assistant_message(
                conversation_id,
                stage1_results,
                stage2_results,
                stage3_result
            )

            # Отправляем событие завершения
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        except Exception as e:
            # Отправляем событие ошибки
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
