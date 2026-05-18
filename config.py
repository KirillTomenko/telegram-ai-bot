import os
import logging
from dotenv import load_dotenv

# Загружаем .env
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Telegram
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден в .env файле!")

# === Определение активного API-провайдера ===
def get_active_provider():
    """
    Возвращает название активного провайдера.
    Приоритет: ProxyAPI > OpenAI > GenAPI
    Если указан только ProxyAPI — используем его.
    """
    proxy_key = os.getenv('PROXYAPI_KEY')
    openai_key = os.getenv('OPENAI_API_KEY')
    genapi_key = os.getenv('GENAPI_KEY')
    
    # Считаем, сколько ключей указано
    provided_keys = {
        'proxyapi': bool(proxy_key),
        'openai': bool(openai_key),
        'genapi': bool(genapi_key)
    }
    active = [k for k, v in provided_keys.items() if v]
    
    if not active:
        raise ValueError("❌ Не найден ни один API-ключ (PROXYAPI_KEY / OPENAI_API_KEY / GENAPI_KEY)")
    
    # Если только ProxyAPI — возвращаем его
    if active == ['proxyapi']:
        logger.info("🔑 Активен только ProxyAPI — используем его")
        return 'proxyapi'
    
    # Приоритет по умолчанию: ProxyAPI > OpenAI > GenAPI
    if provided_keys['proxyapi']:
        return 'proxyapi'
    elif provided_keys['openai']:
        return 'openai'
    else:
        return 'genapi'

ACTIVE_PROVIDER = get_active_provider()
logger.info(f"🎯 Активный провайдер: {ACTIVE_PROVIDER.upper()}")

# Настройки API
API_CONFIG = {
    'proxyapi': {
        'key': os.getenv('PROXYAPI_KEY'),
        'base_url': os.getenv('PROXYAPI_BASE_URL', 'https://api.proxyapi.ru/openai/v1'),
        'endpoint': '/chat/completions'
    },
    'openai': {
        'key': os.getenv('OPENAI_API_KEY'),
        'base_url': 'https://api.openai.com/v1',
        'endpoint': '/chat/completions'
    },
    'genapi': {
        'key': os.getenv('GENAPI_KEY'),
        'base_url': os.getenv('GENAPI_BASE_URL', 'https://api.genapi.ai/v1'),
        'endpoint': '/chat/completions'
    }
}

# Настройки модели
DEFAULT_MODEL = os.getenv('DEFAULT_MODEL', 'gpt-4o-mini')
DEFAULT_TEMPERATURE = float(os.getenv('DEFAULT_TEMPERATURE', 0.7))
DEFAULT_MAX_TOKENS = int(os.getenv('DEFAULT_MAX_TOKENS', 1000))
MAX_CONTEXT_MESSAGES = int(os.getenv('MAX_CONTEXT_MESSAGES', 10))