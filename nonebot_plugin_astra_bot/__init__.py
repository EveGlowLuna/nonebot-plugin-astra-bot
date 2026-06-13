"""AstraBot 聊天服务入口：注册群消息和撤回事件处理器，加载插件"""

from __future__ import annotations

from nonebot import on_message, on_notice, require
require("nonebot_plugin_localstore")

from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, NoticeEvent
from nonebot.plugin import PluginMetadata

from nonebot_plugin_astra_bot.config import Config
from nonebot_plugin_astra_bot.desktop_notify import send_desktop_notification
from nonebot_plugin_astra_bot.history_manager import delete_by_message_id
from nonebot_plugin_astra_bot.message_handler import handle_group_message
from nonebot_plugin_astra_bot.plugin_loader import PluginLoader
from nonebot_plugin_astra_bot.reply_controller import ReplyController
from nonebot_plugin_astra_bot.logger import logger

__plugin_meta__ = PluginMetadata(
    name="nonebot_plugin_astra_bot",
    description="AI-powered QQ group chat bot with multi-LLM support, memory system, plugin mechanism, and web search",
    usage="配置 API Key 后部署到 QQ 群即可使用。支持 @触发和关键词触发。",
    type="application",
    homepage="https://github.com/EveGlowLuna/nonebot-plugin-astra-bot",
    supported_adapters={"~onebot.v11"},
    config=Config,
)

reply = on_message(priority=10)


@reply.handle()
async def handle(bot: Bot, event: GroupMessageEvent):
    await handle_group_message(bot, event)


notice_handler = on_notice()


@notice_handler.handle()
async def handle_notice(bot: Bot, event: NoticeEvent):
    data = event.model_dump()
    notice_type = data.get("notice_type")

    if notice_type == "group_recall":
        group_id = data.get("group_id")
        message_id = data.get("message_id")
        if not group_id or not message_id:
            return
        ReplyController.add_recalled(group_id, message_id)
        deleted = await delete_by_message_id(group_id, message_id)
        if deleted:
            logger.info(f"Removed recalled message {message_id} from history in group {group_id}")
        else:
            logger.trace(f"Recalled message {message_id} not found in history (group {group_id})")

    elif notice_type == "bot_offline":
        msg = data.get("message", "")
        tag = data.get("tag", "")
        logger.warning(f"Bot offline detected: tag={tag}, message={msg}")
        await send_desktop_notification("AstraBot 离线通知", "QQ凭证过期，请重新登录")


PluginLoader.load_all()
