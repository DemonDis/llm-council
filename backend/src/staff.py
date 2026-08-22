"""Загрузка профилей сотрудников и руководителей из Markdown-файлов.

Профили лежат в backend/person/staff/:
  personnel/*.md — сотрудники (режим «Командный штаб»)
  leaders/*.md   — руководители (режим «Диалог с руководителем»)

Каждый файл — один профиль: YAML-frontmatter между строками '---'
и Markdown-тело. Для списка достаточно имён; полный текст профиля
будет отправляться модели при реализации режимов.
"""

import re
from pathlib import Path

# backend/person/staff/ — на уровень выше каталога src/
STAFF_DIR = Path(__file__).parent.parent / "person" / "staff"

# Группы профилей = подкаталоги STAFF_DIR.
GROUP_PERSONNEL = "personnel"   # сотрудники («Командный штаб»)
GROUP_LEADERS = "leaders"       # руководители («Диалог с руководителем»)
GROUPS = (GROUP_PERSONNEL, GROUP_LEADERS)

_H1_RE = re.compile(
    r"^#\s*Профиль\s+(?:сотрудника|руководителя):\s*(.+?)\s*$",
    re.MULTILINE,
)


def _parse_frontmatter(text: str):
    """
    Разделяет файл на frontmatter и тело.

    Возвращает (метаданные_словарём, тело). Простой разбор «ключ: значение»
    без внешних библиотек; кавычки у значений снимаются.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text

    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text

    meta = {}
    for line in lines[1:end]:
        key, sep, value = line.partition(":")
        value = value.strip().strip('"').strip("'")
        if sep and key.strip() and value:
            meta[key.strip()] = value

    return meta, "\n".join(lines[end + 1:])


def load_staff_profiles(group: str) -> list:
    """
    Профили одной группы: [{'id', 'name', 'status'}, ...] по алфавиту имён файлов.

    Имя берётся из frontmatter ('name' → 'fictional_position'),
    затем из заголовка H1 «Профиль сотрудника: X», иначе — имя файла.
    """
    if group not in GROUPS:
        raise ValueError(f"Unknown staff group: {group}")

    profiles = []
    for path in sorted((STAFF_DIR / group).glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            print(f"Ошибка чтения профиля {path}: {e}")
            continue

        meta, body = _parse_frontmatter(text)
        h1 = _H1_RE.search(body)
        name = (
            meta.get("name")
            or meta.get("fictional_position")
            or (h1.group(1) if h1 else None)
            or path.stem
        )
        profiles.append({
            "id": meta.get("id") or path.stem,
            "name": name.strip(),
            "status": meta.get("profile_status", "active"),
        })

    return profiles


def load_staff_profile(group: str, profile_id: str):
    """
    Полный профиль по id (frontmatter 'id' или имя файла без .md).

    Возвращает {'id', 'name', 'status', 'historical_basis', 'body'} или None,
    если профиль не найден. body — Markdown-тело без frontmatter.
    """
    if group not in GROUPS:
        raise ValueError(f"Unknown staff group: {group}")

    for path in sorted((STAFF_DIR / group).glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            print(f"Ошибка чтения профиля {path}: {e}")
            continue

        meta, body = _parse_frontmatter(text)
        file_id = meta.get("id") or path.stem
        if file_id != profile_id:
            continue

        h1 = _H1_RE.search(body)
        name = (
            meta.get("name")
            or meta.get("fictional_position")
            or (h1.group(1) if h1 else None)
            or path.stem
        )
        return {
            "id": file_id,
            "name": name.strip(),
            "status": meta.get("profile_status", "active"),
            "historical_basis": meta.get("historical_basis"),
            "body": body.strip(),
        }

    return None
