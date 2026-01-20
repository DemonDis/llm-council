"""Configuration for the LLM Council."""

import os
from dotenv import load_dotenv

load_dotenv()

# OpenRouter API key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_URL = os.getenv("OPENROUTER_API_URL")

# Council members - list of OpenRouter model identifiers
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

# Chairman model - synthesizes final response
CHAIRMAN_MODEL = "gemini-3-pro"

# OpenRouter API endpoint
# OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Data directory for conversation storage
DATA_DIR = "data/conversations"
