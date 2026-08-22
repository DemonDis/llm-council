"""Этап 2: взаимное ранжирование анонимизированных ответов."""

import asyncio
from typing import Any, Dict, List, Tuple

from openrouter import query_models_parallel, query_model, query_model_stream
from config import COUNCIL_MODELS, ROLEPLAY_MODEL, COUNCIL_ROLES

from .common import MODE_ENSEMBLE, MODE_ROLEPLAY, build_label_to_model
from .prompts import build_ranking_prompt, combine_system_and_user
from .ranking import parse_ranking_from_text


async def stage2_collect_rankings(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    mode: str = MODE_ENSEMBLE,
    api_key: str = None,
    api_url: str = None
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """
    Этап 2: ранжирование анонимизированных ответов.

    В режиме битвы моделей каждый член совета оценивает ответы остальных.
    В ролевом режиме каждая роль (со своим системным промптом) оценивает ответы остальных ролей.

    Args:
        user_query: Исходный запрос пользователя
        stage1_results: Результаты этапа 1
        mode: Режим работы совета (ensemble или roleplay)
        api_key: Ключ API (переопределяет ключ из .env, если передан)
        api_url: URL API (переопределяет URL из .env, если передан)

    Returns:
        Кортеж (список рейтингов, сопоставление меток и имён для отображения)
    """
    # Создаём сопоставление меток с именами для отображения (роль или модель)
    label_to_model = build_label_to_model(stage1_results)

    # Формируем промпт для ранжирования
    ranking_prompt = build_ranking_prompt(user_query, stage1_results)

    if mode == MODE_ROLEPLAY:
        # Каждая роль со своим системным промптом оценивает ответы остальных
        tasks = []
        for system_prompt in COUNCIL_ROLES.values():
            tasks.append(
                query_model(ROLEPLAY_MODEL, [
                    {"role": "user", "content": combine_system_and_user(system_prompt, ranking_prompt)}
                ], timeout=240.0, api_key=api_key, api_url=api_url)
            )
            await asyncio.sleep(2.0) # Пауза чтобы модель успевала

        responses = []
        for task in tasks:
            response = await task
            responses.append(response)
            await asyncio.sleep(2.0) # Пауза между получением ответов

        # Формируем результаты с привязкой к ролям
        stage2_results = []
        for role_name, response in zip(COUNCIL_ROLES.keys(), responses):
            if response is not None:
                full_text = response.get('content', '')
                entry_tokens = response.get('usage')
                parsed = parse_ranking_from_text(full_text)
                entry = {
                    "model": ROLEPLAY_MODEL,
                    "role": role_name,
                    "ranking": full_text,
                    "parsed_ranking": parsed
                }
                if entry_tokens:
                    entry["tokens"] = entry_tokens
                stage2_results.append(entry)

        return stage2_results, label_to_model

    # Режим битвы моделей: все члены совета оценивают ответы параллельно
    messages = [{"role": "user", "content": ranking_prompt}]

    # Получаем рейтинги от всех моделей совета параллельно
    responses = await query_models_parallel(COUNCIL_MODELS, messages, timeout=240.0, api_key=api_key, api_url=api_url)

    # Формируем результаты
    stage2_results = []
    for model, response in responses.items():
        if response is not None:
            full_text = response.get('content', '')
            parsed = parse_ranking_from_text(full_text)
            entry = {
                "model": model,
                "ranking": full_text,
                "parsed_ranking": parsed
            }
            if response.get('usage'):
                entry["tokens"] = response['usage']
            stage2_results.append(entry)

    return stage2_results, label_to_model


async def stage2_collect_rankings_stream(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    api_key: str = None,
    api_url: str = None
):
    """
    Этап 2 (режим «Ролевой мозговой штурм») с потоковой передачей оценок.

    Каждая роль (со своим системным промптом) оценивает анонимизированные ответы.
    Оценки передаются по мере поступления токенов.

    Yields:
        Словари с ключами:
        - {'type': 'start', 'index': int, 'role': str}: начало оценки роли
        - {'type': 'active', 'index': int, 'role': str}: роль начала генерировать токены
        - {'type': 'chunk', 'index': int, 'content': str}: часть текста оценки
        - {'type': 'done', 'index': int, 'role': str, 'model': str, 'ranking': str, 'parsed_ranking': list}: оценка завершена
    """
    label_to_model = build_label_to_model(stage1_results)

    ranking_prompt = build_ranking_prompt(user_query, stage1_results)
    roles = list(COUNCIL_ROLES.items())
    accumulated = ["" for _ in roles]
    usage_stats_list = [{} for _ in roles]

    async def _stream_role(index, role_name, system_prompt):
        await asyncio.sleep(index * 2.0)

        usage_stats = {}
        gen = query_model_stream(ROLEPLAY_MODEL, [
            {"role": "user", "content": combine_system_and_user(system_prompt, ranking_prompt)}
        ], timeout=240.0, api_key=api_key, api_url=api_url, stats=usage_stats)

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

    pending = [_stream_role(i, name, prompt) for i, (name, prompt) in enumerate(roles)]

    for index, (role_name, _) in enumerate(roles):
        yield {"type": "start", "index": index, "role": role_name}

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
                full_text = accumulated[index]
                parsed = parse_ranking_from_text(full_text)
                done = {
                    "type": "done",
                    "index": index,
                    "role": role_name,
                    "model": ROLEPLAY_MODEL,
                    "ranking": full_text,
                    "parsed_ranking": parsed,
                }
                if usage_stats_list[index]:
                    done["tokens"] = usage_stats_list[index]
                yield done
        active = new_active
        if active:
            await asyncio.sleep(0.1)
