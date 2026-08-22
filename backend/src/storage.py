"""Хранилище разговоров на основе JSON."""

import json
import os
import tempfile
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path
from config import DATA_DIR

# Сентинелл «поле не передано» — чтобы отличать от явного None
UNSET = object()

# Блокировки на разговор: атомарные read-modify-write последовательности
_locks_guard = threading.Lock()
_conversation_locks: Dict[str, threading.RLock] = {}

def _get_lock(conversation_id: str) -> threading.RLock:
    """Возвращает блокировку для конкретного разговора (создаёт при необходимости)."""
    with _locks_guard:
        if conversation_id not in _conversation_locks:
            _conversation_locks[conversation_id] = threading.RLock()
        return _conversation_locks[conversation_id]


def ensure_data_dir():
    """Проверяет, что каталог данных существует."""
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)


def get_conversation_path(conversation_id: str) -> str:
    """Возвращает путь к файлу разговора."""
    return os.path.join(DATA_DIR, f"{conversation_id}.json")


def create_conversation(
    conversation_id: str,
    device_id: Optional[str] = None,
    device_ip: Optional[str] = None,
    mode: str = "ensemble"
) -> Dict[str, Any]:
    """
    Создание нового разговора.

    Args:
        conversation_id: Уникальный идентификатор разговора
        device_id: Идентификатор устройства/браузера, создавшего разговор
        device_ip: IP-адрес устройства, создавшего разговор
        mode: Режим совета ('ensemble' или 'roleplay')

    Returns:
        Словарь нового разговора
    """
    ensure_data_dir()

    with _get_lock(conversation_id):
        conversation = {
            "id": conversation_id,
            "created_at": datetime.utcnow().isoformat(),
            "title": "New Conversation",
            "mode": mode,
            "device_id": device_id,
            "device_ip": device_ip,
            "messages": []
        }

        # Сохраняем в файл
        save_conversation(conversation)

    return conversation

def get_conversation(conversation_id: str) -> Optional[Dict[str, Any]]:
    """
    Загрузка разговора из хранилища.

    Args:
        conversation_id: Уникальный идентификатор разговора

    Returns:
        Словарь разговора или None, если не найден
    """
    path = get_conversation_path(conversation_id)

    if not os.path.exists(path):
        return None

    with open(path, 'r') as f:
        return json.load(f)

