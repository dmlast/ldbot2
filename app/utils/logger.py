from aiologger import Logger
from aiologger.handlers.files import AsyncFileHandler

async def setup_logger():
    logger = Logger.with_default_handlers(name="itmo_chatbot")
    handler = AsyncFileHandler("app.log")
    await logger.add_handler(handler)
    return logger