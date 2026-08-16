"""Клиент API OpenRouter для запросов к LLM."""

import httpx
from typing import List, Dict, Any, Optional
from .config import OPENROUTER_API_KEY, OPENROUTER_API_URL


async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0
) -> Optional[Dict[str, Any]]:
    """
    Запрос к одной модели через API OpenRouter.

    Args:
        model: Идентификатор модели OpenRouter (например, "openai/gpt-4o")
        messages: Список словарей сообщений с ключами 'role' и 'content'
        timeout: Тайм-аут запроса в секундах

    Returns:
        Словарь ответа с ключами 'content' и опциональным 'reasoning_details', либо None при ошибке
    """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                OPENROUTER_API_URL,
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
    messages: List[Dict[str, str]]
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Параллельный запрос к нескольким моделям.

    Args:
        models: Список идентификаторов моделей OpenRouter
        messages: Список словарей сообщений, отправляемых каждой модели

    Returns:
        Словарь, сопоставляющий идентификатор модели со словарём ответа (или None при ошибке)
    """
    import asyncio

    # Создаём задачи для всех моделей
    tasks = [query_model(model, messages) for model in models]

    # Ожидаем завершения всех
    responses = await asyncio.gather(*tasks)

    # Сопоставляем модели с их ответами
    return {model: response for model, response in zip(models, responses)}
