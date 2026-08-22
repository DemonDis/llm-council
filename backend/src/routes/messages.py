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
    MODE_STAFF,
    dialogue_reply,
    team_reply,
    load_team_profiles,
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

    # Штаб: профиль берём из разговора, а не из запроса
    mode = conversation["mode"] if conversation.get("mode") else request.mode
    metadata = {"mode": mode}

    if mode == MODE_STAFF:
        reply = await team_reply(
            conversation.get("profile_ids"),
            request.content,
            history=history,
            api_key=request.api_key,
            api_url=request.api_url
        )
        stage1_results = None
        stage2_results = None
        stage3_result = None
        metadata = None
        content = reply["response"]
        response_payload = {
            "model": reply["model"],
            "content": content,
            "tokens": reply.get("tokens"),
        }
    elif mode == MODE_DIALOGUE:
        reply = await dialogue_reply(
            conversation["profile_id"],
            request.content,
            history=history,
            api_key=request.api_key,
            api_url=request.api_url
        )
        stage1_results = None
        stage2_results = None
        stage3_result = None
        metadata = None
        content = reply["response"]
        response_payload = {
            "model": reply["model"],
            "content": content,
            "tokens": reply.get("tokens"),
        }
    else:
        stage1_results, stage2_results, stage3_result, metadata = await run_full_council(
            request.content,
            mode,
            request.api_key,
            request.api_url
        )
        content = None
        # Суммарный расход токенов по всем вызовам трёх этапов
        usage_total = {"prompt": 0, "completion": 0}
        for entry in (stage1_results or []) + (stage2_results or []):
            if isinstance(entry.get("tokens"), dict):
                usage_total["prompt"] += entry["tokens"].get("prompt") or 0
                usage_total["completion"] += entry["tokens"].get("completion") or 0
        if isinstance((stage3_result or {}).get("tokens"), dict):
            usage_total["prompt"] += stage3_result["tokens"].get("prompt") or 0
            usage_total["completion"] += stage3_result["tokens"].get("completion") or 0
        response_payload = {
            "stage1": stage1_results,
            "stage2": stage2_results,
            "stage3": stage3_result,
            "metadata": metadata,
            "tokens": usage_total,
        }

    storage.add_assistant_message(
        conversation_id,
        stage1_results,
        stage2_results,
        stage3_result,
        metadata=metadata,
        content=content,
        tokens=response_payload.get("tokens")
    )

    return response_payload

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

    conv_mode = conversation["mode"]
    if conv_mode == MODE_DIALOGUE and not conversation.get("profile_id"):
        raise HTTPException(status_code=400, detail="Dialogue conversation has no leader profile")
    if conv_mode == MODE_STAFF and not load_team_profiles(conversation.get("profile_ids") or []):
        raise HTTPException(status_code=400, detail="Staff conversation has no valid member profiles")

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
        profile_ids=conversation.get("profile_ids"),
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