import asyncio
import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram.client.session.aiohttp import AiohttpSession
from aiohttp import web
from app.handler import user_router
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
PROXY_URL = os.getenv('PROXY_URL')

logging.basicConfig(level=logging.INFO)

dispatcher = Dispatcher()
dispatcher.include_router(user_router)

async def healthcheck(request: web.Request):
    return web.Response(text="Bot is alive!")

async def main():
    session = AiohttpSession(proxy=PROXY_URL)
    bot = Bot(token=BOT_TOKEN, session=session)
    try:
        bot_info = await bot.get_me()
        print(f"Бот @{bot_info.username} подключён")

        await bot.delete_webhook(drop_pending_updates=True)
        await dispatcher.start_polling(bot)

    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())