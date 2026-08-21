"""Менеджер фоновых задач генерации совета.

Генерация отвязана от HTTP-соединения: клиент может отключиться,
перейти в другой чат или на другую страницу — задача продолжит работать
и поэтапно сохранит результат в хранилище. Вернувшись, клиент
переподключается к задаче и получает пропущенные события из буфера.

Требуется один процесс воркера uvicorn (по умолчанию): задачи живут в памяти.
"""

import asyncio
import json
import logging
import time
import storage
from council import (
    generate_conversation_title,
    stage1_collect_responses,
    stage2_collect_rankings,
    stage3_synthesize_final,
    calculate_aggregate_rankings,
    stage1_collect_roleplay_stream,
    stage2_collect_rankings_stream,
    stage3_synthesize_final_stream,
    build_label_to_model,
    MODE_ROLEPLAY,
)

logger = logging.getLogger(__name__)

# Сколько держать завершённую задачу в памяти (для поздних подписчиков)
JOB_TTL_SECONDS = 3600

# Внутренний маркер конца потока для очередей подписчиков (не попадает в буфер)
_SENTINEL = object()

def json_event(event: dict) -> str:
    """Сериализует событие в SSE-строку."""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

class Job:
    """Фоновая задача генерации одного сообщения совета."""

    def __init__(self, key: str, conversation_id: str, message_index: int):
        self.key = key
        self.conversation_id = conversation_id
        self.message_index = message_index
        # running | complete | error
        self.status = "running"
        # Все события задачи — для переподключившихся клиентов
        self.buffer = []
        # Живые подписчики SSE-потока
        self.subscribers = []
        # Блокировка делает подписку/публикацию атомарными относительно друг друга
        self.lock = asyncio.Lock()
        self.task = None
        self.updated_at = time.monotonic()

    def to_dict(self):
        return {
            "key": self.key,
            "conversation_id": self.conversation_id,
            "message_index": self.message_index,
            "status": self.status,
        }

_jobs = {}

def _job_key(conversation_id: str, message_index: int) -> str:
    return f"{conversation_id}:{message_index}"

def _prune_expired():
    """Удаляет давно завершённые задачи из памяти."""
    now = time.monotonic()
    expired = [
        key
        for key, job in _jobs.items()
        if job.status != "running" and now - job.updated_at > JOB_TTL_SECONDS
    ]
    for key in expired:
        del _jobs[key]

def get_job(conversation_id: str, message_index: int) -> Job | None:
    return _jobs.get(_job_key(conversation_id, message_index))

async def subscribe(job: Job):
    """
    Подписка на события задачи.

    Возвращает (снимок_буфера, очередь). Новые события после подписки
    приходят только в очередь. Подписка атомарна относительно публикации,
    поэтому событие не может быть одновременно пропущено и продублировано.
    """
    async with job.lock:
        queue = asyncio.Queue()
        job.subscribers.append(queue)
        snapshot = list(job.buffer)
    return snapshot, queue


async def unsubscribe(job: Job, queue):
    async with job.lock:
        if queue in job.subscribers:
            job.subscribers.remove(queue)


async def _publish(job: Job, event: dict):
    """Пишет событие в буфер и раздаёт живым подписчикам."""
    async with job.lock:
        job.buffer.append(event)
        job.updated_at = time.monotonic()
        subscribers = list(job.subscribers)
    for queue in subscribers:
        queue.put_nowait(event)


def _save_partial(job: Job, fields: dict):
    """
    Поэтапное сохранение результата. Ошибка сохранения не должна убивать
    генерацию — логируем и продолжаем.
    """
    try:
        storage.update_assistant_message(job.conversation_id, job.message_index, fields)
    except Exception:
        logger.exception(
            "Не удалось сохранить этап для %s [%s]",
            job.conversation_id, job.message_index
        )


def start_job(
    conversation_id: str,
    message_index: int,
    content: str,
    mode: str,
    api_key=None,
    api_url=None,
) -> Job:
    """
    Запускает фоновую генерацию ответа совета.

    Пользовательское сообщение и заглушка ассистента ('pending') должны быть
    добавлены в хранилище ДО вызова — здесь только запуск задачи.
    """
    _prune_expired()

    key = _job_key(conversation_id, message_index)
    existing = _jobs.get(key)
    if existing and existing.status == "running":
        raise RuntimeError(f"Generation already running for {key}")

    job = Job(key, conversation_id, message_index)
    _jobs[key] = job
    job.task = asyncio.create_task(
        _run_job(job, content, mode, api_key, api_url)
    )
    return job


