import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import logger, DEFAULT_MODEL, DEFAULT_TEMPERATURE, DEFAULT_MAX_TOKENS
from api_client import APIClient

async def main():
    client = APIClient()
    print("\n💻 Консольный тестовый клиент")
    print("Команды: /temp <0.0-1.0>, /clear, /stats, exit")
    print(f"По умолчанию: temp={DEFAULT_TEMPERATURE}, model={DEFAULT_MODEL}\n")
    
    # Настройки сессии
    current_temp = DEFAULT_TEMPERATURE
    current_max_tokens = DEFAULT_MAX_TOKENS
    history = []
    system_prompt = "Ты — полезный ассистент. Отвечай кратко и по делу."
    
    # Статистика
    stats = {'requests': 0, 'tokens_in': 0, 'tokens_out': 0}
    
    while True:
        try:
            # Ввод в отдельном потоке
            user_input = await asyncio.get_event_loop().run_in_executor(
                None, lambda: input("👤 Вы > ").strip()
            )
            
            if not user_input:
                continue
            
            # === Обработка команд ===
            if user_input.lower() in ['exit', 'выход', 'quit', 'q', 'стоп']:
                print("👋 До свидания!")
                break
            
            if user_input.lower().startswith('/temp '):
                try:
                    new_temp = float(user_input.split()[1].replace(',', '.'))
                    if 0.0 <= new_temp <= 1.0:
                        current_temp = new_temp
                        print(f"✅ Температура: {current_temp}")
                    else:
                        print("❌ Температура должна быть от 0.0 до 1.0")
                except (IndexError, ValueError):
                    print("❌ Используйте: /temp 0.7")
                continue
            
            if user_input.lower() == '/clear':
                history = []
                print("✅ Контекст очищен")
                continue
            
            if user_input.lower() == '/stats':
                total = stats['tokens_in'] + stats['tokens_out']
                cost = total * 5 / 1_000_000  # ~$5/1M токенов
                print(f"📊 Статистика:\n"
                      f"  Запросов: {stats['requests']}\n"
                      f"  Токены: вх={stats['tokens_in']}, вых={stats['tokens_out']}, всего={total}\n"
                      f"  ~Стоимость: ${cost:.4f}\n"
                      f"  Temp: {current_temp}, Model: {DEFAULT_MODEL}")
                continue
            
            if user_input.lower().startswith('/model '):
                new_model = user_input.split(' ', 1)[1].strip()
                print(f"✅ Модель: {new_model}")
                # Можно добавить глобальную переменную, если нужно
                continue
            
            # === Формируем запрос ===
            messages = [{"role": "system", "content": system_prompt}]
            if history:
                messages.extend(history[-10:])  # последние 10 сообщений
            messages.append({"role": "user", "content": user_input})
            
            print("⏳ Генерация ответа...")
            
            # Запрос с текущими параметрами
            response = client.generate_response(
                messages,
                temperature=current_temp,
                max_tokens=current_max_tokens,
                model=DEFAULT_MODEL
            )
            
            if response["success"]:
                answer = response["content"]
                print(f"\n🤖 AI:\n{answer}\n")
                
                # Сохраняем в историю
                history.append({"role": "user", "content": user_input})
                history.append({"role": "assistant", "content": answer})
                
                # Обновляем статистику
                stats['requests'] += 1
                usage = response.get("usage", {})
                if usage:
                    t_in = usage.get("prompt_tokens", 0)
                    t_out = usage.get("completion_tokens", 0)
                    stats['tokens_in'] += t_in
                    stats['tokens_out'] += t_out
                    print(f"[📊 TOKENS] Вх: {t_in} | Вых: {t_out} | Всего: {t_in + t_out} | Temp: {current_temp}\n")
            else:
                print(f"❌ Ошибка: {response.get('error')}\n")
                
        except KeyboardInterrupt:
            print("\n👋 Прервано пользователем")
            break
        except Exception as e:
            print(f"⚠️ Ошибка: {e}\n")
            logger.exception("Console error")

if __name__ == "__main__":
    asyncio.run(main())