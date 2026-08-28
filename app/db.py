import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'news-bot')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', "")

_pool = None

async def get_pool():
    """Возвращает пул соединений (создаёт при первом вызове)."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            min_size=1,
            max_size=10
        )
        # Создаём таблицы при инициализации
        async with _pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS posts (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    username TEXT,
                    topic TEXT NOT NULL,
                    text TEXT NOT NULL,
                    category TEXT,
                    media_ids JSONB,
                    media_types JSONB,
                    media_names JSONB,
                    status TEXT NOT NULL DEFAULT 'draft',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    taken_by BIGINT,
                    taken_at TIMESTAMP,
                    moderated_by BIGINT,
                    moderated_at TIMESTAMP,
                    comment TEXT,
                    channel_message_id BIGINT,
                    channel_post_url TEXT
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS admins (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    role TEXT NOT NULL DEFAULT 'admin',
                    added_by BIGINT,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id SERIAL PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL
                )
            """)
    return _pool

async def close_pool():
    """Закрывает пул соединений при завершении бота."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None