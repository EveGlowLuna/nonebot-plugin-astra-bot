"""插件加载器：从 plugins 目录动态加载插件，支持插件链式执行和 prompt 注入"""

from __future__ import annotations

import importlib
import importlib.util
import sys
import tomllib
from pathlib import Path
from types import ModuleType
from typing import Any

from nonebot import require
require("nonebot_plugin_localstore")
import nonebot_plugin_localstore as store

from nonebot_plugin_astra_bot.logger import logger

PLUGINS_DIR = Path(__file__).resolve().parent / "plugins"
USER_PLUGINS_DIR = store.get_plugin_data_dir() / "plugins"

DEFAULT_SETTINGS = {
    "must": False,
    "function_format": "string",
    "function_desc": "",
    "re_exec": False,
}


class PluginInfo:
    """插件信息：名称、模块对象、settings.toml 中的配置"""
    def __init__(self, name: str, module: ModuleType, settings: dict):
        self.name = name
        self.module = module
        self.settings = {**DEFAULT_SETTINGS, **settings}


def _load_single_plugin(entry: Path, *, is_user: bool) -> PluginInfo | None:
    """从目录加载单个插件，返回 PluginInfo 或 None"""
    name = entry.name
    try:
        if is_user:
            init_path = entry / "__init__.py"
            if not init_path.exists():
                logger.warning(f"User plugin {name} missing __init__.py, skipping")
                return None
            spec = importlib.util.spec_from_file_location(
                f"astra_user_plugin_{name}", init_path
            )
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot load spec for {name}")
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
        else:
            module = importlib.import_module(
                f"nonebot_plugin_astra_bot.plugins.{name}.__init__"
            )

        if not hasattr(module, "run") or not callable(module.run):
            raise ImportError(f"Plugin {name} missing run() function")

        settings_path = entry / "settings.toml"
        settings = {}
        if settings_path.exists():
            with open(settings_path, "rb") as f:
                settings = tomllib.load(f)

        logger.info(f"Loaded plugin: {name}" + (" (user)" if is_user else ""))
        return PluginInfo(name=name, module=module, settings=settings)
    except Exception as e:
        logger.error(f"Failed to load plugin {name}: {e}")
        return None


class PluginLoader:
    plugins: list[PluginInfo] = []
    _loaded = False

    @classmethod
    def load_all(cls):
        """扫描内置和用户 plugins 目录，加载每个含 run() 函数的子目录为插件"""
        if cls._loaded:
            return
        cls.plugins.clear()

        loaded_names: set[str] = set()

        # 1. 加载内置插件（包内 plugins/）
        if PLUGINS_DIR.exists():
            for entry in sorted(
                (d for d in PLUGINS_DIR.iterdir()
                 if d.is_dir() and not d.name.startswith("_") and d.name != "example_plug"),
                key=lambda d: d.name,
            ):
                plugin = _load_single_plugin(entry, is_user=False)
                if plugin:
                    cls.plugins.append(plugin)
                    loaded_names.add(plugin.name)
        else:
            logger.warning(f"Built-in plugins directory not found: {PLUGINS_DIR}")

        # 2. 加载用户插件（localstore data/plugins/），同名覆盖内置
        if USER_PLUGINS_DIR.exists():
            for entry in sorted(
                (d for d in USER_PLUGINS_DIR.iterdir() if d.is_dir() and not d.name.startswith("_")),
                key=lambda d: d.name,
            ):
                if entry.name in loaded_names:
                    # 替换同名内置插件
                    cls.plugins[:] = [p for p in cls.plugins if p.name != entry.name]
                    loaded_names.discard(entry.name)
                plugin = _load_single_plugin(entry, is_user=True)
                if plugin:
                    cls.plugins.append(plugin)
                    loaded_names.add(plugin.name)

        cls._loaded = True

    @classmethod
    def get_plugin_section(cls) -> str:
        """生成注入到 prompt 中的工具说明文本，告知 AI 可用的插件字段"""
        if not cls.plugins:
            return ""

        required = []
        optional = []
        for p in cls.plugins:
            fmt = p.settings.get("function_format", "string")
            desc = p.settings.get("function_desc", "")
            if not desc:
                continue
            entry = f"{p.name}({fmt})：{desc}"
            if p.settings.get("must", False):
                required.append(entry)
            else:
                optional.append(entry)

        lines = ["【可用工具】（需要时直接在回复 JSON 中添加对应字段即可调用）："]
        if required:
            lines.append("  必填字段（必须在 JSON 中包含）：")
            for r in required:
                lines.append(f"    {r}")
        if optional:
            lines.append("  可选工具（需要时使用）：")
            for o in optional:
                lines.append(f"    {o}")
        lines.append("  示例：{\"reply\": \"...\", \"docker_exec\": \"ls -la\"}")
        return "\n".join(lines)

    @classmethod
    def execute_chain(cls, bot, event, history: list[dict], image_desc: str, config: Any) -> tuple[dict | None, str]:
        """依次执行所有插件的 run()，合并结果；支持 block 终止和 re_exec 追加"""
        merged: dict | None = None
        re_exec_parts: list[str] = []

        for p in cls.plugins:
            try:
                result = p.module.run(
                    bot=bot,
                    event=event,
                    history=history,
                    image_desc=image_desc,
                    config=config,
                    plugin_config=p.settings,
                )
                if result is None:
                    continue
                if merged is None:
                    merged = {}
                merged.update(result)
                # block=True 终止后续插件执行，但已合并的结果仍会生效
                if result.get("block"):
                    break
                # re_exec 插件：将 append_prompt 收集起来，后续注入 prompt 让 AI 重新生成
                if p.settings.get("re_exec", False):
                    if result.get("append_prompt"):
                        re_exec_parts.append(result["append_prompt"])
            except Exception as e:
                logger.error(f"Plugin {p.name} run() error: {e}")

        re_exec_append = "\n\n".join(re_exec_parts) if re_exec_parts else ""
        return merged, re_exec_append

    @classmethod
    def has_re_exec_plugins(cls) -> bool:
        return any(p.settings.get("re_exec", False) for p in cls.plugins)
