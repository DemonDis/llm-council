"""Полный конвейер совета и генерация заголовков разговоров."""

from typing import Any, Dict, List, Tuple

from openrouter import query_model
from config import TITLE_MODEL

from .common import MODE_ENSEMBLE
from .prompts import build_title_prompt
from .stage1 import stage1_collect_responses
from .stage2 import stage2_collect_rankings
from .stage3 import stage3_synthesize_final
from .ranking import calculate_aggregate_rankings


async def generate_conversation_title(
    user_query: str,
    api_key: str = None,
    api_url: str = None
) -> str:
    """
    Генерация короткого заголовка разговора на основе первого сообщения пользователя.

    Args:
        user_query: Первое сообщение пользователя
        api_key: Ключ API (переопределяет ключ из .env, если передан)
        api_url: URL API (переопределяет URL из .env, если передан)

    Returns:
        Короткий заголовок (3-5 слов)
    """
    messages = [{"role": "user", "content": build_title_prompt(user_query)}]

    # Используем TITLE_MODEL для генерации заголовка (быстро и дёшево)
    response = await query_model(TITLE_MODEL, messages, timeout=30.0, api_key=api_key, api_url=api_url)

    if response is None:
        # Запасной вариант — стандартный заголовок
        return "New Conversation"

    title = response.get('content', 'New Conversation').strip()

    # Очищаем заголовок — убираем кавычки, ограничиваем длину
    title = title.strip('" \'')

    # Обрезаем, если слишком длинный
    if len(title) > 50:
        title = title[:47] + "..."

    return title


async def run_full_council(
    user_query: str,
    mode: str = MODE_ENSEMBLE,
    api_key: str = None,
    api_url: str = None
) -> Tuple[List, List, Dict, Dict]:
    """
    Запуск полного трёхэтапного процесса совета.

    Args:
        user_query: Вопрос пользователя
        mode: Режим работы совета (ensemble или roleplay)
        api_key: Ключ API (переопределяет ключ из .env, если передан)
        api_url: URL API (переопределяет URL из .env, если передан)

    Returns:
        Кортеж (результаты этапа 1, результаты этапа 2, результат этапа 3, метаданные)
    """
    # Этап 1: сбор индивидуальных ответов
    stage1_results = await stage1_collect_responses(user_query, mode, api_key=api_key, api_url=api_url)

    # Если ни один участник не ответил успешно, возвращаем ошибку
    if not stage1_results:
        return [], [], {
            "model": "error",
            "response": "All participants failed to respond. Please try again."
        }, {}

    # Этап 2: сбор рейтингов
    stage2_results, label_to_model = await stage2_collect_rankings(
        user_query, stage1_results, mode, api_key=api_key, api_url=api_url
    )

    # Расчёт агрегированных рейтингов
    aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)

    # Этап 3: синтез итогового ответа
    stage3_result = await stage3_synthesize_final(
        user_query,
        stage1_results,
        stage2_results,
        mode,
        api_key=api_key,
        api_url=api_url
    )

    # Формируем метаданные
    metadata = {
        "mode": mode,
        "label_to_model": label_to_model,
        "aggregate_rankings": aggregate_rankings
    }

    return stage1_results, stage2_results, stage3_result, metadata
