"""Оркестрация трёхэтапного процесса LLM Council."""

from typing import List, Dict, Any, Tuple
import asyncio
from .openrouter import query_models_parallel, query_model
from .config import COUNCIL_MODELS, CHAIRMAN_MODEL, ROLEPLAY_MODEL, TITLE_MODEL

# Режимы работы совета
MODE_ENSEMBLE = "ensemble"    # Битва моделей: один вопрос разным моделям
MODE_ROLEPLAY = "roleplay"    # Ролевой мозговой штурм: роли в одной модели

# Роли для режима "Ролевой мозговой штурм"
COUNCIL_ROLES = {
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


async def stage1_collect_ensemble(user_query: str) -> List[Dict[str, Any]]:
    """
    Этап 1 (режим «Битва моделей»): сбор индивидуальных ответов от всех моделей совета.

    Args:
        user_query: Вопрос пользователя

    Returns:
        Список словарей с ключами 'model' и 'response'
    """
    messages = [{"role": "user", "content": user_query}]

    # Параллельный запрос ко всем моделям
    responses = await query_models_parallel(COUNCIL_MODELS, messages)

    # Формируем результаты
    stage1_results = []
    for model, response in responses.items():
        if response is not None:  # Включаем только успешные ответы
            stage1_results.append({
                "model": model,
                "response": response.get('content', '')
            })

    return stage1_results


async def stage1_collect_roleplay(user_query: str) -> List[Dict[str, Any]]:
    """
    Этап 1 (режим «Ролевой мозговой штурм»): сбор ответов от всех ролей в одной модели.

    Каждая роль получает свой системный промпт и общий вопрос пользователя.

    Args:
        user_query: Вопрос пользователя

    Returns:
        Список словарей с ключами 'model', 'role' и 'response'
    """
    # Создаём задачи: для каждой роли свой системный промпт
    tasks = [
        query_model(ROLEPLAY_MODEL, [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query}
        ])
        for system_prompt in COUNCIL_ROLES.values()
    ]

    # Параллельное ожидание ответов всех ролей
    responses = await asyncio.gather(*tasks)

    # Формируем результаты с привязкой к ролям
    stage1_results = []
    for role_name, response in zip(COUNCIL_ROLES.keys(), responses):
        if response is not None:  # Включаем только успешные ответы
            stage1_results.append({
                "model": ROLEPLAY_MODEL,
                "role": role_name,
                "response": response.get('content', '')
            })

    return stage1_results


async def stage1_collect_responses(user_query: str, mode: str = MODE_ENSEMBLE) -> List[Dict[str, Any]]:
    """
    Этап 1: сбор индивидуальных ответов.

    Args:
        user_query: Вопрос пользователя
        mode: Режим работы совета (ensemble или roleplay)

    Returns:
        Список словарей с ответами
    """
    if mode == MODE_ROLEPLAY:
        return await stage1_collect_roleplay(user_query)
    return await stage1_collect_ensemble(user_query)


