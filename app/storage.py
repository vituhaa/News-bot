import json
from datetime import datetime
from typing import List, Optional, Dict

from app.models import Post, Admin, PostStatus
from app.db import get_pool

class Storage:
    def __init__(self):
        pass

    # ==================== ПОСТЫ ====================

    async def create_post(self, post: Post) -> Post:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO posts (
                    user_id, username, topic, text, category, 
                    media_ids, media_types, media_names, status,
                    created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                RETURNING id
            """, 
                post.user_id,
                post.username,
                post.topic,
                post.text,
                post.category,
                json.dumps(post.media_ids),
                json.dumps(post.media_types),
                json.dumps(post.media_names),
                post.status,
                post.created_at,
                post.updated_at
            )
            post.id = row['id']
            return post

    async def get_post(self, post_id: int) -> Optional[Post]:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM posts WHERE id = $1", post_id)
            if not row:
                return None
            return self._row_to_post(row)

    async def get_all_posts(
        self,
        status: Optional[PostStatus] = None,
        user_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Post]:
        pool = await get_pool()
        async with pool.acquire() as conn:
            query = "SELECT * FROM posts"
            conditions = []
            params = []
            if status:
                conditions.append(f"status = ${len(params)+1}")
                params.append(status)
            if user_id:
                conditions.append(f"user_id = ${len(params)+1}")
                params.append(user_id)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY created_at DESC LIMIT $" + str(len(params)+1) + " OFFSET $" + str(len(params)+2)
            params.extend([limit, offset])
            rows = await conn.fetch(query, *params)
            return [self._row_to_post(row) for row in rows]

    async def get_posts_by_status(self, status: PostStatus) -> List[Post]:
        return await self.get_all_posts(status=status)

    async def get_pending_posts(self) -> List[Post]:
        return await self.get_all_posts(status='pending')

    async def update_post(self, post_id: int, **kwargs) -> bool:
        pool = await get_pool()
        
        for field in ['taken_at', 'moderated_at', 'created_at', 'updated_at']:
            if field in kwargs and isinstance(kwargs[field], datetime):
                kwargs[field] = kwargs[field].isoformat()
        
        for field in ['media_ids', 'media_types', 'media_names']:
            if field in kwargs and kwargs[field] is not None:
                kwargs[field] = json.dumps(kwargs[field])

        set_clause = ", ".join([f"{key} = ${i+1}" for i, key in enumerate(kwargs.keys())])
        set_clause += ", updated_at = CURRENT_TIMESTAMP"
        values = list(kwargs.values()) + [post_id]
        query = f"UPDATE posts SET {set_clause} WHERE id = ${len(values)}"
        async with pool.acquire() as conn:
            result = await conn.execute(query, *values)
            return result != "UPDATE 0"  # если затронуто 0 строк – false

    async def delete_post(self, post_id: int) -> bool:
        pool = await get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute("DELETE FROM posts WHERE id = $1", post_id)
            return result != "DELETE 0"

    async def get_pending_count(self) -> int:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT COUNT(*) FROM posts WHERE status = 'pending'")
            return row['count']

    # ==================== АДМИНИСТРАТОРЫ ====================

    async def add_admin(self, admin: Admin) -> Admin:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO admins (user_id, username, role, added_by, added_at)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (user_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    role = EXCLUDED.role,
                    added_by = EXCLUDED.added_by,
                    added_at = EXCLUDED.added_at
            """, admin.user_id, admin.username, admin.role, admin.added_by, admin.added_at)
        return admin

    async def get_admin(self, user_id: int) -> Optional[Admin]:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM admins WHERE user_id = $1", user_id)
            if not row:
                return None
            return self._row_to_admin(row)

    async def get_all_admins(self) -> List[Admin]:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM admins")
            return [self._row_to_admin(row) for row in rows]

    async def remove_admin(self, user_id: int) -> bool:
        pool = await get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute("DELETE FROM admins WHERE user_id = $1", user_id)
            return result != "DELETE 0"

    async def is_admin(self, user_id: int) -> bool:
        admin = await self.get_admin(user_id)
        return admin is not None

    async def is_superadmin(self, user_id: int) -> bool:
        admin = await self.get_admin(user_id)
        return admin is not None and admin.role == 'superadmin'

    # ==================== НАСТРОЙКИ ====================

    async def get_setting(self, key: str):
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT value FROM settings WHERE key = $1", key)
            if row:
                return row['value']
            return None

    async def set_setting(self, key: str, value):
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO settings (key, value) VALUES ($1, $2)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """, key, value)

    async def get_channel_info(self) -> dict:
        channel_link = await self.get_setting('channel_link')
        channel_username = await self.get_setting('channel_username')
        return {
            'channel_link': channel_link,
            'channel_username': channel_username,
            'is_configured': bool(channel_link or channel_username)
        }

    # ==================== СТАТИСТИКА ====================

    async def get_stats(self) -> dict:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT 
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE status = 'pending') AS pending,
                    COUNT(*) FILTER (WHERE status = 'revision') AS revision,
                    COUNT(*) FILTER (WHERE status = 'published') AS published,
                    COUNT(*) FILTER (WHERE status = 'rejected') AS rejected
                FROM posts
            """)
            return {
                'total': row['total'],
                'pending': row['pending'],
                'revision': row['revision'],
                'published': row['published'],
                'rejected': row['rejected']
            }

    # ==================== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ====================

    def _row_to_post(self, row) -> Post:
        post = Post(
            user_id=row['user_id'],
            username=row['username'],
            topic=row['topic'],
            text=row['text'],
            category=row['category'],
            media_ids=json.loads(row['media_ids']) if row['media_ids'] else [],
            media_types=json.loads(row['media_types']) if row['media_types'] else [],
            media_names=json.loads(row['media_names']) if row['media_names'] else [],
            status=row['status']
        )
        post.id = row['id']
        post.created_at = row['created_at']
        post.updated_at = row['updated_at']
        post.taken_by = row['taken_by']
        post.taken_at = row['taken_at']
        post.moderated_by = row['moderated_by']
        post.moderated_at = row['moderated_at']
        post.comment = row['comment']
        post.channel_message_id = row['channel_message_id']
        post.channel_post_url = row['channel_post_url']
        return post

    def _row_to_admin(self, row) -> Admin:
        admin = Admin(
            user_id=row['user_id'],
            username=row['username'],
            role=row['role'],
            added_by=row['added_by']
        )
        admin.added_at = row['added_at']
        return admin


storage = Storage()