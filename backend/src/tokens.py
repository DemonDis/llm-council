"""Подсчёт токенов для сообщений и ответов.

Использует tiktoken (кодировка o200k_base). Для моделей вне семейства OpenAI
подсчёт приблизительный, но для отображения масштаба этого достаточно.
Библиотека загружается лениво: сбой импорта/загрузки кодировки не ломает
генерацию — включается грубая оценка по символам.
"""

from typing import List, Dict

_encoder = None
_encoder_failed = False

# Примерно столько символов в одном токене для смешанного рус/англ текста
_CHARS_PER_TOKEN_FALLBACK = 3


def _get_encoder():
    global _encoder, _encoder_failed
    if _encoder is not None or _encoder_failed:
        return _encoder
    try:
        import tiktoken
        _encoder = tiktoken.get_encoding("o200k_base")
    except Exception as e:
        print(f"Token counting: tiktoken unavailable ({e}), using char estimate")
        _encoder_failed = True
    return _encoder


def count_tokens(text) -> int:
    """Число токенов в строке; пустая/нестроковая — 0."""
    if not isinstance(text, str) or not text:
        return 0
    encoder = _get_encoder()
    if encoder is not None:
        return len(encoder.encode(text))
    return max(1, len(text) // _CHARS_PER_TOKEN_FALLBACK)


def count_messages_tokens(messages: List[Dict]) -> int:
    """
    Число токенов во всём запросе: содержимое всех сообщений плюс небольшой
    оверхед на роль/форматирование каждого элемента (~4 токена).
    """
    total = 0
    for m in messages or []:
        content = m.get("content") if isinstance(m, dict) else None
        total += count_tokens(content) + 4
    return total


def usage(prompt_tokens: int = 0, completion_tokens: int = 0) -> Dict[str, int]:
    """Словарь расхода токенов для хранения в сообщении."""
    return {
        "prompt": int(prompt_tokens),
        "completion": int(completion_tokens),
    }
