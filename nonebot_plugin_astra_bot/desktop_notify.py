"""跨平台桌面通知：通过系统原生通知渠道提醒用户"""

from __future__ import annotations

import asyncio
import platform

from nonebot_plugin_astra_bot.logger import logger


async def send_desktop_notification(title: str, message: str) -> None:
    system = platform.system()
    try:
        if system == "Linux":
            await _notify_linux(title, message)
        elif system == "Darwin":
            await _notify_macos(title, message)
        elif system == "Windows":
            await _notify_windows(title, message)
        else:
            logger.warning(f"Unsupported platform for desktop notification: {system}")
    except Exception as e:
        logger.error(f"Failed to send desktop notification: {e}")


async def _notify_linux(title: str, message: str) -> None:
    proc = await asyncio.create_subprocess_exec(
        "notify-send", title, message, "--urgency=critical", "--expire-time=10000",
        stdout=asyncio.DEVNULL, stderr=asyncio.DEVNULL,
    )
    await proc.wait()


async def _notify_macos(title: str, message: str) -> None:
    script = f'display notification "{message}" with title "{title}"'
    proc = await asyncio.create_subprocess_exec(
        "osascript", "-e", script,
        stdout=asyncio.DEVNULL, stderr=asyncio.DEVNULL,
    )
    await proc.wait()


async def _notify_windows(title: str, message: str) -> None:
    ps_script = (
        f"[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null;"
        f"[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom, ContentType = WindowsRuntime] > $null;"
        f"$template = @'\n<toast><visual><binding template=\"ToastText02\"><text id=\"1\">{title}</text><text id=\"2\">{message}</text></binding></visual></toast>\n'@;"
        f"$xml = New-Object Windows.Data.Xml.Dom.XmlDocument; $xml.LoadXml($template);"
        f"$toast = [Windows.UI.Notifications.ToastNotification]::new($xml);"
        f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('AstraBot').Show($toast)"
    )
    proc = await asyncio.create_subprocess_exec(
        "powershell", "-Command", ps_script,
        stdout=asyncio.DEVNULL, stderr=asyncio.DEVNULL,
    )
    await proc.wait()
