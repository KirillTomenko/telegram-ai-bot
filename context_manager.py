import logging
from typing import Dict, List, Optional
from config import MAX_CONTEXT_MESSAGES, logger

class ContextManager:
    """Управляет контекстом диалога для каждого пользователя в памяти."""
    
    def __init__(self):
        # {user_id: [{"role": "...", "content": "..."}, ...]}
        self._contexts: Dict[int, List[dict]] = {}
        logger.info("✅ ContextManager инициализирован")
    
    def get_context(self, user_id: int) -> List[dict]:
        """Возвращает контекст пользователя (копия, чтобы не мутировать извне)."""
        return self._contexts.get(user_id, []).copy()
    
    def add_message(self, user_id: int, role: str, content: str):
        """Добавляет сообщение в контекст пользователя."""
        if user_id not in self._contexts:
            self._contexts[user_id] = []
        
        self._contexts[user_id].append({"role": role, "content": content})
        
        # Ограничиваем контекст последними N сообщениями
        if len(self._contexts[user_id]) > MAX_CONTEXT_MESSAGES * 2:  # *2 т.к. user+assistant
            self._contexts[user_id] = self._contexts[user_id][-MAX_CONTEXT_MESSAGES * 2:]
        
        logger.debug(f"📝 Контекст пользователя {user_id}: {len(self._contexts[user_id])} сообщений")
    
    def clear_context(self, user_id: int) -> bool:
        """Очищает контекст пользователя."""
        if user_id in self._contexts:
            del self._contexts[user_id]
            logger.info(f"🧹 Контекст пользователя {user_id} очищен")
            return True
        return False
    
    def get_context_stats(self, user_id: int) -> dict:
        """Возвращает статистику по контексту."""
        messages = self._contexts.get(user_id, [])
        return {
            "messages_count": len(messages),
            "user_messages": sum(1 for m in messages if m["role"] == "user"),
            "assistant_messages": sum(1 for m in messages if m["role"] == "assistant")
        }