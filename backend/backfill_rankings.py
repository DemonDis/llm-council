"""Одноразовый бэкфилл: пересчитать рейтинг для старых сообщений совета.

Для сообщений ассистента с сохранённым stage2, но без metadata
(созданы до внедрения сохранения рейтинга) добавляет:
  - metadata.mode (из разговора)
  - metadata.label_to_model (по порядку stage1)
  - metadata.aggregate_rankings (пересчёт из parsed_ranking в stage2)

Использование: python backend/backfill_rankings.py   (из корня проекта)
"""
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "src"))
# Хранилище всегда в backend/data независимо от текущего каталога запуска
os.environ.setdefault("DATA_DIR", str(BACKEND_DIR / "data" / "conversations"))

import storage  # noqa: E402
from council.common import build_label_to_model  # noqa: E402
from council.ranking import calculate_aggregate_rankings  # noqa: E402


def backfill():
    fixed = 0
    for meta in storage.list_conversations():
        conv = storage.get_conversation(meta["id"])
        if conv is None:
            continue
        mode = conv.get("mode", "ensemble")
        changed = False

        for msg in conv.get("messages", []):
            if msg.get("role") != "assistant":
                continue
            stage1 = msg.get("stage1")
            stage2 = msg.get("stage2")
            if not stage2 or msg.get("metadata"):
                continue  # не совет, или метаданные уже есть

            label_to_model = (
                build_label_to_model(stage1) if stage1 else {}
            )
            aggregate = calculate_aggregate_rankings(stage2, label_to_model)
            msg["metadata"] = {
                "mode": mode,
                "label_to_model": label_to_model,
                "aggregate_rankings": aggregate,
            }
            changed = True
            fixed += 1

        if changed:
            storage.save_conversation(conv)
            print(f"обновлён: {conv['id']} ({conv.get('title', '')})")

    print(f"\nСообщений с восстановленным рейтингом: {fixed}")


if __name__ == "__main__":
    backfill()
