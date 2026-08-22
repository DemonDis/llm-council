"""
Пакет council: трёхэтапный процесс LLM Council.

Модули:
- common   — константы режимов и общие помощники (метки Response A/B/C...)
- prompts  — текстовые промпты всех этапов
- ranking  — разбор FINAL RANKING и агрегация рейтингов
- stage1/2/3 — этапы процесса (обычный и потоковый варианты)
- pipeline — полный конвейер run_full_council() и генерация заголовков

Все публичные имена реэкспортируются здесь, поэтому внешние импорты
остаются прежними: `from council import run_full_council, ...`.
"""

from .common import (
    MODE_ENSEMBLE,
    MODE_ROLEPLAY,
    MODE_DIALOGUE,
    MODE_STAFF,
    get_display_name,
    make_labels,
    build_label_to_model,
)
from .prompts import (
    build_ranking_prompt,
    build_chairman_prompt,
    build_title_prompt,
    build_dialogue_system_prompt,
    build_staff_system_prompt,
    combine_system_and_user,
)
from .ranking import parse_ranking_from_text, calculate_aggregate_rankings
from .stage1 import (
    stage1_collect_responses,
    stage1_collect_ensemble,
    stage1_collect_roleplay,
    stage1_collect_roleplay_stream,
)
from .stage2 import stage2_collect_rankings, stage2_collect_rankings_stream
from .stage3 import stage3_synthesize_final, stage3_synthesize_final_stream
from .dialogue import dialogue_reply, dialogue_reply_stream
from .team import team_collect, team_collect_stream, load_team_profiles
from .pipeline import run_full_council, generate_conversation_title

__all__ = [
    "MODE_ENSEMBLE",
    "MODE_ROLEPLAY",
    "MODE_DIALOGUE",
    "MODE_STAFF",
    "get_display_name",
    "make_labels",
    "build_label_to_model",
    "build_ranking_prompt",
    "build_chairman_prompt",
    "build_title_prompt",
    "build_dialogue_system_prompt",
    "build_staff_system_prompt",
    "combine_system_and_user",
    "parse_ranking_from_text",
    "calculate_aggregate_rankings",
    "stage1_collect_responses",
    "stage1_collect_ensemble",
    "stage1_collect_roleplay",
    "stage1_collect_roleplay_stream",
    "stage2_collect_rankings",
    "stage2_collect_rankings_stream",
    "stage3_synthesize_final",
    "stage3_synthesize_final_stream",
    "dialogue_reply",
    "dialogue_reply_stream",
    "team_collect",
    "team_collect_stream",
    "load_team_profiles",
    "run_full_council",
    "generate_conversation_title",
]
