import asyncio
import os
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters.command import Command
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiogram.enums import ParseMode
from dotenv import load_dotenv
from app.student_handler import user_router
from app.admin_handler import admin_router, init_admins, set_dispatcher
from app.superadmin_handler import super_router
from app.db import close_pool
from app.storage import storage

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


BOT_TOKEN = os.getenv("BOT_TOKEN")
PROXY_URL = os.getenv("PROXY_URL")

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
if not WEBHOOK_URL and RENDER_EXTERNAL_URL:
    WEBHOOK_URL = f"{RENDER_EXTERNAL_URL.rstrip('/')}/webhook"

PORT = int(os.getenv("PORT", "10000"))

SUPER_ADMINS = os.getenv("SUPER_ADMINS", "")
super_admins_list = [x.strip() for x in SUPER_ADMINS.split(",") if x.strip()]

dispatcher = Dispatcher()

dispatcher.include_router(user_router)
dispatcher.include_router(admin_router)
dispatcher.include_router(super_router)

set_dispatcher(dispatcher)

@dispatcher.message(Command("id"))
async def get_id(message: Message):
    await message.answer(
        f"Ваш ID: {message.from_user.id}",
        parse_mode=ParseMode.MARKDOWN
    )

async def healthcheck(request: web.Request):
    return web.Response(text="Bot is alive!")


def create_bot():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не задан")

    if PROXY_URL:
        logger.info("Bot запускается через proxy")
        session = AiohttpSession(proxy=PROXY_URL)
        return Bot(token=BOT_TOKEN, session=session)
        
    logger.info("Bot запускается без proxy")

    return Bot(token=BOT_TOKEN)


bot = create_bot()


async def on_startup(bot: Bot):
    if not WEBHOOK_URL:
        raise RuntimeError(
            "WEBHOOK_URL не задан"
        )

    logger.info("Инициализация приложения")

    await init_admins(super_admins_list)
    await storage.init_default_categories()
    bot_info = await bot.get_me()

    logger.info(f"Бот @{bot_info.username} подключён")

    await bot.set_webhook(url=WEBHOOK_URL, secret_token=WEBHOOK_SECRET)

    logger.info(f"Webhook установлен: {WEBHOOK_URL}")


async def on_shutdown(bot: Bot):
    logger.info("Завершение работы")
    await close_pool()


def create_app():
    app = web.Application()

    app.router.add_get("/", healthcheck)

    webhook_handler = SimpleRequestHandler(
        dispatcher=dispatcher,
        bot=bot,
        secret_token=WEBHOOK_SECRET,
    )

    webhook_handler.register(app, path="/webhook")

    dispatcher.startup.register(on_startup)
    dispatcher.shutdown.register(on_shutdown)
    setup_application(app, dispatcher, bot=bot)

    return app


if __name__ == "__main__":
    web.run_app(create_app(), host="0.0.0.0", port=PORT)