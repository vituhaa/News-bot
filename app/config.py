import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
PROXY_URL = os.getenv('PROXY_URL')

# Список суперадминов (Id из Telegram)
# ТОЛЬКО временно храним здесь, потом в БД
SUPER_ADMINS = [
    # @reeywert,
    # @vituuha,
    # @azaa_art,
]