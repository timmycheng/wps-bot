# encoding:utf-8
"""
LLM Bot 模块
对接私有化LLM网关（OpenAI标准接口）
"""

import time
from typing import Dict, List, Optional

import openai

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
        self._setup_openai()
        logger.info("[LLMBot] Initialized")
    
    def _setup_openai(self):
        """配置OpenAI客户端"""
        # 设置API Key
        openai.api_key = self.config.get("llm_api_key", "")
        
        # 设置API Base（私有化网关地址）
        api_base = self.config.get("llm_api_base", "")
        if api_base:
            openai.api_base = api_base
            logger.info(f"[LLMBot] Using custom API base: {api_base}")
    
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
            
            # 调用LLM
            response = self._call_llm(session.get_messages())
            
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
        
        except Exception as e:
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
                logger.warning(f"[LLMBot] Retry {retry_count + 1} after {wait_time}s")
                time.sleep(wait_time)
                return self._call_llm_with_retry(messages, retry_count + 1)
            else:
                raise


# 全局Bot实例
_bot: Optional[LLMBot] = None


def get_bot() -> LLMBot:
    """获取全局Bot实例"""
    global _bot
    if _bot is None:
        _bot = LLMBot()
    return _bot
