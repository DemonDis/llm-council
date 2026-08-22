"""Режим «Диалог с руководителем»: чат 1-на-1 по профилю из person/staff/leaders.

В отличие от трёхэтапного совета здесь один запрос к одной модели:
системный промпт — полный профиль руководителя, далее вся история беседы
и новое сообщение пользователя.
"""

from typing import Any, Dict, List

import staff
from openrouter import query_model, query_model_stream
from config import DIRECTOR_MODEL

from .prompts import build_dialogue_system_prompt


def build_dialogue_messages(
    profile: Dict[str, Any],
    history: List[Dict[str, str]],
    user_query: str,
) -> List[Dict[str, str]]:
    """
    Сообщения для запроса: система (профиль) + история + вопрос пользователя.

    history — список {'role': 'user'|'assistant', 'content': str} предыдущих
    сообщений разговора без текущего вопроса пользователя.
    """
    messages = [
        {"role": "system", "content": build_dialogue_system_prompt(profile)}
    ]
    for item in history:
        role = item.get("role")
        content = item.get("content")
        if role in ("user", "assistant") and isinstance(content, str) and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_query})
    return messages


async def dialogue_reply(
    profile_id: str,
    user_query: str,
    history: List[Dict[str, str]] = None,
    api_key: str = None,
    api_url: str = None,
) -> Dict[str, Any]:
    """
    Ответ руководителя без потоковой передачи.

    Returns:
        Словарь {'model', 'response'}; при сбое response содержит сообщение об ошибке.
    """
    profile = staff.load_staff_profile(staff.GROUP_LEADERS, profile_id)
    if profile is None:
        raise ValueError(f"Profile not found: {profile_id}")

    messages = build_dialogue_messages(profile, history or [], user_query)
    response = await query_model(
        DIRECTOR_MODEL, messages, timeout=240.0, api_key=api_key, api_url=api_url
    )

    if response is None:
        return {"model": DIRECTOR_MODEL, "response": "Error: unable to generate reply."}

    return {"model": DIRECTOR_MODEL, "response": response.get("content", "")}


async def dialogue_reply_stream(
    profile_id: str,
    user_query: str,
    history: List[Dict[str, str]] = None,
    api_key: str = None,
    api_url: str = None,
):
    """
    Потоковый ответ руководителя.

    Yields:
        - {'type': 'start', 'model': str}
        - {'type': 'chunk', 'content': str}
        - {'type': 'done', 'model': str, 'response': str}
    """
    profile = staff.load_staff_profile(staff.GROUP_LEADERS, profile_id)
    if profile is None:
        raise ValueError(f"Profile not found: {profile_id}")

    messages = build_dialogue_messages(profile, history or [], user_query)

    yield {"type": "start", "model": DIRECTOR_MODEL}

    accumulated = ""
    gen = query_model_stream(
        DIRECTOR_MODEL, messages, timeout=240.0, api_key=api_key, api_url=api_url
    )
    async for chunk in gen:
        if chunk is None:
            break
        content = chunk.get("content", "")
        accumulated += content
        yield {"type": "chunk", "content": content}

    yield {"type": "done", "model": DIRECTOR_MODEL, "response": accumulated}
