# app/services/language_model.py

import os
import asyncio
import json
import re
from typing import List, Optional, Tuple

from yandex_cloud_ml_sdk import YCloudML

###############################################################################
# 1) Инициализируем YandexGPT через YCloudML SDK
###############################################################################

# Получение переменных окружения
FOLDER_ID = "b1g9uv256jlf1pq349lq"  # Ваш идентификатор каталога
API_KEY = 'AQVNyZn5A_Pwhh0zmfBrLZuFZ9NzhxMJGvQvwRO0'

if not API_KEY:
    raise ValueError("Необходимо установить переменную окружения YANDEX_API_KEY")

# Инициализация SDK
sdk = YCloudML(
    folder_id=FOLDER_ID,
    auth=API_KEY,
)

# Получение модели YandexGPT
model = sdk.models.completions("yandexgpt")
model = model.configure(temperature=0.5)

###############################################################################
# 2) Утилита для "санитизации" reasoning и search_query
###############################################################################
def sanitize_text(text: str) -> str:
    """
    Удаляет/очищает все нежелательные фрагменты из сгенерированного текста.
    Можно расширять правила при необходимости.
    """
    # Удалим лишние символы и пробелы
    text = text.strip()

    # Удалим многострочные комментарии вида /* ... */
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)

    # Удалим строки, начинающиеся с // или содержащие TODO
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        if '//' in line or 'TODO' in line:
            continue
        cleaned_lines.append(line)
    text = '\n'.join(cleaned_lines)

    # Удалим подозрительные ключевые слова
    suspicious_keywords = ['import', 'requests', 'sys', 'Error', 'Usage']
    for kw in suspicious_keywords:
        if kw.lower() in text.lower():
            # Удалим эту строку целиком
            text_lines = text.split('\n')
            text_lines = [ln for ln in text_lines if kw.lower() not in ln.lower()]
            text = '\n'.join(text_lines)

    # Дополнительная чистка от лишних пустых строк
    text = re.sub(r'\n\s*\n+', '\n', text).strip()

    return text

###############################################################################
# 3) Основная функция get_answer, вызывающая YandexGPT через SDK
###############################################################################
async def is_url(s: str) -> bool:
    """
    Проверяет, выглядит ли строка как URL.
    """
    url_pattern = re.compile(
        r'^(?:http|ftp)s?://'  # http:// или https://
        r'\S+$', re.IGNORECASE)
    return re.match(url_pattern, s) is not None

