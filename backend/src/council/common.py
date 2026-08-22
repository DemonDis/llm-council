"""Общие константы и вспомогательные функции этапов совета."""

from typing import Any, Dict, List

# Режимы работы совета
MODE_ENSEMBLE = "ensemble"    # Битва моделей: один вопрос разным моделям
MODE_ROLEPLAY = "roleplay"    # Ролевой мозговой штурм: роли в одной модели
MODE_DIALOGUE = "dialogue"    # Диалог с руководителем: чат 1-на-1 по его профилю
MODE_STAFF = "staff"          # Командный штаб: вопрос выбранным сотрудникам

# Роли для режима "Ролевой мозговой штурм"
# Загружаются из backend/roles.json (см. load_council_roles в config.py).
# Формат: {"Имя роли": "системный промпт", ...} — можно добавлять/менять роли без правки кода.


def get_display_name(result: Dict[str, Any]) -> str:
    """
    Возвращает имя для отображения результата этапа.

    В ролевом режиме это название роли, в режиме битвы моделей — идентификатор модели.

    Args:
        result: Элемент результата этапа (с ключами 'model' и, возможно, 'role')

    Returns:
        Имя для отображения
    """
    return result.get('role') or result.get('model', 'Unknown')


def make_labels(stage1_results: List[Dict[str, Any]]) -> List[str]:
    """Анонимные метки ответов: A, B, C, ... по числу результатов этапа 1."""
    return [chr(65 + i) for i in range(len(stage1_results))]


def build_label_to_model(stage1_results: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    Сопоставление анонимных меток с именами для отображения
    ("Response A" → роль или модель). Нужно для деанонимизации на клиенте.
    """
    return {
        f"Response {label}": get_display_name(result)
        for label, result in zip(make_labels(stage1_results), stage1_results)
    }
