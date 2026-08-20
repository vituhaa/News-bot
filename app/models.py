from datetime import datetime
from typing import Optional, Literal, List

# Типы статусов
PostStatus = Literal['pending', 'revision', 'published', 'rejected', 'draft']
UserRole = Literal['superadmin', 'admin']

# Модель новости
class Post:
    def __init__(
        self,
        user_id: int,
        username: str,
        topic: str,
        text: str,
        category: Optional[str] = None,
        media_ids: Optional[List[str]] = None,
        media_types: Optional[List[str]] = None,
        media_names: Optional[List[str]] = None,
        status: str = 'draft'
    ):
        self.id = None  # будет присвоен при сохранении
        self.user_id = user_id
        self.username = username
        self.topic = topic
        self.text = text
        self.category = category
        self.media_ids = media_ids or []
        self.media_types = media_types or []
        self.media_names = media_names or []

        # Системные поля
        self.status = status
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        
        # Модерация
        self.taken_by: Optional[int] = None
        self.taken_at: Optional[datetime] = None
        self.moderated_by: Optional[int] = None
        self.moderated_at: Optional[datetime] = None
        self.comment: Optional[str] = None
        
        # Публикация
        self.channel_message_id: Optional[int] = None
        self.channel_post_url: Optional[str] = None

    # Преобразует объект в словарь для хранения (временно)
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.username,
            'topic': self.topic,
            'text': self.text,
            'category': self.category,
            'media_ids': self.media_ids,
            'media_types': self.media_types,
            'media_names': self.media_names,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'taken_by': self.taken_by,
            'taken_at': self.taken_at.isoformat() if self.taken_at else None,
            'moderated_by': self.moderated_by,
            'moderated_at': self.moderated_at.isoformat() if self.moderated_at else None,
            'comment': self.comment,
            'channel_message_id': self.channel_message_id,
            'channel_post_url': self.channel_post_url
        }

    # Преобразует словарь в объект
    @classmethod
    def from_dict(cls, data: dict) -> 'Post':
        post = cls(
            user_id=data['user_id'],
            username=data['username'],
            topic=data['topic'],
            text=data['text'],
            category=data.get('category'),
            media_ids=data.get('media_ids', []),
            media_types=data.get('media_types', []),
            media_names=data.get('media_names', [])
        )
        post.id = data['id']
        post.status = data['status']
        post.created_at = datetime.fromisoformat(data['created_at'])
        post.updated_at = datetime.fromisoformat(data['updated_at'])
        post.taken_by = data.get('taken_by')
        post.taken_at = datetime.fromisoformat(data['taken_at']) if data.get('taken_at') else None
        post.moderated_by = data.get('moderated_by')
        post.moderated_at = datetime.fromisoformat(data['moderated_at']) if data.get('moderated_at') else None
        post.comment = data.get('comment')
        post.channel_message_id = data.get('channel_message_id')
        post.channel_post_url = data.get('channel_post_url')
        return post

# Модель администратора
class Admin:
    def __init__(
        self,
        user_id: int,
        username: str,
        role: UserRole = 'admin',
        added_by: Optional[int] = None
    ):
        self.user_id = user_id
        self.username = username
        self.role: UserRole = role
        self.added_by = added_by
        self.added_at = datetime.now()

    def to_dict(self) -> dict:
        return {
            'user_id': self.user_id,
            'username': self.username,
            'role': self.role,
            'added_by': self.added_by,
            'added_at': self.added_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Admin':
        admin = cls(
            user_id=data['user_id'],
            username=data['username'],
            role=data['role'],
            added_by=data.get('added_by')
        )
        admin.added_at = datetime.fromisoformat(data['added_at'])
        return admin

# Категории постов
class Category:

    def __init__(self, name: str):
        self.id = None
        self.name = name

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Category':
        cat = cls(
            name=data['name'],
        )
        cat.id = data['id']
        return cat