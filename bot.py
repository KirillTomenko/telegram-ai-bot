import asyncio
import os
import json
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.client.bot import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession

from config import BOT_TOKEN, logger, DEFAULT_MODEL
from context_manager import ContextManager
from api_client import APIClient

# =============================================================================
# 🌐 Глобальные объекты
# =============================================================================
context_manager = ContextManager()
api_client = APIClient()
dp = Dispatcher()

# Загрузка промптов
PROMPTS = {}
def load_prompts():
    global PROMPTS
    try:
        with open('prompts.json', 'r', encoding='utf-8-sig') as f:
            data = json.load(f)
            for p in data.get('prompts', []):
                PROMPTS[p['name']] = p
        logger.info(f"📚 Загружено промптов: {len(PROMPTS)}")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось загрузить prompts.json: {e}")

load_prompts()

# =============================================================================
# 📅 Функции даты и промптов
# =============================================================================
def get_system_context():
    now = datetime.now()
    weekdays_ru = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
    months_ru = ["", "января", "февраля", "марта", "апреля", "мая", "июня", 
                 "июля", "августа", "сентября", "октября", "ноября", "декабря"]
    date_str = f"{now.day} {months_ru[now.month]} {now.year} года"
    weekday_str = weekdays_ru[now.weekday()]
    time_str = now.strftime("%H:%M")
    return f"Сегодня {date_str}, {weekday_str}. Время: {time_str}."

def get_system_prompt(user_id: int):
    settings = context_manager.get_settings(user_id)
    mode = settings.get('mode', 'default')
    
    if mode in PROMPTS:
        prompt = PROMPTS[mode]
        base = f"{prompt['role']}. {prompt['context']}. {prompt['question']}. Формат: {prompt['format']}"
        if prompt.get('json_output'):
            base += " ОТВЕЧАЙ ТОЛЬКО ВАЛИДНЫМ JSON, БЕЗ ПОЯСНЕНИЙ."
        return f"{base} {get_system_context()}"
    
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
    if not hasattr(get_user_stats, 'store'):
        get_user_stats.store = {}
    if user_id not in get_user_stats.store:
        get_user_stats.store[user_id] = {
            'total_requests': 0, 'total_tokens_in': 0, 'total_tokens_out': 0, 'last_model': 'N/A'
        }
    return get_user_stats.store[user_id]

def update_user_stats(user_id, tokens_in, tokens_out, model):
    stats = get_user_stats(user_id)
    stats['total_requests'] += 1
    stats['total_tokens_in'] += tokens_in
    stats['total_tokens_out'] += tokens_out
    stats['last_model'] = model

# =============================================================================
# 🤖 Хендлеры
# =============================================================================

@dp.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    context_manager.clear_context(user_id)
    provider_info = api_client.get_provider_info()
    settings = context_manager.get_settings(user_id)
    current_date = get_system_context()
    
    text = (f"👋 Привет, {message.from_user.first_name}!\n\n"
            f"🤖 Я AI-бот, работаю через {provider_info['provider'].upper()}\n"
            f"📅 {current_date}\n\n"
            f"⚙️ **Команды:**\n"
            f"• /temp <0.0-1.0> — изменить температуру (сейчас: {settings['temperature']})\n"
            f"• /mode <название> — сменить режим: {', '.join(PROMPTS.keys())}\n"
            f"• /json on|off — включить/выключить JSON-вывод\n"
            f"• /stats — статистика использования\n"
            f"• /clear — очистить контекст\n\n"
            f"💬 Просто напишите сообщение — я отвечу!")
    await message.answer(text, parse_mode="HTML")
    logger.info(f"🚀 Пользователь {user_id} начал диалог")

@dp.message(Command("temp"))
@dp.message(Command("temp"))
async def cmd_temp(message: Message):
    user_id = message.from_user.id
    
    # Извлекаем аргумент команды правильно
    args = message.text.split()
    
    if len(args) < 2:
        settings = context_manager.get_settings(user_id)
        await message.answer(
            f"🌡️ Текущая температура: <code>{settings['temperature']}</code>\n\n"
            f"Использование: <code>/temp 0.7</code>",
            parse_mode="HTML"
        )
        return
    
    try:
        # Пробуем распарсить число (заменяем запятую на точку для надёжности)
        temp_str = args[1].replace(',', '.')
        temp = float(temp_str)
        
        if 0.0 <= temp <= 1.0:
            context_manager.update_setting(user_id, 'temperature', temp)
            await message.answer(f"✅ Температура изменена на <code>{temp}</code>", parse_mode="HTML")
            logger.info(f"🌡️ Пользователь {user_id} установил temperature={temp}")
        else:
            await message.answer("❌ Температура должна быть от 0.0 до 1.0")
    except (ValueError, IndexError) as e:
        logger.warning(f"❌ Ошибка парсинга температуры от пользователя {user_id}: {message.text}")
        await message.answer(
            f"❌ Введите корректное число, например:\n"
            f"<code>/temp 0.7</code>\n<code>/temp 0.2</code>\n<code>/temp 1.0</code>",
            parse_mode="HTML"
        )

