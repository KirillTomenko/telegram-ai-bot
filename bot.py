import asyncio
import os
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.client.bot import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession

from config import BOT_TOKEN, logger
from context_manager import ContextManager
from api_client import APIClient

context_manager = ContextManager()
api_client = APIClient()
dp = Dispatcher()

# Хранилище статистики по пользователям
user_stats = {}

def get_system_context():
    now = datetime.now()
    weekdays_ru = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
    months_ru = ["", "января", "февраля", "марта", "апреля", "мая", "июня", 
                 "июля", "августа", "сентября", "октября", "ноября", "декабря"]
    date_str = f"{now.day} {months_ru[now.month]} {now.year} года"
    weekday_str = weekdays_ru[now.weekday()]
    time_str = now.strftime("%H:%M")
    return f"Сегодня {date_str}, {weekday_str}. Время: {time_str}."

def get_system_prompt():
    return (f"Ты — полезный ассистент в Telegram. Отвечай кратко, по делу, на русском языке. "
            f"{get_system_context()} Всегда используй эту дату при ответах о времени.")

def create_bot_session():
    proxy_url = os.getenv('TELEGRAM_PROXY')
    if proxy_url:
        logger.info(f"Telegram через прокси: {proxy_url}")
        return AiohttpSession(proxy=proxy_url)
    logger.info("Telegram без прокси")
    return AiohttpSession()

def get_user_stats(user_id):
    if user_id not in user_stats:
        user_stats[user_id] = {
            'total_requests': 0,
            'total_tokens_in': 0,
            'total_tokens_out': 0,
            'last_model': 'N/A'
        }
    return user_stats[user_id]

def update_user_stats(user_id, tokens_in, tokens_out, model):
    stats = get_user_stats(user_id)
    stats['total_requests'] += 1
    stats['total_tokens_in'] += tokens_in
    stats['total_tokens_out'] += tokens_out
    stats['last_model'] = model

@dp.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    context_manager.clear_context(user_id)
    provider_info = api_client.get_provider_info()
    current_date = get_system_context()
    text = (f"👋 Привет, {message.from_user.first_name}!\n\n"
            f"🤖 Я AI-бот, работаю через {provider_info['provider'].upper()}\n"
            f"📅 {current_date}\n"
            f"💬 Напиши мне что угодно — я отвечу!\n\n"
            f"📊 /stats — статистика использования\n"
            f"🔄 /clear — очистить контекст диалога")
    await message.answer(text, parse_mode="Markdown")
    logger.info(f"Пользователь {user_id} начал диалог")

@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    user_id = message.from_user.id
    stats = get_user_stats(user_id)
    context_stats = context_manager.get_context_stats(user_id)
    provider = api_client.get_provider_info()
    
    text = (f"📊 **Статистика использования**\n\n"
            f"👤 Ваш ID: {user_id}\n"
            f"💬 Сообщений в контексте: {context_stats['messages_count']}\n"
            f"🤖 Модель AI: {stats['last_model']}\n"
            f"📝 Максимум сообщений в контексте: {context_manager.__class__.__name__}\n\n"
            f"📈 **Общая статистика:**\n"
            f"• Всего запросов: {stats['total_requests']}\n"
            f"• Токенов вход: {stats['total_tokens_in']}\n"
            f"• Токенов выход: {stats['total_tokens_out']}\n"
            f"• Всего токенов: {stats['total_tokens_in'] + stats['total_tokens_out']}\n\n"
            f"🔌 Провайдер: {provider['provider'].upper()}\n\n"
            f"Используйте /clear для очистки контекста.")
    
    await message.answer(text, parse_mode="Markdown")
    logger.info(f"Пользователь {user_id} запросил статистику")

@dp.message(Command("clear"))
async def cmd_clear(message: Message):
    user_id = message.from_user.id
    if context_manager.clear_context(user_id):
        await message.answer("✅ Контекст диалога очищен! Можете начать новый разговор.")
        logger.info(f"Пользователь {user_id} очистил контекст")
    else:
        await message.answer("ℹ️ Контекст уже пуст.")

@dp.message(Command("reset"))
async def cmd_reset(message: Message):
    # Алиас для /clear
    await cmd_clear(message)

@dp.message(Command("info"))
async def cmd_info(message: Message):
    # Алиас для /stats
    await cmd_stats(message)

@dp.message()
async def handle_message(message: Message):
    user_id = message.from_user.id
    user_text = message.text
    context_manager.add_message(user_id, "user", user_text)
    messages = [{"role": "system", "content": get_system_prompt()}]
    messages.extend(context_manager.get_context(user_id))
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    logger.info(f"Пользователь {user_id}: {user_text[:100]}...")
    response = api_client.generate_response(messages)
    
    if response["success"]:
        answer = response["content"]
        context_manager.add_message(user_id, "assistant", answer)
        usage = response.get("usage", {})
        if usage:
            tokens_in = usage.get("prompt_tokens", 0)
            tokens_out = usage.get("completion_tokens", 0)
            model_used = response.get("model_used", "gpt-4o-mini")
            update_user_stats(user_id, tokens_in, tokens_out, model_used)
            logger.info(f"Токены: вх={tokens_in}, вых={tokens_out}")
        await message.answer(answer)
        logger.info(f"Ответ отправлен пользователю {user_id}")
    else:
        error_msg = response.get("error", "Неизвестная ошибка")
        logger.error(f"Ошибка для пользователя {user_id}: {error_msg}")
        await message.answer("😔 Ошибка AI. Попробуйте позже или /clear.")

async def main():
    logger.info("Запуск Telegram-бота...")
    logger.info(f"Активный провайдер: {api_client.get_provider_info()['provider'].upper()}")
    os.makedirs("logs", exist_ok=True)
    session = create_bot_session()
    bot = Bot(token=BOT_TOKEN, session=session, default=DefaultBotProperties(parse_mode="Markdown"))
    logger.info("Бот запущен и ожидает сообщения...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.exception(f"Критическая ошибка: {e}")