async def _run_job(job: Job, content: str, mode: str, api_key, api_url):
    """Сам пайплайн: три этапа + заголовок, с публикацией событий и поэтапным сохранением."""
    conversation_id = job.conversation_id
    index = job.message_index

    try:
        # Заголовок генерируем параллельно, только для первого сообщения:
        # [0] — сообщение пользователя, [1] — заглушка ассистента (index)
        title_task = None
        if index == 1:
            title_task = asyncio.create_task(
                generate_conversation_title(
                    content, api_key=api_key, api_url=api_url
                )
            )

        # Этап 1: сбор ответов
        if mode == MODE_ROLEPLAY:
            from config import COUNCIL_ROLES
            await _publish(job, {"type": "stage1_start", "roles_total": len(COUNCIL_ROLES)})
        else:
            await _publish(job, {"type": "stage1_start"})

        if mode == MODE_ROLEPLAY:
            stage1_results = []
            async for chunk in stage1_collect_roleplay_stream(
                content, api_key=api_key, api_url=api_url
            ):
                if chunk["type"] == "start":
                    await _publish(job, {
                        "type": "stage1_role_start",
                        "index": chunk["index"],
                        "role": chunk["role"],
                    })
                elif chunk["type"] == "active":
                    await _publish(job, {
                        "type": "stage1_role_active",
                        "index": chunk["index"],
                        "role": chunk["role"],
                    })
                elif chunk["type"] == "chunk":
                    await _publish(job, {
                        "type": "stage1_chunk",
                        "index": chunk["index"],
                        "content": chunk["content"],
                    })
                elif chunk["type"] == "done":
                    stage1_results.append({
                        "model": chunk["model"],
                        "role": chunk["role"],
                        "response": chunk["response"],
                    })
        else:
            stage1_results = await stage1_collect_responses(
                content, mode, api_key=api_key, api_url=api_url
            )

        # Этап 1 завершён — сразу сохраняем
        _save_partial(job, {"stage1": stage1_results})
        await _publish(job, {"type": "stage1_complete", "data": stage1_results})

        # Этап 2: сбор рейтингов
        await _publish(job, {"type": "stage2_start"})

        if mode == MODE_ROLEPLAY:
            stage2_results = []
            async for chunk in stage2_collect_rankings_stream(
                content, stage1_results, api_key=api_key, api_url=api_url
            ):
                if chunk["type"] == "start":
                    await _publish(job, {
                        "type": "stage2_role_start",
                        "index": chunk["index"],
                        "role": chunk["role"],
                    })
                elif chunk["type"] == "active":
                    await _publish(job, {
                        "type": "stage2_role_active",
                        "index": chunk["index"],
                        "role": chunk["role"],
                    })
                elif chunk["type"] == "chunk":
                    await _publish(job, {
                        "type": "stage2_chunk",
                        "index": chunk["index"],
                        "content": chunk["content"],
                    })
                elif chunk["type"] == "done":
                    stage2_results.append({
                        "model": chunk["model"],
                        "role": chunk["role"],
                        "ranking": chunk["ranking"],
                        "parsed_ranking": chunk["parsed_ranking"],
                    })
            label_to_model = build_label_to_model(stage1_results)
        else:
            stage2_results, label_to_model = await stage2_collect_rankings(
                content, stage1_results, mode, api_key=api_key, api_url=api_url
            )

        aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
        metadata = {
            "mode": mode,
            "label_to_model": label_to_model,
            "aggregate_rankings": aggregate_rankings,
        }

        # Этап 2 завершён — сразу сохраняем вместе с метаданными
        _save_partial(job, {"stage2": stage2_results, "metadata": metadata})
        await _publish(job, {"type": "stage2_complete", "data": stage2_results, "metadata": metadata})

        # Этап 3: синтез итогового ответа
        await _publish(job, {"type": "stage3_start"})

        if mode == MODE_ROLEPLAY:
            stage3_result = None
            async for chunk in stage3_synthesize_final_stream(
                content, stage1_results, stage2_results, mode,
                api_key=api_key, api_url=api_url
            ):
                if chunk["type"] == "start":
                    await _publish(job, {"type": "stage3_role_start", "model": chunk["model"]})
                elif chunk["type"] == "chunk":
                    await _publish(job, {"type": "stage3_chunk", "content": chunk["content"]})
                elif chunk["type"] == "done":
                    stage3_result = {
                        "model": chunk["model"],
                        "response": chunk["response"],
                    }
        else:
            stage3_result = await stage3_synthesize_final(
                content, stage1_results, stage2_results, mode,
                api_key=api_key, api_url=api_url
            )

        # Этап 3 завершён — сообщение полностью готово
        _save_partial(job, {"stage3": stage3_result, "status": "complete"})
        await _publish(job, {"type": "stage3_complete", "data": stage3_result})

        # Дожидаемся генерации заголовка, если она была запущена
        if title_task:
            try:
                title = await title_task
                storage.update_conversation_title(conversation_id, title)
                await _publish(job, {"type": "title_complete", "data": {"title": title}})
            except Exception:
                logger.exception("Не удалось сгенерировать заголовок для %s", conversation_id)

        await _publish(job, {"type": "complete"})
        job.status = "complete"

    except Exception as e:
        logger.exception("Ошибка генерации для %s [%s]", conversation_id, index)
        # Частичные результаты уже в хранилище; фиксируем ошибку статусом
        _save_partial(job, {"status": "error"})
        await _publish(job, {"type": "error", "message": str(e)})
        job.status = "error"

    finally:
        # Сигнализируем живым подписчикам о конце потока
        async with job.lock:
            job.updated_at = time.monotonic()
            subscribers = list(job.subscribers)
        for queue in subscribers:
            queue.put_nowait(_SENTINEL)


