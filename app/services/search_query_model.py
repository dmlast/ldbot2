# app/services/search_query_model.py

import os
import asyncio
import re
from typing import Optional, Tuple

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
# 2) Утилита для "санитизации" поискового запроса
###############################################################################
def sanitize_search_query(text: str) -> str:
    """
    Удаляет/очищает все нежелательные фрагменты из сгенерированного поискового запроса.
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
# 3) Основная функция get_search_query, вызывающая YandexGPT через SDK
###############################################################################
async def get_search_query(user_query: str) -> Optional[str]:
    """
    Генерирует наиболее релевантный поисковый запрос на основе пользовательского запроса.

    Возвращает:
      - search_query (str|null): Сгенерированный поисковый запрос или None при ошибке.

    user_query - строка запроса пользователя.
    """
    system_msg = (
        "Ты помощник, который преобразует пользовательские вопросы в наиболее релевантные поисковые запросы "
        "для поисковых систем. Сформируй четкий и точный запрос, который позволит получить максимально релевантные результаты."
    )
    prompt_text = f"""
Пользовательский запрос: "{user_query}"

Сформируй наиболее релевантный поисковый запрос для поисковой системы на основе данного вопроса.
Ответь только строкой с поисковым запросом без дополнительных пояснений.
"""

    final_prompt = f"{system_msg}\n\n{prompt_text}"

    # Генерируем текст с помощью YandexGPT
    try:
        result = await asyncio.to_thread(model.run, final_prompt)
    except Exception as e:
        print(f"[YandexGPT] Generation error: {e}")
        return None

    # Предполагается, что result это объект с атрибутом `alternatives`
    if not hasattr(result, "alternatives") or not result.alternatives:
        return None

    generated_text = result.alternatives[0].text

    if not generated_text:
        return None

    # Санитизируем сгенерированный поисковый запрос
    search_query = sanitize_search_query(generated_text)

    if not search_query:
        return None

    return search_query
