# app/main.py

import asyncio
import logging

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError

from app.schemas.request import PredictionRequest
from app.schemas.response import PredictionResponse

# Импортируем обновлённые функции
from app.services.search_query_model import get_search_query
from app.services.yandex_search import perform_yandex_search
from app.services.news import get_latest_news
from app.services.language_model import get_answer

from app.utils.exceptions import validation_exception_handler, generic_exception_handler

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

app = FastAPI()

# Регистрация обработчиков исключений
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

@app.post("/api/request", response_model=PredictionResponse)
async def predict(body: PredictionRequest):
    """
    Эндпоинт для обработки запроса PredictionRequest.
    """
    try:
        logging.info(f"Processing prediction request with id: {body.id}")

        # 1. Получаем search_query на основе пользовательского запроса
        search_query = await get_search_query(body.query)
        if not search_query:
            raise ValueError("Не удалось сгенерировать поисковый запрос.")

        logging.info(f"Generated search query: {search_query}")

        # 2. Выполняем поиск через Yandex Search с использованием search_query
        yandex_search_results = await perform_yandex_search(search_query, 3)  # Получаем до 3 результатов

        logging.info(f"Yandex Search results: {yandex_search_results}")

        # 3. Получаем актуальные новости
        latest_news = await get_latest_news()

        logging.info(f"Latest news: {latest_news}")

        # 4. Вызываем языковую модель с результатами поиска и новостями
        answer, reasoning, sources = await get_answer(body.query, yandex_search_results, latest_news)

        # Убираем дубли и ограничиваем количество источников до 3
        unique_sources = list(dict.fromkeys(sources))[:3]

        # Формируем итоговый объект ответа (PredictionResponse)
        response_data = PredictionResponse(
            id=body.id,
            answer=answer,
            reasoning=reasoning,
            sources=unique_sources
        )

        logging.info(f"Successfully processed request {body.id}")
        return response_data

    except ValueError as e:
        error_msg = str(e)
        logging.error(f"Validation error for request {body.id}: {error_msg}")
        raise HTTPException(status_code=400, detail=error_msg)

    except Exception as e:
        logging.error(f"Internal error processing request {body.id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
