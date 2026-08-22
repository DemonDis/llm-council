"""Проверка привязки диалога к профилю и содержимого системного промпта.

Показывает, какой профиль привязан к разговору и какой системный промпт
(полный текст профиля) уходит модели DIRECTOR_MODEL первым сообщением.

Использование из корня проекта:
    python backend/check_dialogue.py <conversation_id>
"""

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "src"))
# Хранилище всегда в backend/data независимо от текущего каталога запуска
os.environ.setdefault("DATA_DIR", str(BACKEND_DIR / "data" / "conversations"))

import staff  # noqa: E402
from storage import get_conversation  # noqa: E402
from council.dialogue import build_dialogue_messages  # noqa: E402


def main():
    if len(sys.argv) != 2:
        print("Использование: python backend/check_dialogue.py <conversation_id>")
        sys.exit(1)

    conv = get_conversation(sys.argv[1])
    if conv is None:
        print(f"Разговор не найден: {sys.argv[1]}")
        sys.exit(1)

    print(f"mode          : {conv.get('mode')}")
    print(f"profile_id    : {conv.get('profile_id')}")
    print(f"profile_name  : {conv.get('profile_name')}")

    if conv.get("mode") != "dialogue" or not conv.get("profile_id"):
        print("\nЭто не диалоговый разговор (или профиль не задан).")
        sys.exit(1)

    profile = staff.load_staff_profile(staff.GROUP_LEADERS, conv["profile_id"])
    if profile is None:
        print(f"\nПРОФИЛЬ НЕ НАЙДЕН: person/staff/{staff.GROUP_LEADERS}/{conv['profile_id']}.md")
        sys.exit(1)

    print(f"файл профиля  : person/staff/{staff.GROUP_LEADERS}/{profile['id']}.md")
    print(f"имя в профиле : {profile['name']}")
    if profile["name"] == conv.get("profile_name"):
        print("привязка      : имя в разговоре СОВПАДАЕТ с профилем")
    else:
        print("привязка      : ВНИМАНИЕ — имя в разговоре отличается от профиля!")

    messages = build_dialogue_messages(profile, [], "")
    prompt = messages[0]["content"]
    print(f"\n=== СИСТЕМНЫЙ ПРОМПТ ({len(prompt)} символов) ===\n")
    print(prompt)
    print(
        "\n---\nИменно эта строка уходит модели как role='system' "
        "в каждом сообщении диалога."
    )


if __name__ == "__main__":
    main()
