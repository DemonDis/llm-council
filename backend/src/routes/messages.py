"""Роутер: отправка сообщений и потоковая передача этапов совета.

Генерация выполняется фоновой задачей (jobs.py), а не внутри HTTP-соединения:
отключение клиента не останавливает процесс, результат сохраняется поэтапно.
"""
import asyncio
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
import storage
import jobs
from council import (
    run_full_council,
    generate_conversation_title,
    calculate_aggregate_rankings,
    MODE_DIALOGUE,
    dialogue_reply,
)
from schemas import SendMessageRequest
from utils import get_client_ip

router = APIRouter()


def _dialogue_history(conversation: dict) -> list:
    """
    История беседы для режима 'dialogue': предыдущие сообщения пользователя
    и ответы ассистента (у ассистентов режима совета поля content нет).
    """
    return [
        {"role": m["role"], "content": m["content"]}
        for m in conversation.get("messages", [])
        if m.get("role") in ("user", "assistant")
        and isinstance(m.get("content"), str)
        and m["content"]
    ]

@router.post("/api/conversations/{conversation_id}/message")
async def send_message(conversation_id: str, request: SendMessageRequest, http_request: Request):
    """
    Отправка сообщения и запуск трёхэтапного процесса совета (без стрима).
    Возвращает полный ответ со всеми этапами.
    """
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    is_first_message = len(conversation["messages"]) == 0
    # История для режима 'dialogue' — до добавления нового сообщения пользователя
    history = _dialogue_history(conversation)

    # Отмечаем устройство для разговоров без информации о нём
    if request.device_id:
        storage.set_device_info(
            conversation_id,
            request.device_id,
            get_client_ip(http_request)
        )

    storage.add_user_message(conversation_id, request.content)

    if is_first_message:
        title = await generate_conversation_title(
            request.content,
            api_key=request.api_key,
            api_url=request.api_url
        )
        storage.update_conversation_title(conversation_id, title)

    metadata = {"mode": request.mode}

    if request.mode == MODE_DIALOGUE:
        stage1_results = []
        stage2_results = []
        stage3_result = await dialogue_reply(
            conversation["profile_id"],
            request.content,
            history=history,
            api_key=request.api_key,
            api_url=request.api_url
        )
        stage3_result = {
            "model": stage3_result["model"],
            "response": stage3_result["response"],
        }
        content = stage3_result["response"]
    else:
        stage1_results, stage2_results, stage3_result, metadata = await run_full_council(
            request.content,
            request.mode,
            request.api_key,
            request.api_url
        )
        content = None

    storage.add_assistant_message(
        conversation_id,
        stage1_results,
        stage2_results,
        stage3_result,
        metadata=metadata,
        content=content
    )

    return {
        "stage1": stage1_results,
        "stage2": stage2_results,
        "stage3": stage3_result,
        "metadata": metadata
    }

@router.post("/api/conversations/{conversation_id}/message/stream")
async def send_message_stream(conversation_id: str, request: SendMessageRequest, http_request: Request):
    """
    Отправка сообщения с потоковой передачей этапов совета.

    Пользовательское сообщение и заглушка ассистента сохраняются синхронно,
    затем запускается фоновая задача генерации. SSE-ответ — лишь подписка на её
    события: при отключении клиента генерация продолжается и донашивает
    результаты в хранилище. Вернуться к результату можно через
    GET /api/conversations/{id}/messages/{index}/events.
    """
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Отмечаем устройство для разговоров без информации о нём
    if request.device_id:
        storage.set_device_info(
            conversation_id,
            request.device_id,
            get_client_ip(http_request)
        )

    if conversation["mode"] == MODE_DIALOGUE and not conversation.get("profile_id"):
        raise HTTPException(status_code=400, detail="Dialogue conversation has no leader profile")

    # История беседы для режима 'dialogue' — до добавления нового сообщения
    history = _dialogue_history(conversation)

    # Сохраняем сообщение пользователя и заглушку ассистента синхронно:
    # они видны сразу после любого отключения/перезагрузки страницы
    try:
        storage.add_user_message(conversation_id, request.content)
        message_index = storage.add_pending_assistant_message(conversation_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    job = jobs.start_job(
        conversation_id,
        message_index,
        request.content,
        request.mode,
        api_key=request.api_key,
        api_url=request.api_url,
        profile_id=conversation.get("profile_id"),
        history=history,
    )

    return _sse_response(jobs.stream_job_events(job))

@router.get("/api/conversations/{conversation_id}/messages/{message_index}/events")
async def message_events(conversation_id: str, message_index: int):
    """
    Переподключение к событиям генерации сообщения.

    - Задача ещё жива (идёт или недавно завершилась) → снимок буфера + живые события.
    - Задачи нет → мгновенно воспроизводим состояние из сохранённого сообщения.
    """
    job = jobs.get_job(conversation_id, message_index)

    if job is not None:
        return _sse_response(jobs.stream_job_events(job))

    # Задачи нет в памяти — восстанавливаем события из хранилища
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = conversation["messages"]
    if not 0 <= message_index < len(messages):
        raise HTTPException(status_code=404, detail="Message not found")

    message = messages[message_index]
    if message.get("role") != "assistant":
        raise HTTPException(status_code=400, detail="Not an assistant message")

    async def replay():
        for event in jobs.synthesize_events_from_message(message, conversation.get("mode", "ensemble")):
            yield jobs.json_event(event)

    return _sse_response(replay())

def _sse_response(generator):
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )