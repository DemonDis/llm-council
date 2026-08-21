"""Разбор и агрегация рейтингов этапа 2."""

import re
from collections import defaultdict
from typing import Any, Dict, List


def parse_ranking_from_text(ranking_text: str) -> List[str]:
    """
    Извлечение секции FINAL RANKING из ответа модели.

    Args:
        ranking_text: Полный текстовый ответ модели

    Returns:
        Список меток ответов в порядке рейтинга
    """
    # Ищем секцию "FINAL RANKING:"
    if "FINAL RANKING:" in ranking_text:
        # Извлекаем всё после "FINAL RANKING:"
        parts = ranking_text.split("FINAL RANKING:")
        if len(parts) >= 2:
            ranking_section = parts[1]
            # Пробуем извлечь нумерованный список (например, "1. Response A")
            # Этот шаблон ищет: номер, точка, необязательный пробел, "Response X"
            numbered_matches = re.findall(r'\d+\.\s*Response [A-Z]', ranking_section)
            if numbered_matches:
                # Извлекаем только часть "Response X"
                return [re.search(r'Response [A-Z]', m).group() for m in numbered_matches]

            # Запасной вариант: извлекаем все "Response X" по порядку
            matches = re.findall(r'Response [A-Z]', ranking_section)
            return matches

    # Запасной вариант: ищем любые "Response X" по порядку во всём тексте
    matches = re.findall(r'Response [A-Z]', ranking_text)
    return matches


def calculate_aggregate_rankings(
    stage2_results: List[Dict[str, Any]],
    label_to_model: Dict[str, str]
) -> List[Dict[str, Any]]:
    """
    Расчёт агрегированных рейтингов по всем моделям.

    Args:
        stage2_results: Рейтинги от каждой модели
        label_to_model: Сопоставление анонимных меток с названиями моделей

    Returns:
        Список словарей с названием модели и средним местом, отсортированный от лучшего к худшему
    """
    # Отслеживаем позиции каждой модели
    model_positions = defaultdict(list)

    for ranking in stage2_results:
        ranking_text = ranking['ranking']

        # Извлекаем рейтинг из структурированного формата
        parsed_ranking = parse_ranking_from_text(ranking_text)

        for position, label in enumerate(parsed_ranking, start=1):
            if label in label_to_model:
                model_name = label_to_model[label]
                model_positions[model_name].append(position)

    # Вычисляем среднюю позицию для каждой модели
    aggregate = []
    for model, positions in model_positions.items():
        if positions:
            avg_rank = sum(positions) / len(positions)
            aggregate.append({
                "model": model,
                "average_rank": round(avg_rank, 2),
                "rankings_count": len(positions)
            })

    # Сортируем по средней позиции (меньше — лучше)
    aggregate.sort(key=lambda x: x['average_rank'])

    return aggregate