async def stage2_collect_rankings(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    mode: str = MODE_ENSEMBLE
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """
    Этап 2: ранжирование анонимизированных ответов.

    В режиме битвы моделей каждый член совета оценивает ответы остальных.
    В ролевом режиме каждая роль (со своим системным промптом) оценивает ответы остальных ролей.

    Args:
        user_query: Исходный запрос пользователя
        stage1_results: Результаты этапа 1
        mode: Режим работы совета (ensemble или roleplay)

    Returns:
        Кортеж (список рейтингов, сопоставление меток и имён для отображения)
    """
    # Создаём анонимные метки для ответов (Response A, Response B и т.д.)
    labels = [chr(65 + i) for i in range(len(stage1_results))]  # A, B, C, ...

    # Создаём сопоставление меток с именами для отображения (роль или модель)
    label_to_model = {
        f"Response {label}": get_display_name(result)
        for label, result in zip(labels, stage1_results)
    }

    # Формируем промпт для ранжирования
    responses_text = "\n\n".join([
        f"Response {label}:\n{result['response']}"
        for label, result in zip(labels, stage1_results)
    ])

    ranking_prompt = f"""Вы оцениваете различные ответы на следующий вопрос:

Вопрос: {user_query}

Вот ответы от разных участников (анонимизированы):

{responses_text}

Ваша задача:
1. Сначала оцените каждый ответ по отдельности. Для каждого ответа объясните, что в нём хорошо, а что плохо.
2. Затем, в самом конце вашего ответа, предоставьте итоговый рейтинг.

ВАЖНО: Ваш итоговый рейтинг ДОЛЖЕН быть отформатирован ТОЧНО следующим образом:
- Начните со строки "FINAL RANKING:" (заглавными буквами, с двоеточием)
- Затем перечислите ответы от лучшего к худшему в виде нумерованного списка
- Каждая строка должна быть: номер, точка, пробел, затем ТОЛЬКО метка ответа (например, "1. Response A")
- Не добавляйте никакого другого текста или пояснений в раздел рейтинга

Пример правильного формата для ВСЕГО вашего ответа:

Response A предоставляет хорошие детали по X, но упускает Y...
Response B точен, но не хватает глубины по Z...
Response C даёт самый полный ответ...

FINAL RANKING:
1. Response C
2. Response A
3. Response B

Теперь предоставьте вашу оценку и рейтинг:"""

    if mode == MODE_ROLEPLAY:
        # Каждая роль со своим системным промптом оценивает ответы остальных
        tasks = [
            query_model(ROLEPLAY_MODEL, [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": ranking_prompt}
            ])
            for system_prompt in COUNCIL_ROLES.values()
        ]
        responses = await asyncio.gather(*tasks)

        # Формируем результаты с привязкой к ролям
        stage2_results = []
        for role_name, response in zip(COUNCIL_ROLES.keys(), responses):
            if response is not None:
                full_text = response.get('content', '')
                parsed = parse_ranking_from_text(full_text)
                stage2_results.append({
                    "model": ROLEPLAY_MODEL,
                    "role": role_name,
                    "ranking": full_text,
                    "parsed_ranking": parsed
                })

        return stage2_results, label_to_model

    # Режим битвы моделей: все члены совета оценивают ответы параллельно
    messages = [{"role": "user", "content": ranking_prompt}]

    # Получаем рейтинги от всех моделей совета параллельно
    responses = await query_models_parallel(COUNCIL_MODELS, messages)

    # Формируем результаты
    stage2_results = []
    for model, response in responses.items():
        if response is not None:
            full_text = response.get('content', '')
            parsed = parse_ranking_from_text(full_text)
            stage2_results.append({
                "model": model,
                "ranking": full_text,
                "parsed_ranking": parsed
            })

    return stage2_results, label_to_model


async def stage3_synthesize_final(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]],
    mode: str = MODE_ENSEMBLE
) -> Dict[str, Any]:
    """
    Этап 3: председатель синтезирует итоговый ответ.

    Args:
        user_query: Исходный запрос пользователя
        stage1_results: Индивидуальные ответы с этапа 1
        stage2_results: Рейтинги с этапа 2
        mode: Режим работы совета (ensemble или roleplay)

    Returns:
        Словарь с ключами 'model' и 'response'
    """
    # Формируем полный контекст для председателя
    stage1_text = "\n\n".join([
        f"Участник: {get_display_name(result)}\nОтвет: {result['response']}"
        for result in stage1_results
    ])

    stage2_text = "\n\n".join([
        f"Участник: {get_display_name(result)}\nОценка: {result['ranking']}"
        for result in stage2_results
    ])

    if mode == MODE_ROLEPLAY:
        chairman_prompt = f"""Ты — Председатель Совета ИИ. Твоя задача — изучить ответы экспертов (Скептика, Визионера, Исполнителя, Человека со стороны и Проверяющего факты) на запрос пользователя.
Синтезируй их мнения в единое, взвешенное итоговое решение. Учти риски скептика, идеи визионера и шаги исполнителя.

Исходный вопрос: {user_query}

ЭТАП 1 — Ответы экспертов:
{stage1_text}

ЭТАП 2 — Взаимные рейтинги экспертов:
{stage2_text}

Учитывай также:
- Взаимные рейтинги и то, что они говорят о качестве ответов
- Любые закономерности согласия или разногласий

Предоставь чёткий, хорошо обоснованный итоговый ответ, отражающий коллективную мудрость совета:"""
    else:
        chairman_prompt = f"""Вы — Председатель Совета LLM. Несколько моделей ИИ предоставили ответы на вопрос пользователя, а затем проранжировали ответы друг друга.

Исходный вопрос: {user_query}

ЭТАП 1 — Индивидуальные ответы:
{stage1_text}

ЭТАП 2 — Взаимные рейтинги:
{stage2_text}

Ваша задача как Председателя — синтезировать всю эту информацию в один полный, точный и исчерпывающий ответ на исходный вопрос пользователя. Учитывайте:
- Индивидуальные ответы и их идеи
- Взаимные рейтинги и то, что они говорят о качестве ответов
- Любые закономерности согласия или разногласий

Предоставьте чёткий, хорошо обоснованный итоговый ответ, отражающий коллективную мудрость совета:"""

    messages = [{"role": "user", "content": chairman_prompt}]

    # Запрашиваем модель председателя
    response = await query_model(CHAIRMAN_MODEL, messages)

    if response is None:
        # Запасной вариант, если председатель не ответил
        return {
            "model": CHAIRMAN_MODEL,
            "response": "Error: Unable to generate final synthesis."
        }

    return {
        "model": CHAIRMAN_MODEL,
        "response": response.get('content', '')
    }


