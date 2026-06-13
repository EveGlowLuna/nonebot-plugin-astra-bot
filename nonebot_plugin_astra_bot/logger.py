"""日志管理：使用 NoneBot 官方 loguru logger，统一日志格式，同时输出到文件"""

from __future__ import annotations

from datetime import datetime

from nonebot import require
require("nonebot_plugin_localstore")
import nonebot_plugin_localstore as store

from nonebot import logger

LOG_DIR = store.get_plugin_cache_dir() / "logs"


def _setup_file_sink():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = LOG_DIR / f"astrabot_{timestamp}.log"
    logger.add(
        file_path,
        encoding="utf-8",
        rotation="10 MB",
        retention="30 days",
        level="TRACE",
    )


_setup_file_sink()
