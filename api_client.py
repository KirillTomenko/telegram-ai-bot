import os
import json
import time
import logging
import requests
from typing import Optional, Dict, List
from config import API_CONFIG, ACTIVE_PROVIDER, logger

class APIClient:
    """Унифицированный клиент для работы с разными AI-провайдерами."""
    
    def __init__(self, provider: str = None):
        self.provider = provider or ACTIVE_PROVIDER
        self.config = API_CONFIG[self.provider]
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.config['key']}",
            "Content-Type": "application/json"
        })
        logger.info(f"🔌 APIClient инициализирован для {self.provider.upper()}")
    
    def _make_request(self, messages: List[dict], temperature: float, 
                      max_tokens: int, model: str) -> Dict:
        """Внутренний метод отправки запроса."""
        url = self.config['base_url'] + self.config['endpoint']
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        # ProxyAPI/GenAPI могут требовать дополнительные параметры
        if self.provider in ['proxyapi', 'genapi']:
            payload["stream"] = False  # отключаем стриминг для простоты
        
        logger.info(f"📤 Запрос к {self.provider.upper()}: model={model}, temp={temperature}, tokens={max_tokens}")
        logger.debug(f"📦 Payload: {json.dumps(payload, ensure_ascii=False)[:500]}...")
        
        start_time = time.time()
        try:
            response = self.session.post(url, json=payload, timeout=60)
            elapsed = time.time() - start_time
            
            if response.status_code != 200:
                error_text = response.text[:300]
                logger.error(f"❌ Ошибка API ({response.status_code}): {error_text}")
                return {
                    "success": False,
                    "error": f"API Error {response.status_code}: {error_text}",
                    "usage": None
                }
            
            result = response.json()
            logger.info(f"✅ Ответ получен за {elapsed:.2f}с")
            
            # Извлекаем ответ и статистику использования
            choice = result.get("choices", [{}])[0]
            content = choice.get("message", {}).get("content", "")
            usage = result.get("usage", {})
            
            return {
                "success": True,
                "content": content,
                "usage": usage,
                "model_used": result.get("model", model),
                "request_id": result.get("id", "N/A")
            }
            
        except requests.exceptions.Timeout:
            logger.error("⏱ Таймаут запроса")
            return {"success": False, "error": "Таймаут соединения с API", "usage": None}
        except requests.exceptions.RequestException as e:
            logger.error(f"🌐 Ошибка сети: {e}")
            return {"success": False, "error": f"Сетевая ошибка: {e}", "usage": None}
        except json.JSONDecodeError as e:
            logger.error(f"🔤 Ошибка парсинга JSON: {e}")
            return {"success": False, "error": "Некорректный ответ от API", "usage": None}
    
    def generate_response(self, messages: List[dict], 
                          temperature: Optional[float] = None,
                          max_tokens: Optional[int] = None,
                          model: Optional[str] = None) -> Dict:
        """
        Публичный метод генерации ответа.
        
        Args:
            messages: Список сообщений в формате [{"role": "user", "content": "..."}]
            temperature: Температура генерации (0.0-2.0)
            max_tokens: Лимит токенов в ответе
            model: Название модели (переопределяет дефолтную)
        
        Returns:
            Dict с ключами: success, content/error, usage, model_used, request_id
        """
        from config import DEFAULT_TEMPERATURE, DEFAULT_MAX_TOKENS, DEFAULT_MODEL
        
        params = {
            "temperature": temperature if temperature is not None else DEFAULT_TEMPERATURE,
            "max_tokens": max_tokens if max_tokens is not None else DEFAULT_MAX_TOKENS,
            "model": model if model else DEFAULT_MODEL
        }
        
        logger.info(f"🎯 Генерация ответа: {params}")
        return self._make_request(messages, **params)
    
    def get_provider_info(self) -> dict:
        """Возвращает информацию о текущем провайдере."""
        return {
            "provider": self.provider,
            "base_url": self.config['base_url'],
            "key_preview": f"{self.config['key'][:8]}..." if self.config['key'] else "N/A"
        }