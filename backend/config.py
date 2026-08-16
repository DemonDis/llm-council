"""Конфигурация для LLM Council."""

import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Корень проекта (каталог на уровень выше backend/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

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

# Модель для ролевого режима — отвечает от лица всех ролей совета
ROLEPLAY_MODEL = os.getenv("ROLEPLAY_MODEL")

# Модель для генерации заголовков разговоров (по умолчанию — модель председателя)
TITLE_MODEL = os.getenv("TITLE_MODEL") or CHAIRMAN_MODEL or "gemini-3-pro"

# Каталог для хранения разговоров
DATA_DIR = os.getenv("DATA_DIR", "data/conversations")

# Роли по умолчанию (используются, если roles.json не создан или пуст)
DEFAULT_COUNCIL_ROLES = {
    "Скептик": """Ты — Скептик. Твоя цель: Найти точки отказа и предотвратить проблемы.
Ищи скрытые риски, слабые места, уязвимости и неучтенные факторы. 
Ответь на вопросы: Что может пойти не так? Какой худший сценарий?""",

    "Визионер": """Ты — Визионер. Твоя цель: Найти скрытые возможности и точки роста.
Думай о 10х потенциале, расширении аудитории и новых рынках. 
Ответь на вопрос: Что хорошего может из этого получиться и как это масштабировать?""",

    "Человек со стороны": """Ты — Человек со стороны. Твоя цель: Увидеть привычные вещи под новым углом.
Смотри свежим взглядом без знания индустрии. Задавай "глупые" и наивные вопросы. 
Ответь на вопрос: Почему это делается именно так? Нет ли более простого пути?""",

    "Исполнитель": """Ты — Исполнитель. Твоя цель: Довести задачи до результата.
Превращай планы в действия. Фокус, действие, результат.
Напиши четкий план действий (Задача 1, Задача 2, Задача 3) и расставь приоритеты.""",

    "Проверяющий факты": """Ты — Проверяющий факты. Твоя цель: Отделить факты от предположений.
Сомневайся и проверяй. 
Задай вопросы: На чем основано это утверждение? Какие данные это подтверждают? Что мы принимаем на веру?"""
}


def load_council_roles() -> dict:
    """
    Загружает роли для режима «Ролевой мозговой штурм» из JSON-файла.

    Формат файла: {"Имя роли": "системный промпт (как эта роль думает и говорит)", ...}
    Ключи, начинающиеся с "_" (например, "_comment"), игнорируются и служат для заметок.

    Путь к файлу: roles.json в корне проекта (переопределяется через COUNCIL_ROLES_FILE).
    """
    roles_file = os.getenv("COUNCIL_ROLES_FILE", str(PROJECT_ROOT / "roles.json"))
    path = Path(roles_file)

    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                roles = {k: v for k, v in raw.items() if not k.startswith("_")}
                if roles:
                    return roles
        except Exception as e:
            print(f"Ошибка загрузки ролей из {path}: {e}")

    return DEFAULT_COUNCIL_ROLES


# Роли для режима «Ролевой мозговой штурм» (загружаются из roles.json)
COUNCIL_ROLES = load_council_roles()
