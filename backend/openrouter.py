"""Клиент API OpenRouter для запросов к LLM."""

import httpx
from typing import List, Dict, Any, Optional
from .config import OPENROUTER_API_KEY, OPENROUTER_API_URL

# Стандартный URL OpenRouter, используется, если не задан в .env и не передан с фронтенда
DEFAULT_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0,
    api_key: Optional[str] = None,
    api_url: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Запрос к одной модели через API OpenRouter.

    Args:
        model: Идентификатор модели OpenRouter (например, "openai/gpt-4o")
        messages: Список словарей сообщений с ключами 'role' и 'content'
        timeout: Тайм-аут запроса в секундах
        api_key: Ключ API (переопределяет ключ из .env, если передан)
        api_url: URL API (переопределяет URL из .env, если передан)

    Returns:
        Словарь ответа с ключами 'content' и опциональным 'reasoning_details', либо None при ошибке
    """
    key = api_key or OPENROUTER_API_KEY
    url = api_url or OPENROUTER_API_URL or DEFAULT_OPENROUTER_URL

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                url,
                headers=headers,
                json=payload
            )
            response.raise_for_status()

            data = response.json()
            message = data['choices'][0]['message']

            return {
                'content': message.get('content'),
                'reasoning_details': message.get('reasoning_details')
            }

    except Exception as e:
        print(f"Error querying model {model}: {e}")
        return None


async def query_models_parallel(
    models: List[str],
    messages: List[Dict[str, str]],
    api_key: Optional[str] = None,
    api_url: Optional[str] = None
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Параллельный запрос к нескольким моделям.

    Args:
        models: Список идентификаторов моделей OpenRouter
        messages: Список словарей сообщений, отправляемых каждой модели
        api_key: Ключ API (переопределяет ключ из .env, если передан)
        api_url: URL API (переопределяет URL из .env, если передан)

    Returns:
        Словарь, сопоставляющий идентификатор модели со словарём ответа (или None при ошибке)
    """
    import asyncio

    # Создаём задачи для всех моделей
    tasks = [query_model(model, messages, api_key=api_key, api_url=api_url) for model in models]

    # Ожидаем завершения всех
    responses = await asyncio.gather(*tasks)

    # Сопоставляем модели с их ответами
    return {model: response for model, response in zip(models, responses)}
