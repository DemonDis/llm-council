"""Хранилище разговоров на основе JSON."""

import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
from config import DATA_DIR


def ensure_data_dir():
    """Проверяет, что каталог данных существует."""
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)


def get_conversation_path(conversation_id: str) -> str:
    """Возвращает путь к файлу разговора."""
    return os.path.join(DATA_DIR, f"{conversation_id}.json")


def create_conversation(
    conversation_id: str,
    device_id: Optional[str] = None,
    device_ip: Optional[str] = None
) -> Dict[str, Any]:
    """
    Создание нового разговора.

    Args:
        conversation_id: Уникальный идентификатор разговора
        device_id: Идентификатор устройства/браузера, создавшего разговор
        device_ip: IP-адрес устройства, создавшего разговор

    Returns:
        Словарь нового разговора
    """
    ensure_data_dir()

    conversation = {
        "id": conversation_id,
        "created_at": datetime.utcnow().isoformat(),
        "title": "New Conversation",
        "device_id": device_id,
        "device_ip": device_ip,
        "messages": []
    }

    # Сохраняем в файл
    path = get_conversation_path(conversation_id)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(conversation, f, indent=2, ensure_ascii=False)

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
    Сохранение разговора в хранилище.

    Args:
        conversation: Словарь разговора для сохранения
    """
    ensure_data_dir()

    path = get_conversation_path(conversation['id'])
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(conversation, f, indent=2, ensure_ascii=False)


def list_conversations() -> List[Dict[str, Any]]:
    """
    Список всех разговоров (только метаданные).

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
                # Возвращаем только метаданные
                conversations.append({
                    "id": data["id"],
                    "created_at": data["created_at"],
                    "title": data.get("title", "New Conversation"),
                    "message_count": len(data["messages"]),
                    "device_id": data.get("device_id"),
                    "device_ip": data.get("device_ip")
                })

    # Сортируем по времени создания, новые сверху
    conversations.sort(key=lambda x: x["created_at"], reverse=True)

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
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    conversation["messages"].append({
        "role": "user",
        "content": content
    })

    save_conversation(conversation)


def add_assistant_message(
    conversation_id: str,
    stage1: List[Dict[str, Any]],
    stage2: List[Dict[str, Any]],
    stage3: Dict[str, Any]
):
    """
    Добавление сообщения ассистента со всеми 3 этапами в разговор.

    Args:
        conversation_id: Идентификатор разговора
        stage1: Список индивидуальных ответов моделей
        stage2: Список рейтингов моделей
        stage3: Итоговый синтезированный ответ
    """
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    conversation["messages"].append({
        "role": "assistant",
        "stage1": stage1,
        "stage2": stage2,
        "stage3": stage3
    })

    save_conversation(conversation)


def update_conversation_title(conversation_id: str, title: str):
    """
    Обновление заголовка разговора.

    Args:
        conversation_id: Идентификатор разговора
        title: Новый заголовок разговора
    """
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise ValueError(f"Conversation {conversation_id} not found")

    conversation["title"] = title
    save_conversation(conversation)
