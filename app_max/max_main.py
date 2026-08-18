import asyncio
import os
import logging
from dotenv import load_dotenv
from maxapi import Bot, Dispatcher

from app_max.max_student_handler import user_router

load_dotenv()

from max_admin_handler import admin_router
dp.include_router(admin_router)

MAX_BOT_TOKEN = os.getenv("MAX_BOT_TOKEN")  # токен в .env! после получения

logging.basicConfig(level=logging.INFO)

dp = Dispatcher()
dp.include_router(user_router)

async def main():
    bot = Bot(token=MAX_BOT_TOKEN)
    print("бот запущен в режиме Long Polling")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())