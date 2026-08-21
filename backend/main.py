"""FastAPI бэкенд для LLM Council."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uuid
import json
import asyncio
import socket

import storage
from config import OPENROUTER_API_KEY, OPENROUTER_API_URL, COUNCIL_ROLES
from council import run_full_council, generate_conversation_title, stage1_collect_responses, stage2_collect_rankings, stage3_synthesize_final, calculate_aggregate_rankings, stage1_collect_roleplay_stream, stage2_collect_rankings_stream, stage3_synthesize_final_stream, get_display_name, MODE_ROLEPLAY

app = FastAPI(title="LLM Council API")


def _get_lan_ip() -> str:
    """Определяет локальный сетевой IP машины (например, 192.168.x.x)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Соединение не отправляет пакеты, только определяет маршрут по умолчанию
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def get_client_ip(http_request: Request) -> Optional[str]:
    """IP клиента; для localhost возвращается реальный сетевой IP машины."""
    host = http_request.client.host if http_request.client else None
    if host in ("127.0.0.1", "::1", "localhost"):
        return _get_lan_ip()
    return host

# Включаем CORS для локальной разработки
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False, # Обязательно False, если allow_origins=["*"] !
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
        "roles": list(COUNCIL_ROLES.keys()),
    }


@app.get("/api/conversations", response_model=List[ConversationMetadata])
async def list_conversations(request: Request):
    """
    Список разговоров текущего компьютера (только метаданные).

    Возвращаются только разговоры, созданные с этого же сетевого IP.
    """
    client_ip = get_client_ip(request)
    return [
        c
        for c in storage.list_conversations()
        if c.get("device_ip") == client_ip
    ]


@app.post("/api/conversations", response_model=Conversation)
async def create_conversation(request: CreateConversationRequest, http_request: Request):
    """Создание нового разговора."""
    conversation_id = str(uuid.uuid4())
    conversation = storage.create_conversation(
        conversation_id,
        device_id=request.device_id,
        device_ip=get_client_ip(http_request)
    )
    return conversation


@app.delete("/api/conversations/{conversation_id}")
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
            get_client_ip(http_request)
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
            get_client_ip(http_request)
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
            if request.mode == MODE_ROLEPLAY:
                from config import COUNCIL_ROLES
                yield f"data: {json.dumps({'type': 'stage1_start', 'roles_total': len(COUNCIL_ROLES)})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'stage1_start'})}\n\n"

            if request.mode == MODE_ROLEPLAY:
                # Потоковая передача для ролевого режима
                stage1_results = []
                async for chunk in stage1_collect_roleplay_stream(
                    request.content,
                    api_key=request.api_key, api_url=request.api_url
                ):
                    if chunk["type"] == "start":
                        yield f"data: {json.dumps({'type': 'stage1_role_start', 'index': chunk['index'], 'role': chunk['role']})}\n\n"
                    elif chunk["type"] == "active":
                        yield f"data: {json.dumps({'type': 'stage1_role_active', 'index': chunk['index'], 'role': chunk['role']})}\n\n"
                    elif chunk["type"] == "chunk":
                        yield f"data: {json.dumps({'type': 'stage1_chunk', 'index': chunk['index'], 'content': chunk['content']})}\n\n"
                    elif chunk["type"] == "done":
                        stage1_results.append({
                            "model": chunk["model"],
                            "role": chunk["role"],
                            "response": chunk["response"],
                        })
            else:
                # Обычный режим без потоковой передачи
                stage1_results = await stage1_collect_responses(
                    request.content, request.mode,
                    api_key=request.api_key, api_url=request.api_url
                )

            yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results})}\n\n"

            # Этап 2: сбор рейтингов
            yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"

            if request.mode == MODE_ROLEPLAY:
                # Потоковая передача для ролевого режима
                stage2_results = []
                async for chunk in stage2_collect_rankings_stream(
                    request.content, stage1_results,
                    api_key=request.api_key, api_url=request.api_url
                ):
                    if chunk["type"] == "start":
                        yield f"data: {json.dumps({'type': 'stage2_role_start', 'index': chunk['index'], 'role': chunk['role']})}\n\n"
                    elif chunk["type"] == "active":
                        yield f"data: {json.dumps({'type': 'stage2_role_active', 'index': chunk['index'], 'role': chunk['role']})}\n\n"
                    elif chunk["type"] == "chunk":
                        yield f"data: {json.dumps({'type': 'stage2_chunk', 'index': chunk['index'], 'content': chunk['content']})}\n\n"
                    elif chunk["type"] == "done":
                        stage2_results.append({
                            "model": chunk["model"],
                            "role": chunk["role"],
                            "ranking": chunk["ranking"],
                            "parsed_ranking": chunk["parsed_ranking"],
                        })
                # label_to_model вычисляется из stage1_results (детерминировано)
                labels = [chr(65 + i) for i in range(len(stage1_results))]
                label_to_model = {
                    f"Response {label}": get_display_name(result)
                    for label, result in zip(labels, stage1_results)
                }
            else:
                stage2_results, label_to_model = await stage2_collect_rankings(
                    request.content, stage1_results, request.mode,
                    api_key=request.api_key, api_url=request.api_url
                )

            aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
            yield f"data: {json.dumps({'type': 'stage2_complete', 'data': stage2_results, 'metadata': {'mode': request.mode, 'label_to_model': label_to_model, 'aggregate_rankings': aggregate_rankings}})}\n\n"

            # Этап 3: синтез итогового ответа
            yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"

            if request.mode == MODE_ROLEPLAY:
                # Потоковая передача для ролевого режима
                stage3_result = None
                async for chunk in stage3_synthesize_final_stream(
                    request.content, stage1_results, stage2_results, request.mode,
                    api_key=request.api_key, api_url=request.api_url
                ):
                    if chunk["type"] == "start":
                        yield f"data: {json.dumps({'type': 'stage3_role_start', 'model': chunk['model']})}\n\n"
                    elif chunk["type"] == "chunk":
                        yield f"data: {json.dumps({'type': 'stage3_chunk', 'content': chunk['content']})}\n\n"
                    elif chunk["type"] == "done":
                        stage3_result = {
                            "model": chunk["model"],
                            "response": chunk["response"],
                        }
            else:
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
