"""Конфигурация для LLM Council."""

import os
from dotenv import load_dotenv

load_dotenv()

# Ключ API OpenRouter
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_URL = os.getenv("OPENROUTER_API_URL")

# Члены совета — список идентификаторов моделей OpenRouter
COUNCIL_MODELS = [
    "deepseek-v3.1",
    "gemini-3-pro",
    "gemma-3-27b",
    "glm-4.6",
    "gpt-5.1",
    "gpt-oss-120b",
    "grok-4",
    "qwen3-30b-a3b",
]

# Модель председателя — синтезирует итоговый ответ
CHAIRMAN_MODEL = "gemini-3-pro"

# Конечная точка API OpenRouter
# OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Каталог для хранения разговоров
DATA_DIR = "data/conversations"
