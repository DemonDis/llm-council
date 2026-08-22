"""Логирование запросов и ответов к LLM.

Каждый вызов модели (обычный и стримовый) пишется одной JSONL-строкой
в дневной файл backend/data/logs/llm_calls_YYYY-MM-DD.jsonl:
    {ts, stream, model, duration_s, messages, response, [error]}

API-ключ никогда не попадает в лог. Ошибка записи лога не должна
ломать генерацию — только сообщение в консоль.
"""

import json
import os
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from config import LOGS_DIR, LLM_LOGS_ENABLED

# Записи из разных параллельных задач не должны перемешиваться в файле
_write_lock = threading.Lock()


def log_llm_call(
    model: str,
    messages: List[Dict[str, Any]],
    response: Optional[Dict[str, Any]] = None,
    error: Optional[Exception] = None,
    duration_s: Optional[float] = None,
    stream: bool = False,
) -> None:
    """
    Добавить запись о вызове модели в дневной JSONL-файл логов.

    Args:
        model: Идентификатор модели OpenRouter
        messages: Отправленные сообщения (включая системный промпт)
        response: Ответ модели {'content': ...} либо None при ошибке/обрыве
        error: Исключение, если запрос завершился ошибкой
        duration_s: Длительность запроса в секундах
        stream: Был ли запрос потоковым
    """
    if not LLM_LOGS_ENABLED:
        return  # логирование отключено в .env (LLM_LOGS_ENABLED=false)
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        record = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "stream": stream,
            "model": model,
            "duration_s": round(duration_s, 2) if duration_s is not None else None,
            "messages": messages,
            "response": response,
        }
        if error is not None:
            record["error"] = f"{type(error).__name__}: {error}"

        filename = os.path.join(
            LOGS_DIR, f"llm_calls_{datetime.now():%Y-%m-%d}.jsonl"
        )
        with _write_lock:
            with open(filename, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"Не удалось записать лог LLM-вызова: {e}")
