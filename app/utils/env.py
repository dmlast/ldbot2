# app/utils/env.py

from dotenv import load_dotenv
import os

load_dotenv()  # Загружаем переменные окружения из .env файла

YC_FOLDER_ID = os.getenv("YC_FOLDER_ID")
YC_API_KEY = os.getenv("YC_API_KEY")
YC_SECRET_KEY = os.getenv("YC_SECRET_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")
YANDEX_XML_API_KEY = os.getenv("YANDEX_XML_API_KEY")

if not all([YC_FOLDER_ID, YC_API_KEY, YC_SECRET_KEY, GOOGLE_API_KEY, GOOGLE_CSE_ID, YANDEX_XML_API_KEY]):
    raise EnvironmentError("Не все необходимые переменные окружения установлены.")
