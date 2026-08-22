"""Режим «Командный штаб»: единый ответ на вопрос от лица всего состава.

Все выбранные профили (person/staff/personnel) собираются в один системный
промпт: модель вырабатывает общий ответ штаба, руководствуясь экспертизой,
стилем и приоритетами каждого участника. Отдельные реплики не запрашиваются.
"""

from typing import Any, Dict, List

import staff
from openrouter import query_model, query_model_stream
from config import STAFF_MODEL
import tokens as tokens_mod

from .prompts import build_staff_system_prompt


def load_team_profiles(profile_ids: List[str]) -> List[Dict[str, Any]]:
    """
    Загружает профили участников по id, отбрасывая несуществующие.
    Порядок сохраняется как в списке выбора.
    """
    profiles = []
    for pid in profile_ids or []:
        profile = staff.load_staff_profile(staff.GROUP_PERSONNEL, pid)
        if profile is not None:
            profiles.append(profile)
    return profiles


def build_team_messages(
    profiles: List[Dict[str, Any]],
    history: List[Dict[str, str]],
    user_query: str,
) -> List[Dict[str, str]]:
    """
    Сообщения для запроса: система (все профили) + история + вопрос пользователя.

    history — список {'role': 'user'|'assistant', 'content': str} предыдущих
    сообщений разговора без текущего вопроса пользователя.
    """
    messages = [
        {"role": "system", "content": build_staff_system_prompt(profiles)}
    ]
    for item in history:
        role = item.get("role")
        content = item.get("content")
        if role in ("user", "assistant") and isinstance(content, str) and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_query})
    return messages


async def team_reply(
    profile_ids: List[str],
    user_query: str,
    history: List[Dict[str, str]] = None,
    api_key: str = None,
    api_url: str = None,
) -> Dict[str, Any]:
    """
    Единый ответ штаба без потоковой передачи.

    Returns:
        Словарь {'model', 'response'}; при сбое response содержит сообщение об ошибке.
    """
    profiles = load_team_profiles(profile_ids)
    if not profiles:
        raise ValueError("No valid staff profiles selected")

    messages = build_team_messages(profiles, history or [], user_query)
    names = ", ".join(p["name"] for p in profiles)
    print(
        f"TEAM [sync]: members={len(profiles)} ({names}), "
        f"model={STAFF_MODEL}, system_prompt={len(messages[0]['content'])} chars"
    )
    response = await query_model(
        STAFF_MODEL, messages, timeout=240.0, api_key=api_key, api_url=api_url
    )

    if response is None:
        return {
            "model": STAFF_MODEL,
            "response": "Error: unable to generate reply.",
            "tokens": tokens_mod.usage(),
        }

    return {
        "model": STAFF_MODEL,
        "response": response.get("content", ""),
        "tokens": response.get("usage") or tokens_mod.usage(),
    }


async def team_reply_stream(
    profile_ids: List[str],
    user_query: str,
    history: List[Dict[str, str]] = None,
    api_key: str = None,
    api_url: str = None,
):
    """
    Потоковый единый ответ штаба. Формат событий совпадает с диалоговым,
    поэтому фронтенд рендерит его тем же механизмом.

    Yields:
        - {'type': 'start', 'model': str}
        - {'type': 'chunk', 'content': str}
        - {'type': 'done', 'model': str, 'response': str, 'tokens': {'prompt','completion'}}
    """
    profiles = load_team_profiles(profile_ids)
    if not profiles:
        raise ValueError("No valid staff profiles selected")

    messages = build_team_messages(profiles, history or [], user_query)
    names = ", ".join(p["name"] for p in profiles)
    print(
        f"TEAM [stream]: members={len(profiles)} ({names}), "
        f"model={STAFF_MODEL}, system_prompt={len(messages[0]['content'])} chars"
    )

    yield {"type": "start", "model": STAFF_MODEL}

    accumulated = ""
    usage_stats = {}
    gen = query_model_stream(
        STAFF_MODEL, messages, timeout=240.0, api_key=api_key, api_url=api_url,
        stats=usage_stats,
    )
    async for chunk in gen:
        if chunk is None:
            break
        content = chunk.get("content", "")
        accumulated += content
        yield {"type": "chunk", "content": content}

    yield {
        "type": "done",
        "model": STAFF_MODEL,
        "response": accumulated,
        "tokens": usage_stats or tokens_mod.usage(
            prompt_tokens=tokens_mod.count_messages_tokens(messages),
            completion_tokens=tokens_mod.count_tokens(accumulated),
        ),
    }
