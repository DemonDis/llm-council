"""Режим «Командный штаб»: вопрос выбранным сотрудникам (person/staff/personnel).

Каждый выбранный участник получает вопрос со своим системным промптом
(полный текст профиля) и отвечает параллельно, как роли в ролевом режиме.
События стрима повторяют форму stage1-событий ролевого режима, поэтому
фронтенд переиспует тот же механизм отображения.
"""

from typing import Any, Dict, List

import asyncio

import staff
from openrouter import query_model, query_model_stream
from config import ROLEPLAY_MODEL

from .prompts import build_staff_system_prompt, combine_system_and_user


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


async def team_collect_stream(
    profile_ids: List[str],
    user_query: str,
    api_key: str = None,
    api_url: str = None,
):
    """
    Ответы выбранных участников штаба с потоковой передачей.

    Yields:
        Словари с ключами:
        - {'type': 'start', 'index': int, 'role': str}: начало ответа участника
        - {'type': 'active', 'index': int, 'role': str}: пришёл первый токен
        - {'type': 'chunk', 'index': int, 'content': str}: часть текста
        - {'type': 'done', 'index': int, 'role': str, 'model': str, 'response': str}
    """
    profiles = load_team_profiles(profile_ids)
    if not profiles:
        raise ValueError("No valid staff profiles selected")

    accumulated = [""] * len(profiles)

    async def _stream_member(index: int, profile: Dict[str, Any]):
        # Стаггер для rate-limiting: все участники обращаются к одной модели
        await asyncio.sleep(index * 1.0)

        gen = query_model_stream(ROLEPLAY_MODEL, [
            {"role": "user", "content": combine_system_and_user(
                build_staff_system_prompt(profile), user_query)}
        ], api_key=api_key, api_url=api_url)

        first = True
        async for chunk in gen:
            if chunk is None:
                break
            content = chunk.get("content", "")
            accumulated[index] += content
            if first:
                yield {"type": "active", "index": index, "role": profile["name"]}
                first = False
            yield {"type": "chunk", "index": index, "content": content}

    pending = [_stream_member(i, p) for i, p in enumerate(profiles)]

    for index, profile in enumerate(profiles):
        yield {"type": "start", "index": index, "role": profile["name"]}

    active = list(range(len(pending)))
    while active:
        new_active = []
        for index in active:
            try:
                event = await pending[index].__anext__()
                yield event
                new_active.append(index)
            except StopAsyncIteration:
                yield {
                    "type": "done",
                    "index": index,
                    "role": profiles[index]["name"],
                    "model": ROLEPLAY_MODEL,
                    "response": accumulated[index],
                }
        active = new_active
        if active:
            await asyncio.sleep(0.05)


async def team_collect(
    profile_ids: List[str],
    user_query: str,
    api_key: str = None,
    api_url: str = None,
) -> List[Dict[str, Any]]:
    """
    Ответы участников штаба без потоковой передачи (для синхронного эндпоинта).

    Returns:
        Список {'role', 'model', 'response'} по каждому валидному профилю.
    """
    profiles = load_team_profiles(profile_ids)
    if not profiles:
        raise ValueError("No valid staff profiles selected")

    tasks = [
        query_model(ROLEPLAY_MODEL, [
            {"role": "user", "content": combine_system_and_user(
                build_staff_system_prompt(p), user_query)}
        ], api_key=api_key, api_url=api_url)
        for p in profiles
    ]
    responses = await asyncio.gather(*tasks)

    results = []
    for profile, response in zip(profiles, responses):
        content = (response or {}).get("content") or ""
        results.append({
            "role": profile["name"],
            "model": ROLEPLAY_MODEL,
            "response": content,
        })
    return results
