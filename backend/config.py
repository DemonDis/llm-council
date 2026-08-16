"""Конфигурация для LLM Council."""

import os
from dotenv import load_dotenv

load_dotenv()

# Ключ API OpenRouter
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_URL = os.getenv("OPENROUTER_API_URL")

# Члены совета — список идентификаторов моделей OpenRouter через запятую
COUNCIL_MODELS = [
    m.strip()
    for m in os.getenv(
        "COUNCIL_MODELS"
    ).split(",")
    if m.strip()
]

# Модель председателя — синтезирует итоговый ответ
CHAIRMAN_MODEL = os.getenv("CHAIRMAN_MODEL")

# Каталог для хранения разговоров
DATA_DIR = os.getenv("DATA_DIR", "data/conversations")
