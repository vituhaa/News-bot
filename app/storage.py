from typing import List, Optional, Dict
from datetime import datetime
from app.models import Post, Admin, Category, PostStatus

# Временное хранилище
class Storage:
    def __init__(self):
        self._posts: Dict[int, dict] = {}
        self._admins: Dict[int, dict] = {}
        self._categories: Dict[int, dict] = {}
        self._post_counter = 0
        self._category_counter = 0
        self._settings = {
            'channel_link': None,
            'channel_username': None,
            'moderation_timeout': 600
        }

    # Категории
    def _init_default_categories(self):
        """Инициализация категорий по умолчанию"""
        default_categories = [
            ("Мероприятие", ""),
            ("Стипендия", ""),
            ("Спорт", ""),
            ("Обучение", "")
        ]
        for name in default_categories:
            cat = Category(name)
            self.add_category(cat)

    # ==================== ПОСТЫ ====================

    def create_post(self, post: Post) -> Post:
        self._post_counter += 1
        post.id = self._post_counter
        self._posts[post.id] = post.to_dict()
        return post

    def get_post(self, post_id: int) -> Optional[Post]:
        data = self._posts.get(post_id)
        return Post.from_dict(data) if data else None

    def get_all_posts(
        self,
        status: Optional[PostStatus] = None,
        user_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Post]:
        posts = []
        for data in self._posts.values():
            if status and data['status'] != status:
                continue
            if user_id and data['user_id'] != user_id:
                continue
            posts.append(Post.from_dict(data))
        posts.sort(key=lambda p: p.created_at, reverse=True)
        return posts[offset:offset + limit]

    def get_posts_by_status(self, status: PostStatus) -> List[Post]:
        return self.get_all_posts(status=status)

    def get_pending_posts(self) -> List[Post]:
        """Посты на модерации (pending + revision)"""
        pending = self.get_all_posts(status='pending')
        
        # Проверим, что это объекты Post
        for p in pending:
            print(f"[DEBUG] Пост {p.id}: {p.status} ({type(p)})")
        return pending

    def update_post(self, post_id: int, **kwargs) -> bool:
        if post_id not in self._posts:
            return False
        
        post_data = self._posts[post_id]
        
        # Конвертируем datetime в строки
        for field in ['taken_at', 'moderated_at', 'created_at', 'updated_at']:
            if field in kwargs and kwargs[field] and isinstance(kwargs[field], datetime):
                kwargs[field] = kwargs[field].isoformat()
        
        kwargs['updated_at'] = datetime.now().isoformat()
        post_data.update(kwargs)
        self._posts[post_id] = post_data
        return True

    def delete_post(self, post_id: int) -> bool:
        if post_id in self._posts:
            del self._posts[post_id]
            return True
        return False

    def get_pending_count(self) -> int:
        return len(self.get_pending_posts())

    # ==================== РАБОТА С АДМИНИСТРАТОРАМИ ====================

    def add_admin(self, admin: Admin) -> Admin:
        self._admins[admin.user_id] = admin.to_dict()
        return admin

    def get_admin(self, user_id: int) -> Optional[Admin]:
        data = self._admins.get(user_id)
        return Admin.from_dict(data) if data else None

    def get_all_admins(self) -> List[Admin]:
        return [Admin.from_dict(data) for data in self._admins.values()]

    def remove_admin(self, user_id: int) -> bool:
        if user_id in self._admins:
            del self._admins[user_id]
            return True
        return False

    # Проверки на права
    def is_admin(self, user_id: int) -> bool:
        return user_id in self._admins

    def is_superadmin(self, user_id: int) -> bool:
        admin = self.get_admin(user_id)
        if admin:
            return admin.role == 'superadmin'
        return False

    # настройки
    def get_setting(self, key: str):
        return self._settings.get(key)

    def set_setting(self, key: str, value):
        self._settings[key] = value

    def get_channel_info(self) -> dict:
        return {
            'channel_link': self._settings.get('channel_link'),
            'channel_username': self._settings.get('channel_username'),
            'is_configured': bool(self._settings.get('channel_link') or self._settings.get('channel_username'))
        }

    # Для получения сводки о постах
    def get_stats(self) -> dict:
        stats = {
            'total': 0,
            'draft': 0,
            'pending': 0,
            'revision': 0,
            'approved': 0,
            'published': 0,
            'rejected': 0
        }
        for data in self._posts.values():
            stats['total'] += 1
            status = data['status']
            if status in stats:
                stats[status] += 1
        return stats

storage = Storage()