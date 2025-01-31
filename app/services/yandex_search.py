import asyncio
from typing import List, Dict
from aiocache import cached, Cache
import aiohttp
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import re

from yandex_cloud_ml_sdk import YCloudML

# 📌 Данные для API Яндекса (замените на свои)
YANDEX_FOLDER_ID = "b1g9uv256jlf1pq349lq"  # ID папки в Yandex Cloud
YANDEX_API_KEY = "AQVNya6rksDSvOKJbQdaXiLdVXTFUyF5hMzXkQio"  # Ваш API ключ

# 📌 Ограничения
MAX_RESULTS = 3        # Сколько страниц берем
MAX_TEXT_LENGTH = 1000 # Максимальная длина текста

# 📌 Маппинг языков к доменам Яндекса
LANGUAGE_DOMAIN_MAP = {
    "lang_ru": "yandex.ru",
    "lang_tr": "yandex.com.tr",
    "lang_com": "yandex.com"
}

# Инициализируем YandexGPT для очистки текста
ycp_sdk = YCloudML(
    folder_id=YANDEX_FOLDER_ID,
    auth=YANDEX_API_KEY,
)
yandex_gpt_model = ycp_sdk.models.completions("yandexgpt")
yandex_gpt_model = yandex_gpt_model.configure(temperature=0.5)


@cached(ttl=300, cache=Cache.MEMORY)  # Кэшируем результаты на 5 минут
async def perform_yandex_search(query: str, num_results: int = MAX_RESULTS, languages: List[str] = ["lang_ru"]) -> List[Dict[str, str]]:
    """
    Выполняет поиск через Yandex Search API v1, получает наиболее релевантные страницы и очищает их контент.
    Возвращает список словарей с заголовком, ссылкой и текстом страницы.
    
    :param query: Поисковый запрос.
    :param num_results: Общее количество результатов.
    :param languages: Список языковых ограничений (например, ["lang_ru", "lang_en"]).
    :return: Список словарей с ключами 'title', 'url', 'text'.
    """
    search_results = []

    async with aiohttp.ClientSession() as session:
        for lang in languages:
            # Получаем домен для языка (в данном примере используем фиксированный)
            domain = LANGUAGE_DOMAIN_MAP.get(lang, "yandex.ru")
            if not domain:
                print(f"⚠️ Неизвестный язык: {lang}. Пропускаем.")
                continue

            # Формируем параметры запроса
            params = {
                "folderid": YANDEX_FOLDER_ID,
                "apikey": YANDEX_API_KEY,
                "query": query,
                "lr": "213",            # ID региона для России (Москва). Замените на нужный регион
                "l10n": "ru",           # Язык уведомлений
                "sortby": "rlv",        # Сортировка по релевантности
                "filter": "strict",     # Фильтр семейства сайтов
                "groupby": "attr=d.mode=deep.groups-on-page=1.docs-in-group=1",  # Настроено под MAX_RESULTS=1
                "maxpassages": "3",
                "page": "0"             # Первая страница
            }

            # Формируем URL запроса
            search_url = f"https://{domain}/search/xml"

            try:
                # Отправляем GET-запрос к Yandex Search API v1
                async with session.get(search_url, params=params) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        print(f"⚠️ Ошибка запроса к Yandex API: статус {response.status}")
                        print(f"🔍 Текст ошибки: {error_text[:500]}...")
                        continue

                    # Получаем текст ответа
                    response_text = await response.text()

                    # Парсим XML-ответ
                    try:
                        root = ET.fromstring(response_text)
                    except ET.ParseError as parse_error:
                        print(f"⚠️ Ошибка парсинга XML: {parse_error}")
                        print(f"🔍 Сырой ответ: {response_text[:500]}...")
                        continue

                    # Извлекаем документы из XML
                    docs = root.findall(".//doc")
                    if not docs:
                        print("⚠️ Нет релевантных результатов в Яндексе.")
                        continue

                    for doc in docs:
                        url = doc.findtext("url")
                        if url:
                            url = url.strip()  # Убираем лишние пробелы и переносы
                        title = doc.findtext("title", default="Без заголовка")
                        if url and url not in [result["url"] for result in search_results]:
                            search_results.append({"title": title, "url": url})
                            if len(search_results) >= num_results:
                                break

            except Exception as e:
                print(f"⚠️ Ошибка при выполнении запроса к Yandex API: {e}")
                continue

            if len(search_results) >= num_results:
                break

    if not search_results:
        print("⚠️ Нет релевантных результатов в Яндексе.")
        return []

    # Асинхронно скачиваем и парсим страницы
    tasks = [scrape_page(result["url"]) for result in search_results]
    scraped_results = await asyncio.gather(*tasks)

    # Объединяем заголовки и ссылки с текстом
    final_results = []
    for i, scraped in enumerate(scraped_results):
        if scraped["text"]:
            final_results.append({
                "title": search_results[i]["title"],
                "url": search_results[i]["url"],
                "text": scraped["text"]
            })

    return final_results


async def strong_clean_text(text: str) -> str:
    """
    Использует YandexGPT для очень сильной очистки входящего текста.
    Инструкция: очисти текст от HTML-тегов, спецсимволов, комментариев и лишних пробелов, оставь только чистый, хорошо структурированный текст.
    """
    system_msg = (
        "Ты помощник по очистке текста. Очисти следующий текст от HTML-тегов, спецсимволов, комментариев, избыточных пробелов и любых неинформативных данных. "
        "Верни только чистый текст без дополнительных пояснений. "
    )
    prompt = f"{system_msg}\n\nТекст:\n{text}\n\nЧистый текст:"
    try:
        result = await asyncio.to_thread(yandex_gpt_model.run, prompt)
        if hasattr(result, "alternatives") and result.alternatives:
            cleaned = result.alternatives[0].text.strip()
            # Если очистка вернула пустой результат — возвращаем исходный текст
            return cleaned if cleaned else text
        else:
            return text
    except Exception as e:
        print(f"⚠️ Ошибка при сильной очистке текста: {e}")
        return text


async def scrape_page(url: str) -> Dict[str, str]:
    """
    Загружает страницу по URL, очищает HTML и извлекает текст.
    
    :param url: URL страницы для скрапинга.
    :return: Словарь с ключами 'title', 'url', 'text'.
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    print(f"⚠️ Ошибка загрузки страницы {url}: статус {response.status}")
                    return {"title": "Ошибка загрузки", "url": url, "text": ""}
                html = await response.text()

        soup = BeautifulSoup(html, "html.parser")

        # Удаляем ненужные элементы
        for tag in soup(["script", "style", "meta", "head", "footer", "nav", "aside"]):
            tag.decompose()

        # Извлекаем заголовок
        title_tag = soup.find('title')
        title = title_tag.get_text(strip=True) if title_tag else "Без заголовка"

        # Извлекаем текст
        text = soup.get_text(separator="\n", strip=True)

        # Ограничиваем длину текста
        if len(text) > MAX_TEXT_LENGTH:
            text = text[:MAX_TEXT_LENGTH] + "..."

        # Применяем очень сильную очистку с помощью YandexGPT
        cleaned_text = await strong_clean_text(text)

        return {"title": title, "url": url, "text": cleaned_text}

    except Exception as e:
        print(f"⚠️ Ошибка при скрапинге {url}: {e}")
        return {"title": "Ошибка загрузки", "url": url, "text": ""}
