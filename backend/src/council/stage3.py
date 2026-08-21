"""Этап 3: синтез итогового ответа председателем совета."""

from typing import Any, Dict, List

from openrouter import query_model, query_model_stream
from config import CHAIRMAN_MODEL

from .common import MODE_ENSEMBLE
from .prompts import build_chairman_prompt


async def stage3_synthesize_final(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]],
    mode: str = MODE_ENSEMBLE,
    api_key: str = None,
    api_url: str = None
) -> Dict[str, Any]:
    """
    Этап 3: председатель синтезирует итоговый ответ.

    Args:
        user_query: Исходный запрос пользователя
        stage1_results: Индивидуальные ответы с этапа 1
        stage2_results: Рейтинги с этапа 2
        mode: Режим работы совета (ensemble или roleplay)
        api_key: Ключ API (переопределяет ключ из .env, если передан)
        api_url: URL API (переопределяет URL из .env, если передан)

    Returns:
        Словарь с ключами 'model' и 'response'
    """
    chairman_prompt = build_chairman_prompt(user_query, stage1_results, stage2_results, mode)
    messages = [{"role": "user", "content": chairman_prompt}]

    # Запрашиваем модель председателя с увеличенным таймаутом из-за большого контекста
    response = await query_model(CHAIRMAN_MODEL, messages, timeout=300.0, api_key=api_key, api_url=api_url)

    if response is None:
        # Запасной вариант, если председатель не ответил
        return {
            "model": CHAIRMAN_MODEL,
            "response": "Error: Unable to generate final synthesis."
        }

    return {
        "model": CHAIRMAN_MODEL,
        "response": response.get('content', '')
    }


async def stage3_synthesize_final_stream(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]],
    mode: str = MODE_ENSEMBLE,
    api_key: str = None,
    api_url: str = None
):
    """
    Этап 3 с потоковой передачей ответа председателя.

    Yields:
        Словари с ключами:
        - {'type': 'start', 'model': str}: начало ответа
        - {'type': 'chunk', 'content': str}: часть текста
        - {'type': 'done', 'model': str, 'response': str}: ответ завершён
    """
    chairman_prompt = build_chairman_prompt(user_query, stage1_results, stage2_results, mode)
    messages = [{"role": "user", "content": chairman_prompt}]

    yield {"type": "start", "model": CHAIRMAN_MODEL}

    accumulated = ""
    gen = query_model_stream(CHAIRMAN_MODEL, messages, timeout=300.0, api_key=api_key, api_url=api_url)

    async for chunk in gen:
        if chunk is None:
            break
        content = chunk.get("content", "")
        accumulated += content
        yield {"type": "chunk", "content": content}

    yield {"type": "done", "model": CHAIRMAN_MODEL, "response": accumulated}
