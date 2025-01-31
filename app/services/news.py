import feedparser
from typing import List
from aiocache import cached, Cache

RSS_URL = "https://Itmo.ru/rss"  # Замените на фактический URL RSS-ленты

@cached(ttl=300, cache=Cache.MEMORY)  # Кэшировать на 5 минут
async def get_latest_news() -> List[str]:
    """
    Получает последние новости из RSS-ленты Университета ИТМО.
    """
    try:
        feed = feedparser.parse(RSS_URL)
        
        news_links = []
        for entry in feed.entries[:3]:
            news_links.append(str(entry.link))
        return news_links
    except Exception as e:
        print(f"Error in get_latest_news: {e}")
        return []
