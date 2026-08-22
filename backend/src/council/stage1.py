"""Этап 1: сбор индивидуальных ответов участников совета."""

import asyncio
from typing import Any, Dict, List

from openrouter import query_models_parallel, query_model, query_model_stream
from config import COUNCIL_MODELS, ROLEPLAY_MODEL, COUNCIL_ROLES

from .common import MODE_ENSEMBLE, MODE_ROLEPLAY
from .prompts import combine_system_and_user


async def stage1_collect_ensemble(
    user_query: str,
    api_key: str = None,
    api_url: str = None
) -> List[Dict[str, Any]]:
    """
    Этап 1 (режим «Битва моделей»): сбор индивидуальных ответов от всех моделей совета.

    Args:
        user_query: Вопрос пользователя
        api_key: Ключ API (переопределяет ключ из .env, если передан)
        api_url: URL API (переопределяет URL из .env, если передан)

    Returns:
        Список словарей с ключами 'model' и 'response'
    """
    messages = [{"role": "user", "content": user_query}]

    # Параллельный запрос ко всем моделям
    responses = await query_models_parallel(COUNCIL_MODELS, messages, timeout=240.0, api_key=api_key, api_url=api_url)

    # Формируем результаты
    stage1_results = []
    for model, response in responses.items():
        if response is not None:  # Включаем только успешные ответы
            entry = {
                "model": model,
                "response": response.get('content', '')
            }
            if response.get('usage'):
                entry["tokens"] = response['usage']
            stage1_results.append(entry)

    return stage1_results


async def stage1_collect_roleplay(
    user_query: str,
    api_key: str = None,
    api_url: str = None
) -> List[Dict[str, Any]]:
    """
    Этап 1 (режим «Ролевой мозговой штурм»): сбор ответов от всех ролей в одной модели.

    Каждая роль получает свой системный промпт и общий вопрос пользователя.

    Args:
        user_query: Вопрос пользователя
        api_key: Ключ API (переопределяет ключ из .env, если передан)
        api_url: URL API (переопределяет URL из .env, если передан)

    Returns:
        Список словарей с ключами 'model', 'role' и 'response'
    """
    # Создаём задачи: для каждой роли объединяем системный промпт и запрос пользователя
    tasks = []
    for system_prompt in COUNCIL_ROLES.values():
        tasks.append(
            query_model(ROLEPLAY_MODEL, [
                {"role": "user", "content": combine_system_and_user(system_prompt, user_query)}
            ], api_key=api_key, api_url=api_url)
        )
        await asyncio.sleep(2.0) # Пауза чтобы модель успевала

    # Параллельное ожидание ответов всех ролей
    responses = []
    for task in tasks:
        response = await task
        responses.append(response)
        await asyncio.sleep(2.0) # Пауза между получением ответов

    # Формируем результаты с привязкой к ролям
    stage1_results = []
    for role_name, response in zip(COUNCIL_ROLES.keys(), responses):
        if response is not None:  # Включаем только успешные ответы
            entry = {
                "model": ROLEPLAY_MODEL,
                "role": role_name,
                "response": response.get('content', '')
            }
            if response.get('usage'):
                entry["tokens"] = response['usage']
            stage1_results.append(entry)

    return stage1_results


async def stage1_collect_roleplay_stream(
    user_query: str,
    api_key: str = None,
    api_url: str = None
):
    """
    Этап 1 (режим «Ролевой мозговой штурм») с потоковой передачей ответов.

    Каждая роль получает свой системный промпт и общий вопрос пользователя.
    Ответы передаются по мере поступления токенов.

    Yields:
        Словари с ключами:
        - {'type': 'start', 'index': int, 'role': str}: начало ответа роли
        - {'type': 'chunk', 'index': int, 'content': str}: часть текста
        - {'type': 'done', 'index': int, 'role': str, 'model': str, 'response': str}: ответ завершён
    """
    accumulated = ["" for _ in COUNCIL_ROLES]
    roles = list(COUNCIL_ROLES.items())
    usage_stats_list = [{} for _ in roles]

    async def _stream_role(index, role_name, system_prompt):
        # Задержка перед запросом к API для rate-limiting (все роли обращаются к одной модели)
        await asyncio.sleep(index * 2.0)

        usage_stats = {}
        gen = query_model_stream(ROLEPLAY_MODEL, [
            {"role": "user", "content": combine_system_and_user(system_prompt, user_query)}
        ], api_key=api_key, api_url=api_url, stats=usage_stats)

        first = True
        async for chunk in gen:
            if chunk is None:
                break
            content = chunk.get("content", "")
            accumulated[index] += content
            if first:
                yield {"type": "active", "index": index, "role": role_name}
                first = False
            yield {"type": "chunk", "index": index, "content": content}
        usage_stats_list[index] = usage_stats

    # Создаём все потоки сразу
    pending = [_stream_role(i, name, prompt) for i, (name, prompt) in enumerate(roles)]

    # Уведомляем о начале всех ролей (прогресс-бар знает общее число)
    for index, (role_name, _) in enumerate(roles):
        yield {"type": "start", "index": index, "role": role_name}

    # Собираем чанки по мере поступления (API-запросы идут с задержкой)
    active = list(range(len(pending)))
    while active:
        new_active = []
        for index in active:
            try:
                event = await pending[index].__anext__()
                yield event
                new_active.append(index)
            except StopAsyncIteration:
                role_name = roles[index][0]
                done = {
                    "type": "done",
                    "index": index,
                    "role": role_name,
                    "model": ROLEPLAY_MODEL,
                    "response": accumulated[index],
                }
                if usage_stats_list[index]:
                    done["tokens"] = usage_stats_list[index]
                yield done
        active = new_active

        if active:
            await asyncio.sleep(0.1)


async def stage1_collect_responses(
    user_query: str,
    mode: str = MODE_ENSEMBLE,
    api_key: str = None,
    api_url: str = None
) -> List[Dict[str, Any]]:
    """
    Этап 1: сбор индивидуальных ответов.

    Args:
        user_query: Вопрос пользователя
        mode: Режим работы совета (ensemble или roleplay)
        api_key: Ключ API (переопределяет ключ из .env, если передан)
        api_url: URL API (переопределяет URL из .env, если передан)

    Returns:
        Список словарей с ответами
    """
    if mode == MODE_ROLEPLAY:
        return await stage1_collect_roleplay(user_query, api_key=api_key, api_url=api_url)
    return await stage1_collect_ensemble(user_query, api_key=api_key, api_url=api_url)