async def get_answer(query: str, yandex_search_results: List[dict], latest_news: List[dict]) -> Tuple[Optional[int], str, List[str]]:
    """
    Генерирует ответ в формате JSON с ключами:
      - answer (int|null),
      - reasoning (str),
      - sources (list).

    :param query: Строка запроса пользователя.
    :param yandex_search_results: Список результатов поиска из Yandex Search.
    :param latest_news: Список актуальных новостей.
    :return: Tuple с ответом, reasoning и списком источников.
    """
    # Формируем контекст из новостей и результатов поиска
    if latest_news:
        context_news = "\n".join([
            f"Новость {i+1}: {news['title']} - {news['text']}" if isinstance(news, dict) else f"Новость {i+1}: {news}"
            for i, news in enumerate(latest_news)
        ])
    else:
        context_news = "Нет актуальных новостей."

    context_search = "\n".join([
        f"Результат поиска {i+1}: {result['title']} - {result['text']}"
        for i, result in enumerate(yandex_search_results)
    ])

    system_msg = (
        "Ты помощник, предоставляющий информацию об Университете ИТМО. "
        "Используй предоставленные данные из новостей и результатов поиска для формирования ответа. "
        "Если вопрос как-то относится с недавними событиями (после начала 2024 года), предпочитай использовать информацию из новостей. "
        "В противном случае используй результаты поиска. "
        "Выбери от одного до трёх НАИБОЛЕЕ релевантных запросу источников из представленных и запиши их в поле 'sources'. "
        "Вставляй ссылки на источники не обработанными, в том числе и на результаты поиска. Источники бери из поля url в результатах поиска и новостях. ВНИМАТЕЛЬНО СЛЕДИ чтобы источники были ссылками, там был в начале https или https "
        "Если вопрос с открытым ответом, установи 'answer' в null. "
        "Если в вопросе есть варианты ответа, предоставь ответ в поле 'answer'. "
        "В начале поля reasoning пиши YandexGPT. "
        "Верни ответ в формате JSON строго со следующими ключами: id, answer, reasoning, sources."
    )
    prompt_text = f"""
    Контекст из новостей:
    {context_news}

    Контекст из результатов поиска:
    {context_search}

    Запрос: "{query}"

    Пожалуйста, ответь только в формате JSON строго со следующими ключами: id, answer, reasoning, sources.
    Не добавляй ничего кроме JSON. Пример формата ответа:

    {{
        "id": 999,
        "answer": 2,  # Для закрытых вопросов
        "reasoning": "YandexGPT. Главный кампус ИТМО находится в Санкт-Петербурге.",
        "sources": ["https://itmo.ru", "https://ru.wikipedia.org/wiki/%D0%A3%D0%BD%D0%B8%D0%B2%D0%B5%D1%80%D1%81%D0%B8%D1%82%D0%B5%D1%82_%D0%98%D0%A2%D0%9C%D0%9E"]
    }}

    Для открытых вопросов, поле "answer" должно быть null.
    Вставляй наиболее релевантные источники как указано выше. Источники бери из поля url в результатах поиска и новостях.
    В начале поля reasoning ВСЕГДА пиши YandexGPT.
    """
    final_prompt = f"{system_msg}\n\n{prompt_text}"

        # Генерируем текст с помощью YandexGPT
    try:
            result = await asyncio.to_thread(model.run, final_prompt)
    except Exception as e:
            print(f"[YandexGPT] Generation error: {e}")
            return (None, "Произошла ошибка при генерации ответа языковой моделью (YandexGPT).", [])

    if not hasattr(result, "alternatives") or not result.alternatives:
            return (None, "Непредвиденный формат ответа от языковой модели.", [])

    generated_text = result.alternatives[0].text
    if not generated_text:
            return (None, "Пустой ответ от языковой модели.", [])

        # Пытаемся найти JSON в сгенерированном тексте
    parsed = None
    match = re.search(r'(\{.*\})', generated_text, flags=re.S)
    if match:
            json_block = match.group(1)
            try:
                parsed = json.loads(json_block)
            except json.JSONDecodeError:
                try:
                    fixed_json = re.sub(r'<int или null>', 'null', json_block)
                    fixed_json = re.sub(r'"<строка>"', '""', fixed_json)
                    fixed_json = re.sub(r'"<url\d+>"', '""', fixed_json)
                    parsed = json.loads(fixed_json)
                except json.JSONDecodeError:
                    pass

    if not parsed or not isinstance(parsed, dict):
            return (None, generated_text.strip(), [])

    answer = parsed.get("answer", None)
    reasoning = parsed.get("reasoning", "")
    raw_sources = parsed.get("sources", [])

    # Приводим answer к типу int, если это список или строка
    if isinstance(answer, list):
        try:
            # Попробуем преобразовать первый элемент списка к целому числу
            answer = int(answer[0])
        except Exception:
            answer = None
    elif isinstance(answer, str):
        try:
            answer = int(answer)
        except Exception:
            answer = None
    # Если answer не int, оставляем его как None
    elif not isinstance(answer, int):
        answer = None

    # Приводим список источников к виду, где каждый элемент является корректным URL
    final_sources = []
    for src in raw_sources:
        if isinstance(src, dict):
            # Если источник передан как словарь, пытаемся взять значение поля 'url'
            url_candidate = src.get("url", "")
            if isinstance(url_candidate, str) and is_url(url_candidate.strip()):
                final_sources.append(url_candidate.strip())
        elif isinstance(src, str):
            src = src.strip()
            # Если строка выглядит как URL — добавляем её
            if is_url(src):
                final_sources.append(src)
            else:
                # Иначе пытаемся извлечь URL из строки
                found_urls = re.findall(r'https?://\S+', src)
                final_sources.extend([u.strip() for u in found_urls if is_url(u.strip())])
        else:
            # Если источник не строка и не словарь, преобразуем его в строку и пытаемся извлечь URL
            src_str = str(src).strip()
            found_urls = re.findall(r'https?://\S+', src_str)
            final_sources.extend([u.strip() for u in found_urls if is_url(u.strip())])

    reasoning_clean = sanitize_text(reasoning)
    if not reasoning_clean:
        reasoning_clean = "Ответ не удалось корректно сформировать."

    return answer, reasoning_clean, final_sources