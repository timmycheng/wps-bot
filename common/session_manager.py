# encoding:utf-8
"""
会话管理模块
管理用户与机器人的对话上下文
"""

import time
from typing import Dict, List, Optional
from common.logger import logger


class Session:
    """单个会话"""
    
    def __init__(self, session_id: str, max_tokens: int = 4000):
        self.session_id = session_id
        self.max_tokens = max_tokens
        self.messages: List[Dict] = []  # 消息历史
        self.last_active = time.time()  # 最后活跃时间
    
    def add_message(self, role: str, content: str):
        """添加消息到会话"""
        self.messages.append({
            "role": role,
            "content": content,
            "timestamp": time.time()
        })
        self.last_active = time.time()
        
        # 简单控制上下文长度（可根据token计算优化）
        self._trim_messages()
    
    def _trim_messages(self):
        """修剪消息历史，控制长度"""
        # 保留最近20条消息
        if len(self.messages) > 20:
            # 保留system消息和最近的对话
            system_msgs = [m for m in self.messages if m.get("role") == "system"]
            other_msgs = [m for m in self.messages if m.get("role") != "system"]
            self.messages = system_msgs + other_msgs[-20:]
    
    def get_messages(self) -> List[Dict]:
        """获取消息历史（用于LLM调用）"""
        return [{"role": m["role"], "content": m["content"]} for m in self.messages]
    
    def is_expired(self, expires_in_seconds: int) -> bool:
        """检查会话是否过期"""
        return time.time() - self.last_active > expires_in_seconds
    
    def clear(self):
        """清空会话"""
        self.messages = []
        self.last_active = time.time()


class SessionManager:
    """会话管理器"""
    
    def __init__(self, max_tokens: int = 4000, expires_in_seconds: int = 3600):
        self.sessions: Dict[str, Session] = {}
        self.max_tokens = max_tokens
        self.expires_in_seconds = expires_in_seconds
        logger.info("[SessionManager] Initialized")
    
    def get_session(self, session_id: str) -> Session:
        """获取或创建会话"""
        self._clean_expired_sessions()
        
        if session_id not in self.sessions:
            logger.debug(f"[SessionManager] Creating new session: {session_id}")
            self.sessions[session_id] = Session(session_id, self.max_tokens)
        
        return self.sessions[session_id]
    
    def clear_session(self, session_id: str):
        """清空指定会话"""
        if session_id in self.sessions:
            self.sessions[session_id].clear()
            logger.info(f"[SessionManager] Session cleared: {session_id}")
    
    def clear_all_sessions(self):
        """清空所有会话"""
        self.sessions.clear()
        logger.info("[SessionManager] All sessions cleared")
    
    def _clean_expired_sessions(self):
        """清理过期会话"""
        expired_sessions = [
            sid for sid, session in self.sessions.items()
            if session.is_expired(self.expires_in_seconds)
        ]
        for sid in expired_sessions:
            del self.sessions[sid]
            logger.debug(f"[SessionManager] Expired session removed: {sid}")


# 全局会话管理器实例
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """获取全局会话管理器"""
    global _session_manager
    if _session_manager is None:
        from config import get_config
        conf = get_config()
        _session_manager = SessionManager(
            max_tokens=conf.get("conversation_max_tokens", 4000),
            expires_in_seconds=conf.get("expires_in_seconds", 3600)
        )
    return _session_manager