async def stream_job_events(job: Job):
    """
    Асинхронный генератор SSE-строк для подписчика задачи.

    Сначала отдаёт снимок буфера (пропущенные события), затем живые события.
    Завершается после терминального события (complete/error) и опустошения очереди.
    Безопасен при отключении клиента: задача продолжает работу.
    """
    snapshot, queue = await subscribe(job)

    async def _drain():
        while True:
            item = await queue.get()
            if item is _SENTINEL:
                return
            yield item

    try:
        for event in snapshot:
            yield json_event(event)
            if event.get("type") in ("complete", "error"):
                return

        async for event in _drain():
            yield json_event(event)
            if event.get("type") in ("complete", "error"):
                return
    finally:
        await unsubscribe(job, queue)

def synthesize_events_from_message(message: dict, fallback_mode: str = "ensemble"):
    """
    Строит список событий по уже сохранённому сообщению ассистента.

    Используется, когда клиент переподключается к сообщению, для которого
    фоновой задачи уже нет (завершена и вытеснена, сервер перезапущен).
    Клиент мгновенно получает текущее состояние без повторной генерации.
    """
    events = []

    stage1 = message.get("stage1")
    if stage1:
        events.append({"type": "stage1_start", "roles_total": len(stage1)})
        events.append({"type": "stage1_complete", "data": stage1})

    stage2 = message.get("stage2")
    metadata = message.get("metadata")
    if stage2:
        events.append({"type": "stage2_start"})
        events.append({
            "type": "stage2_complete",
            "data": stage2,
            "metadata": metadata or {"mode": fallback_mode},
        })

    stage3 = message.get("stage3")
    if stage3:
        events.append({"type": "stage3_start"})
        events.append({"type": "stage3_complete", "data": stage3})

    status = message.get("status", "complete")
    if status == "pending":
        # Задача потеряна (например, перезапуск сервера) — сообщаем об ошибке
        events.append({
            "type": "error",
            "message": "Генерация была прервана (возможно, сервер перезапускался). Отправьте сообщение ещё раз.",
        })
    elif status == "error":
        # Частичный результат сохранён, но генерация не завершилась
        events.append({"type": "error", "message": "Генерация ранее завершилась ошибкой (показаны частичные результаты)."})
    else:
        events.append({"type": "complete"})

    return events