def parse_ranking_from_text(ranking_text: str) -> List[str]:
    """
    Извлечение секции FINAL RANKING из ответа модели.

    Args:
        ranking_text: Полный текстовый ответ модели

    Returns:
        Список меток ответов в порядке рейтинга
    """
    import re

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
    from collections import defaultdict

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


async def generate_conversation_title(user_query: str) -> str:
    """
    Генерация короткого заголовка разговора на основе первого сообщения пользователя.

    Args:
        user_query: Первое сообщение пользователя

    Returns:
        Короткий заголовок (3-5 слов)
    """
    title_prompt = f"""Сгенерируйте очень короткий заголовок (не более 3-5 слов), который кратко описывает следующий вопрос.
Заголовок должен быть лаконичным и описательным. Не используйте кавычки или знаки препинания в заголовке.

Вопрос: {user_query}

Заголовок:"""

    messages = [{"role": "user", "content": title_prompt}]

    # Используем TITLE_MODEL для генерации заголовка (быстро и дёшево)
    response = await query_model(TITLE_MODEL, messages, timeout=30.0)

    if response is None:
        # Запасной вариант — стандартный заголовок
        return "New Conversation"

    title = response.get('content', 'New Conversation').strip()

    # Очищаем заголовок — убираем кавычки, ограничиваем длину
    title = title.strip('"\'')

    # Обрезаем, если слишком длинный
    if len(title) > 50:
        title = title[:47] + "..."

    return title


async def run_full_council(user_query: str, mode: str = MODE_ENSEMBLE) -> Tuple[List, List, Dict, Dict]:
    """
    Запуск полного трёхэтапного процесса совета.

    Args:
        user_query: Вопрос пользователя
        mode: Режим работы совета (ensemble или roleplay)

    Returns:
        Кортеж (результаты этапа 1, результаты этапа 2, результат этапа 3, метаданные)
    """
    # Этап 1: сбор индивидуальных ответов
    stage1_results = await stage1_collect_responses(user_query, mode)

    # Если ни один участник не ответил успешно, возвращаем ошибку
    if not stage1_results:
        return [], [], {
            "model": "error",
            "response": "All participants failed to respond. Please try again."
        }, {}

    # Этап 2: сбор рейтингов
    stage2_results, label_to_model = await stage2_collect_rankings(user_query, stage1_results, mode)

    # Расчёт агрегированных рейтингов
    aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)

    # Этап 3: синтез итогового ответа
    stage3_result = await stage3_synthesize_final(
        user_query,
        stage1_results,
        stage2_results,
        mode
    )

    # Формируем метаданные
    metadata = {
        "mode": mode,
        "label_to_model": label_to_model,
        "aggregate_rankings": aggregate_rankings
    }

    return stage1_results, stage2_results, stage3_result, metadata
