"""Клиент API OpenRouter для запросов к LLM."""

import ssl
import json
import httpx
from typing import List, Dict, Any, Optional
from config import OPENROUTER_API_KEY, OPENROUTER_API_URL

# Создаём SSL-контекст с отключённой верификацией (как в rick/backend/src/app.py)
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.set_ciphers("DEFAULT:@SECLEVEL=2")
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

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

    # Логируем размер запроса для отладки
    payload_str = json.dumps(payload)
    num_chars = len(payload_str)
    # Приблизительный подсчёт токенов (1 токен ~ 4 символа в среднем для английского)
    # Это грубая оценка, но даёт представление о масштабе
    approx_tokens = num_chars / 4
    print(f"DEBUG: Querying model '{model}'. Payload size: ~{num_chars} chars, ~{int(approx_tokens)} tokens.")


    try:
        # Создаём транспорт с кастомным SSL-контекстом (как в rick/backend/src/app.py)
        transport = httpx.AsyncHTTPTransport(verify=_SSL_CTX)
        async with httpx.AsyncClient(timeout=timeout, transport=transport, follow_redirects=True) as client:
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


async def query_model_stream(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0,
    api_key: Optional[str] = None,
    api_url: Optional[str] = None
):
    """
    Запрос к модели через API OpenRouter с потоковой передачей токенов.

    Yields:
        Словари с ключом 'content' (str) по мере поступления токенов.
        При ошибке yields None и завершается.
    """
    import asyncio

    key = api_key or OPENROUTER_API_KEY
    url = api_url or OPENROUTER_API_URL or DEFAULT_OPENROUTER_URL

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
    }

    print(f"DEBUG: Streaming query to model '{model}'.")

    try:
        transport = httpx.AsyncHTTPTransport(verify=_SSL_CTX)
        async with httpx.AsyncClient(timeout=timeout, transport=transport, follow_redirects=True) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        choices = data.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            content = delta.get("content")
                            if content:
                                yield {"content": content}
                    except json.JSONDecodeError:
                        continue
    except Exception as e:
        print(f"Error streaming from model {model}: {e}")
        yield None


async def query_models_parallel(
    models: List[str],
    messages: List[Dict[str, str]],
    timeout: float = 240.0,
    api_key: Optional[str] = None,
    api_url: Optional[str] = None
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Параллельный запрос к нескольким моделям.

    Args:
        models: Список идентификаторов моделей OpenRouter
        messages: Список словарей сообщений, отправляемых каждой модели
        timeout: Тайм-аут запроса в секундах
        api_key: Ключ API (переопределяет ключ из .env, если передан)
        api_url: URL API (переопределяет URL из .env, если передан)

    Returns:
        Словарь, сопоставляющий идентификатор модели со словарём ответа (или None при ошибке)
    """
    import asyncio

    # Создаём задачи для всех моделей
    tasks = []
    for model in models:
        tasks.append(query_model(model, messages, timeout=timeout, api_key=api_key, api_url=api_url))
        # await asyncio.sleep(1.0) # Пауза перед отправкой запроса к следующей модели

    # Ожидаем завершения всех с задержкой между получением ответов
    responses = []
    for task in tasks:
        response = await task
        responses.append(response)
        # await asyncio.sleep(2.0) # Пауза после получения ответа от модели

    # Сопоставляем модели с их ответами
    return {model: response for model, response in zip(models, responses)}