@dp.message(Command("mode"))
async def cmd_mode(msg: Message):
    uid = msg.from_user.id
    parts = msg.text.split()
    
    if len(parts) < 2:
        current = context_manager.get_settings(uid)['mode']
        available = ', '.join(f"<code>{k}</code>" for k in PROMPTS.keys())
        await msg.answer(
            f"🎭 Текущий режим: <code>{current}</code>\n"
            f"Доступно: {available}\n"
            f"Пример: <code>/mode код</code>",
            parse_mode="HTML"
        )
        return
    
    m = parts[1].lower()
    if m in PROMPTS:
        context_manager.update_setting(uid, 'mode', m)
        if PROMPTS[m].get('json_output'):
            context_manager.update_setting(uid, 'json_output', True)
        fmt = PROMPTS[m]['format'].replace('<', '&lt;').replace('>', '&gt;')  # экранируем < >
        await msg.answer(
            f"✅ Режим: <code>{m}</code>\n"
            f"📋 Формат: {fmt}",
            parse_mode="HTML"
        )
    else:
        available = ', '.join(f"<code>{k}</code>" for k in PROMPTS.keys())
        await msg.answer(
            f"❌ Режим <code>{m}</code> не найден.\n"
            f"Доступно: {available}",
            parse_mode="HTML"
        )

@dp.message(Command("json"))
async def cmd_json(message: Message):
    user_id = message.from_user.id
    args = message.text.split(maxsplit=1)
    
    if len(args) < 2:
        settings = context_manager.get_settings(user_id)
        status = "✅ ВКЛ" if settings['json_output'] else "❌ ВЫКЛ"
        await message.answer(f"📦 JSON-режим: {status}\n\nИспользование: <code>/json on</code> или <code>/json off</code>")
        return
    
    val = args[1].lower()
    if val in ['on', '1', 'да', 'true']:
        context_manager.update_setting(user_id, 'json_output', True)
        await message.answer("✅ JSON-режим включён. Ответы будут в формате JSON.")
    elif val in ['off', '0', 'нет', 'false']:
        context_manager.update_setting(user_id, 'json_output', False)
        await message.answer("❌ JSON-режим выключен. Обычные текстовые ответы.")
    else:
        await message.answer("❌ Используйте: <code>/json on</code> или <code>/json off</code>")
    
    logger.info(f"📦 Пользователь {user_id} установил json_output={args[1]}")

@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    user_id = message.from_user.id
    stats = get_user_stats(user_id)
    ctx_stats = context_manager.get_context_stats(user_id)
    settings = context_manager.get_settings(user_id)
    provider = api_client.get_provider_info()
    
    total_tokens = stats['total_tokens_in'] + stats['total_tokens_out']
    # Ориентировочная стоимость ~$5/1M токенов для ProxyAPI
    cost_estimate = total_tokens * 5 / 1_000_000
    
    text = (f"📊 **Статистика использования**\n\n"
            f"👤 Ваш ID: <code>{user_id}</code>\n"
            f"💬 Сообщений в контексте: {ctx_stats['messages_count']}\n"
            f"🎭 Режим: <code>{settings['mode']}</code>\n"
            f"🌡️ Температура: <code>{settings['temperature']}</code>\n"
            f"📦 JSON-вывод: {'✅ Да' if settings['json_output'] else '❌ Нет'}\n"
            f"🤖 Модель: {stats['last_model']}\n\n"
            f"📈 **Токены:**\n"
            f"• Вход: {stats['total_tokens_in']}\n"
            f"• Выход: {stats['total_tokens_out']}\n"
            f"• Всего: {total_tokens}\n"
            f"• ~Стоимость: ${cost_estimate:.4f}\n\n"
            f"🔌 Провайдер: {provider['provider'].upper()}\n\n"
            f"Используйте /clear для очистки контекста.")
    
    await message.answer(text, parse_mode="HTML")
    logger.info(f"📊 Пользователь {user_id} запросил статистику")

@dp.message(Command("clear"))
async def cmd_clear(message: Message):
    user_id = message.from_user.id
    if context_manager.clear_context(user_id):
        await message.answer("✅ Контекст диалога очищен! Можете начать новый разговор.")
        logger.info(f"🔄 Пользователь {user_id} очистил контекст")
    else:
        await message.answer("ℹ️ Контекст уже пуст.")

