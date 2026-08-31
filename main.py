import asyncio
import os
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters.command import Command
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiohttp import web
from dotenv import load_dotenv

from app.student_handler import user_router
from app.admin_handler import admin_router, init_admins, set_dispatcher
from app.superadmin_handler import super_router
from app.db import close_pool
from app.storage import storage
import logging

load_dotenv()
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('BOT_TOKEN')
PROXY_URL = os.getenv('PROXY_URL')
SUPER_ADMINS = os.getenv("SUPER_ADMINS", "")
super_admins_list = [x.strip() for x in SUPER_ADMINS.split(",") if x.strip()]

logging.basicConfig(level=logging.INFO)

dispatcher = Dispatcher()
dispatcher.include_router(user_router)
dispatcher.include_router(admin_router)
dispatcher.include_router(super_router)
set_dispatcher(dispatcher)

@dispatcher.message(Command("id"))
async def get_id(message: Message):
    user = message.from_user
    await message.answer(
        f"Ваш ID: {user.id}",
        parse_mode=ParseMode.MARKDOWN
    )


async def healthcheck(request: web.Request):
    return web.Response(text="Bot is alive!")


async def reminder(bot: Bot):
    while True:
        try:
            drafts = await storage.get_old_draft(days=1)
            for post in drafts:
                try:
                    await bot.send_message(post.user_id,
                                           "Вы не закончили новость. Продолжите заполнение? (команда /start)")
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"Не удалось отправить напоминание: {e}")
        except Exception as e:
            logger.error(f"Ошибка в функции: {e}")
        await asyncio.sleep(86400)


async def main():
    session = AiohttpSession(proxy=PROXY_URL)
    bot = Bot(token=BOT_TOKEN, session=session)
    try:
        bot_info = await bot.get_me()
        print(f"Бот @{bot_info.username} подключён")

        await init_admins(super_admins_list)
        asyncio.create_task(reminder(bot))
        await storage.init_default_categories()

        await bot.delete_webhook(drop_pending_updates=True)
        await dispatcher.start_polling(bot)

    finally:
        await bot.session.close()
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())