def save_conversation(conversation: Dict[str, Any]):
    """
    Атомарное сохранение разговора в хранилище.

    Пишет во временный файл и переименовывает через os.replace,
    чтобы сбой/параллельная запись не оставили битый JSON.
    """
    ensure_data_dir()

    path = get_conversation_path(conversation['id'])
    fd, tmp_path = tempfile.mkstemp(dir=DATA_DIR, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(conversation, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise

def infer_conversation_mode(data: Dict[str, Any]) -> str:
    """
    Определяет режим разговора для старых файлов без поля 'mode'.

    В ролевом режиме ответы этапа 1 содержат ключ 'role', в обычном — нет.
    """
    for message in data.get("messages", []):
        for item in message.get("stage1", []) or []:
            if isinstance(item, dict) and item.get("role"):
                return "roleplay"
    return "ensemble"

def list_conversations(mode: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Список всех разговоров (только метаданные).

    Args:
        mode: Если задан ('ensemble' или 'roleplay'), возвращаются только
            разговоры этого режима. Для старых разговоров без поля 'mode'
            режим определяется по содержимому и сохраняется обратно.

    Returns:
        Список словарей с метаданными разговоров
    """
    ensure_data_dir()

    conversations = []
    for filename in os.listdir(DATA_DIR):
        if filename.endswith('.json'):
            path = os.path.join(DATA_DIR, filename)
            with open(path, 'r') as f:
                data = json.load(f)
                # Миграция старых разговоров: определяем и сохраняем режим
                if "mode" not in data:
                    data["mode"] = infer_conversation_mode(data)
                    with _get_lock(data["id"]):
                        save_conversation(data)
                # Возвращаем только метаданные
                conversations.append({
                    "id": data["id"],
                    "created_at": data["created_at"],
                    "title": data.get("title", "New Conversation"),
                    "mode": data["mode"],
                    "message_count": len(data["messages"]),
                    "device_id": data.get("device_id"),
                    "device_ip": data.get("device_ip")
                })

    # Сортируем по времени создания, новые сверху
    conversations.sort(key=lambda x: x["created_at"], reverse=True)

    if mode:
        conversations = [c for c in conversations if c["mode"] == mode]

    return conversations

def delete_conversation(conversation_id: str) -> bool:
    """
    Удаление разговора из хранилища.

    Args:
        conversation_id: Уникальный идентификатор разговора

    Returns:
        True, если разговор был удалён; False, если он не найден
    """
    path = get_conversation_path(conversation_id)

    if not os.path.exists(path):
        return False

    os.remove(path)
    return True

def set_device_info(
    conversation_id: str,
    device_id: str,
    device_ip: Optional[str] = None
):
    """
    Заполняет информацию об устройстве, если она ещё не установлена.

    Позволяет отметить устройство для разговоров, созданных до появления этой функции.

    Args:
        conversation_id: Идентификатор разговора
        device_id: Идентификатор устройства
        device_ip: IP-адрес устройства
    """
    with _get_lock(conversation_id):
        conversation = get_conversation(conversation_id)
        if conversation is None:
            raise ValueError(f"Conversation {conversation_id} not found")

        changed = False
        if conversation.get("device_id") is None and device_id:
            conversation["device_id"] = device_id
            changed = True
        if conversation.get("device_ip") in (None, "127.0.0.1", "::1", "localhost") and device_ip:
            # Заполняем отсутствующий или устаревший loopback-адрес реальным сетевым IP
            conversation["device_ip"] = device_ip
            changed = True
        if changed:
            save_conversation(conversation)

def add_user_message(conversation_id: str, content: str):
    """
    Добавление сообщения пользователя в разговор.

    Args:
        conversation_id: Идентификатор разговора
        content: Содержимое сообщения пользователя
    """
    with _get_lock(conversation_id):
        conversation = get_conversation(conversation_id)
        if conversation is None:
            raise ValueError(f"Conversation {conversation_id} not found")

        conversation["messages"].append({
            "role": "user",
            "content": content
        })

        save_conversation(conversation)

def add_pending_assistant_message(conversation_id: str) -> int:
    """
    Добавление сообщения-заглушки ассистента со статусом 'pending'.

    Вызывается ДО запуска фоновой генерации, чтобы сообщение появилось
    в хранилище сразу и по нему можно было переподключиться к стриму
    даже после перезагрузки страницы.

    Args:
        conversation_id: Идентификатор разговора

    Returns:
        Индекс добавленного сообщения в conversation["messages"]
    """
    with _get_lock(conversation_id):
        conversation = get_conversation(conversation_id)
        if conversation is None:
            raise ValueError(f"Conversation {conversation_id} not found")

        conversation["messages"].append({
            "role": "assistant",
            "status": "pending",
            "stage1": None,
            "stage2": None,
            "stage3": None,
            "metadata": None,
        })

        save_conversation(conversation)
        return len(conversation["messages"]) - 1

# Поля, разрешённые для частичного обновления сообщения ассистента
_UPDATABLE_FIELDS = ("status", "stage1", "stage2", "stage3", "metadata")

def update_assistant_message(conversation_id: str, index: int, fields: Dict[str, Any]):
    """
    Частичное обновление сообщения ассистента (поэтапное сохранение результата).

    Используется фоновым заданием: после завершения каждого этапа результат
    сразу попадает в хранилище и переживает отключение клиента.

    Args:
        conversation_id: Идентификатор разговора
        index: Индекс сообщения ассистента в conversation["messages"]
        fields: Словарь обновляемых полей (status/stage1/stage2/stage3/metadata)
    """
    with _get_lock(conversation_id):
        conversation = get_conversation(conversation_id)
        if conversation is None:
            raise ValueError(f"Conversation {conversation_id} not found")

        messages = conversation["messages"]
        if not 0 <= index < len(messages):
            raise ValueError(f"Message index {index} out of range")

        message = messages[index]
        if message.get("role") != "assistant":
            raise ValueError(f"Message at index {index} is not an assistant message")

        for key, value in fields.items():
            if key in _UPDATABLE_FIELDS:
                message[key] = value

        save_conversation(conversation)

def add_assistant_message(
    conversation_id: str,
    stage1: List[Dict[str, Any]],
    stage2: List[Dict[str, Any]],
    stage3: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None
):
    """
    Добавление сообщения ассистента со всеми 3 этапами в разговор.

    Args:
        conversation_id: Идентификатор разговора
        stage1: Список индивидуальных ответов моделей
        stage2: Список рейтингов моделей
        stage3: Итоговый синтезированный ответ
        metadata: Метаданные (label_to_model, aggregate_rankings, mode)
    """
    with _get_lock(conversation_id):
        conversation = get_conversation(conversation_id)
        if conversation is None:
            raise ValueError(f"Conversation {conversation_id} not found")

        conversation["messages"].append({
            "role": "assistant",
            "status": "complete",
            "stage1": stage1,
            "stage2": stage2,
            "stage3": stage3,
            "metadata": metadata,
        })

        save_conversation(conversation)

def update_conversation_title(conversation_id: str, title: str):
    """
    Обновление заголовка разговора.

    Args:
        conversation_id: Идентификатор разговора
        title: Новый заголовок разговора
    """
    with _get_lock(conversation_id):
        conversation = get_conversation(conversation_id)
        if conversation is None:
            raise ValueError(f"Conversation {conversation_id} not found")

        conversation["title"] = title
        save_conversation(conversation)