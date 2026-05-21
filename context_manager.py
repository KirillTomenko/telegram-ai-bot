import logging
from typing import Dict, List, Optional
from config import MAX_CONTEXT_MESSAGES, USER_SETTINGS_DEFAULT, logger

class ContextManager:
    """Управляет контекстом и настройками для каждого пользователя."""
    
    def __init__(self):
        self._contexts: Dict[int, List[dict]] = {}
        self._settings: Dict[int, dict] = {}
        logger.info("✅ ContextManager инициализирован")
    
    def get_context(self, user_id: int) -> List[dict]:
        return self._contexts.get(user_id, []).copy()
    
    def add_message(self, user_id: int, role: str, content: str):
        if user_id not in self._contexts:
            self._contexts[user_id] = []
        self._contexts[user_id].append({"role": role, "content": content})
        if len(self._contexts[user_id]) > MAX_CONTEXT_MESSAGES * 2:
            self._contexts[user_id] = self._contexts[user_id][-MAX_CONTEXT_MESSAGES * 2:]
    
    def clear_context(self, user_id: int) -> bool:
        if user_id in self._contexts:
            del self._contexts[user_id]
            logger.info(f"🧹 Контекст пользователя {user_id} очищен")
            return True
        return False
    
    def get_settings(self, user_id: int) -> dict:
        if user_id not in self._settings:
            self._settings[user_id] = USER_SETTINGS_DEFAULT.copy()
        return self._settings[user_id].copy()
    
    def update_setting(self, user_id: int, key: str, value):
        if user_id not in self._settings:
            self._settings[user_id] = USER_SETTINGS_DEFAULT.copy()
        self._settings[user_id][key] = value
        logger.debug(f"⚙️ Настройка {user_id}.{key} = {value}")
    
    def get_context_stats(self, user_id: int) -> dict:
        messages = self._contexts.get(user_id, [])
        return {
            "messages_count": len(messages),
            "user_messages": sum(1 for m in messages if m["role"] == "user"),
            "assistant_messages": sum(1 for m in messages if m["role"] == "assistant")
        }