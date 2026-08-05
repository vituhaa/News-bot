import asyncio
import os
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession

from app.student_handler import user_router
from app.admin_handler import admin_router, init_admins
from app.config import BOT_TOKEN, PROXY_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    init_admins()
    
    session = AiohttpSession(proxy=PROXY_URL) if PROXY_URL else None
    bot = Bot(token=BOT_TOKEN, session=session)
    
    dispatcher = Dispatcher()
    dispatcher.include_router(user_router)
    dispatcher.include_router(admin_router)
    
    try:
        bot_info = await bot.get_me()
        logger.info(f"Бот @{bot_info.username} подключён")
        
        await bot.delete_webhook(drop_pending_updates=True)
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())