@dp.message(Command("reset"))
async def cmd_reset(message: Message):
    await cmd_clear(message)

@dp.message()
async def handle_message(message: Message):
    user_id = message.from_user.id
    user_text = message.text
    settings = context_manager.get_settings(user_id)
    
    context_manager.add_message(user_id, "user", user_text)
    
    # Формируем сообщения с учётом режима
    messages = [{"role": "system", "content": get_system_prompt(user_id)}]
    messages.extend(context_manager.get_context(user_id))
    
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    logger.info(f"💬 Пользователь {user_id}: {user_text[:100]}...")
    
    # Запрос к API с параметрами пользователя
    response = api_client.generate_response(
        messages,
        temperature=settings['temperature'],
        max_tokens=settings['max_tokens'],
        model=DEFAULT_MODEL
    )
    
    if response["success"]:
        answer = response["content"]
        context_manager.add_message(user_id, "assistant", answer)
        
        usage = response.get("usage", {})
        if usage:
            tokens_in = usage.get("prompt_tokens", 0)
            tokens_out = usage.get("completion_tokens", 0)
            total = tokens_in + tokens_out
            model_used = response.get("model_used", DEFAULT_MODEL)
            update_user_stats(user_id, tokens_in, tokens_out, model_used)
            
            # 📊 Вывод токенов в КОНСОЛЬ (требование задания)
            print(f"\n[📊 TOKENS] User {user_id} | In: {tokens_in} | Out: {tokens_out} | Total: {total} | Temp: {settings['temperature']}")
            logger.info(f"📈 Токены: вх={tokens_in}, вых={tokens_out}, всего={total}")
        
        await message.answer(answer)
        logger.info(f"✅ Ответ отправлен пользователю {user_id}")
        
    else:
        error_msg = response.get("error", "Неизвестная ошибка")
        logger.error(f"❌ Ошибка для пользователя {user_id}: {error_msg}")
        await message.answer("😔 Ошибка AI. Попробуйте позже или /clear.")

# =============================================================================
# 💻 Консольный интерфейс (параллельно с Telegram)
# =============================================================================
async def run_console_mode():
    print("\n" + "="*60)
    print(" КОНСОЛЬНЫЙ РЕЖИМ АКТИВЕН")
    print("Вводите запросы. Для выхода введите: exit или выход")
    print("="*60 + "\n")

    console_history = []
    system_prompt = "Ты — полезный ассистент. Отвечай кратко и по делу."

    while True:
        try:
            # Неблокирующий ввод (не останавливает Telegram-бота)
            user_input = await asyncio.to_thread(input, "👤 Вы > ").strip()
            
            if not user_input:
                continue
            if user_input.lower() in ['exit', 'выход', 'quit', 'q']:
                print("👋 Консольный режим завершён. Telegram-бот продолжает работать.")
                break

            # Формируем сообщения с историей
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(console_history)
            messages.append({"role": "user", "content": user_input})

            print("⏳ Генерация ответа...")
            response = api_client.generate_response(messages)

            if response["success"]:
                answer = response["content"]
                print(f"\n🤖 AI:\n{answer}\n")
                
                # Сохраняем в историю
                console_history.append({"role": "user", "content": user_input})
                console_history.append({"role": "assistant", "content": answer})

                # Вывод токенов
                usage = response.get("usage", {})
                if usage:
                    t_in = usage.get("prompt_tokens", 0)
                    t_out = usage.get("completion_tokens", 0)
                    print(f"[📊 TOKENS] Console | Вх: {t_in} | Вых: {t_out} | Всего: {t_in + t_out}\n")
            else:
                print(f"❌ Ошибка: {response.get('error')}\n")

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"⚠️ Ошибка в консоли: {e}\n")

# =============================================================================
# 🚀 Точка входа
# =============================================================================

async def main():
    logger.info("🚀 Запуск Telegram-бота...")
    logger.info(f"🔑 Активный провайдер: {api_client.get_provider_info()['provider'].upper()}")
    os.makedirs("logs", exist_ok=True)
    
    session = create_bot_session()
    bot = Bot(token=BOT_TOKEN, session=session, default=DefaultBotProperties(parse_mode="HTML"))
    
    logger.info("✅ Бот запущен. Ожидание сообщений...")
    print("\n" + "="*50)
    print("🤖 TELEGRAM BOT READY")
    print("="*50 + "\n")
    
    # Запускаем polling (единственный раз!)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Остановлено пользователем.")
    except Exception as e:
        logger.exception(f"💥 Критическая ошибка: {e}")