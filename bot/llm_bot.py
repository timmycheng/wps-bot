# encoding:utf-8
"""
LLM Bot 模块
对接私有化LLM网关（OpenAI标准接口）
"""

import time
from typing import Dict, List, Optional

import openai
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from common.logger import logger
from common.session_manager import get_session_manager
from config import get_config


class LLMBot:
    """
    LLM机器人
    支持OpenAI标准接口的私有化LLM网关
    """
    
    def __init__(self):
        self.config = get_config()
        self._session: Optional[requests.Session] = None
        self._setup_openai()
        logger.info("[LLMBot] Initialized")
    
    def _get_session(self) -> requests.Session:
        """获取或创建带连接池的 Session"""
        if self._session is None:
            self._session = requests.Session()
            
            # 配置重试策略：连接错误时自动重试
            retry_strategy = Retry(
                total=3,
                backoff_factor=0.5,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]
            )
            
            # 配置连接池：保持连接活跃，防止被网关切断
            adapter = HTTPAdapter(
                pool_connections=10,
                pool_maxsize=20,
                max_retries=retry_strategy,
                pool_block=False
            )
            
            self._session.mount("http://", adapter)
            self._session.mount("https://", adapter)
            
            # 设置 keep-alive header
            self._session.headers.update({
                "Connection": "keep-alive",
                "Keep-Alive": "timeout=60, max=1000"
            })
            
            # 将 session 设置给 openai
            openai.requestssession = self._session
            
        return self._session
    
    def _setup_openai(self):
        """配置OpenAI客户端"""
        # 设置API Key
        openai.api_key = self.config.get("llm_api_key", "")
        
        # 设置API Base（私有化网关地址）
        api_base = self.config.get("llm_api_base", "")
        if api_base:
            openai.api_base = api_base
            logger.info(f"[LLMBot] Using custom API base: {api_base}")
        
        # 初始化 session（连接池）
        self._get_session()
    
    def chat(self, query: str, session_id: str, context: Optional[Dict] = None) -> str:
        """
        对话
        
        :param query: 用户输入
        :param session_id: 会话ID
        :param context: 额外上下文
        :return: 机器人回复
        """
        try:
            # 处理特殊命令
            reply = self._handle_command(query, session_id)
            if reply:
                return reply
            
            # 获取会话并添加用户消息
            session_manager = get_session_manager()
            session = session_manager.get_session(session_id)
            
            # 如果是新会话，添加系统提示
            if not session.messages:
                character_desc = self.config.get("character_desc", "")
                if character_desc:
                    session.add_message("system", character_desc)
            
            # 添加用户消息
            session.add_message("user", query)
            
            # 调用LLM（带重试机制）
            response = self._call_llm_with_retry(session.get_messages())
            
            # 添加助手回复到会话
            session.add_message("assistant", response)
            
            return response
            
        except Exception as e:
            logger.error(f"[LLMBot] Chat error: {e}")
            return f"抱歉，我遇到了一些问题：{str(e)}"
    
    def _handle_command(self, query: str, session_id: str) -> Optional[str]:
        """
        处理内置命令
        
        :param query: 用户输入
        :param session_id: 会话ID
        :return: 如果是命令返回回复，否则返回None
        """
        query = query.strip()
        
        # 清除记忆命令
        clear_commands = ["#清除记忆", "#清空", "#reset", "/reset", "/clear"]
        if query in clear_commands:
            session_manager = get_session_manager()
            session_manager.clear_session(session_id)
            return "🧹 会话记忆已清除，让我们开始新的对话吧！"
        
        # 帮助命令
        help_commands = ["#帮助", "#help", "/help"]
        if query in help_commands:
            return self._get_help_text()
        
        return None
    
    def _get_help_text(self) -> str:
        """获取帮助文本"""
        return """🤖 **WPS智能助手使用指南**

**基本功能：**
• 直接发送消息与我对话
• 我可以回答问题、生成内容、辅助办公

**常用命令：**
• `#帮助` / `#help` - 显示帮助信息
• `#清除记忆` / `#reset` - 清空当前会话记忆

**提示：**
• 在群聊中@我即可触发对话
• 私聊可直接发送消息
• 我会记住对话上下文，方便连续交流"""
    
    def _call_llm(self, messages: List[Dict]) -> str:
        """
        调用LLM API
        
        :param messages: 消息列表
        :return: LLM回复
        """
        try:
            model = self.config.get("llm_model", "gpt-3.5-turbo")
            temperature = self.config.get("temperature", 0.7)
            max_tokens = self.config.get("max_tokens", 2048)
            request_timeout = self.config.get("request_timeout", 120)
            
            logger.debug(f"[LLMBot] Calling LLM with {len(messages)} messages")
            
            # 确保使用带连接池的 session
            self._get_session()
            
            response = openai.ChatCompletion.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=self.config.get("top_p", 1.0),
                frequency_penalty=self.config.get("frequency_penalty", 0.0),
                presence_penalty=self.config.get("presence_penalty", 0.0),
                request_timeout=request_timeout
            )
            
            content = response.choices[0].message.content
            usage = response.get("usage", {})
            
            logger.info(
                f"[LLMBot] LLM response received, "
                f"tokens: prompt={usage.get('prompt_tokens', 0)}, "
                f"completion={usage.get('completion_tokens', 0)}"
            )
            
            return content.strip()
            
        except openai.error.RateLimitError as e:
            logger.error(f"[LLMBot] Rate limit error: {e}")
            return "⚠️ 请求过于频繁，请稍后再试"
        
        except openai.error.Timeout as e:
            logger.error(f"[LLMBot] Timeout error: {e}")
            return "⏱️ 请求超时，请稍后再试"
        
        except openai.error.APIError as e:
            logger.error(f"[LLMBot] API error: {e}")
            return f"🔌 API错误：{str(e)}"
        
        except (ConnectionError, requests.exceptions.ConnectionError) as e:
            # 捕获连接重置错误，交由上层重试
            logger.warning(f"[LLMBot] Connection error (will retry): {e}")
            raise
        
        except Exception as e:
            error_msg = str(e).lower()
            # 检查是否是连接重置相关错误
            if any(kw in error_msg for kw in ["connection", "reset", "aborted", "peer", "broken pipe"]):
                logger.warning(f"[LLMBot] Connection reset detected (will retry): {e}")
                raise ConnectionError(f"Connection reset: {e}")
            logger.error(f"[LLMBot] LLM call failed: {e}")
            raise
    
    def _call_llm_with_retry(self, messages: List[Dict], retry_count: int = 0) -> str:
        """
        带重试的LLM调用
        
        :param messages: 消息列表
        :param retry_count: 当前重试次数
        :return: LLM回复
        """
        max_retries = 2
        
        try:
            return self._call_llm(messages)
        except Exception as e:
            if retry_count < max_retries:
                wait_time = 3 * (retry_count + 1)
                error_type = type(e).__name__
                logger.warning(f"[LLMBot] {error_type} - Retry {retry_count + 1}/{max_retries} after {wait_time}s: {e}")
                time.sleep(wait_time)
                
                # 如果是连接错误，重置 session 以创建新连接
                if isinstance(e, (ConnectionError, requests.exceptions.ConnectionError)) or \
                   any(kw in str(e).lower() for kw in ["connection", "reset", "aborted"]):
                    logger.info("[LLMBot] Resetting connection pool for retry")
                    self._reset_session()
                
                return self._call_llm_with_retry(messages, retry_count + 1)
            else:
                raise
    
    def _reset_session(self):
        """重置连接池，用于连接错误后重建连接"""
        if self._session:
            try:
                self._session.close()
            except Exception:
                pass
        self._session = None
        openai.requestssession = None
        # 重新初始化
        self._get_session()


# 全局Bot实例
_bot: Optional[LLMBot] = None


def get_bot() -> LLMBot:
    """获取全局Bot实例"""
    global _bot
    if _bot is None:
        _bot = LLMBot()
    return _bot
