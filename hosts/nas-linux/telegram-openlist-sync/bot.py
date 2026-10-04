"""Standard-library-only Telegram bot; all configuration is read at runtime."""

import json
import logging
import math
import os
import signal
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from offline import OfflineDownloads, extract_links

LOG = logging.getLogger("telegram-openlist-sync")


class RequestError(Exception):
    """Safe diagnostic that never includes URLs, credentials or response bodies."""


def http_json(url, data=None, headers=None, timeout=30):
    headers = dict(headers or {})
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        raise RequestError(f"HTTP {exc.code}") from None
    except (OSError, ValueError, urllib.error.URLError):
        raise RequestError("网络连接失败、请求超时或响应不是有效 JSON") from None
    if not isinstance(result, dict):
        raise RequestError("API 响应格式错误")
    return result


class Bot:
    request_error = RequestError

    def __init__(self, env):
        for name in (
            "TELEGRAM_BOT_TOKEN",
            "ALLOWED_USER_ID",
            "OPENLIST_URL",
            "OPENLIST_TOKEN",
        ):
            if not env.get(name, "").strip():
                raise ValueError(f"缺少环境变量 {name}")
        try:
            self.user_id = int(env["ALLOWED_USER_ID"])
        except ValueError:
            raise ValueError("ALLOWED_USER_ID 必须是正整数") from None
        if self.user_id <= 0:
            raise ValueError("ALLOWED_USER_ID 必须是正整数")
        self.tg = f"https://api.telegram.org/bot{env['TELEGRAM_BOT_TOKEN']}"
        self.initialize_openlist(env)
        self.offset = (
            int(self.offset_file.read_text()) if self.offset_file.exists() else None
        )

    def initialize_openlist(self, env):
        """Initialize the shared OpenList configuration."""
        for name in ("OPENLIST_URL", "OPENLIST_TOKEN"):
            if not env.get(name, "").strip():
                raise ValueError(f"缺少环境变量 {name}")
        self.url = env["OPENLIST_URL"].rstrip("/")
        parsed = urllib.parse.urlsplit(self.url)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("OPENLIST_URL 必须是无凭据、查询参数和片段的 HTTP(S) 地址")
        self.headers = {"Authorization": env["OPENLIST_TOKEN"]}
        self.path = env.get("SCAN_PATH", "/STRM")
        if not self.path.startswith("/"):
            raise ValueError("SCAN_PATH 必须以 / 开头")
        self.limit = self.number(env, "SCAN_LIMIT", 0, zero=True)
        self.interval = self.number(env, "SCAN_POLL_INTERVAL", 2)
        self.scan_timeout = self.number(env, "SCAN_TIMEOUT", 3600)
        self.stop = threading.Event()
        self.scan_lock = threading.Lock()
        self.offset_file = Path(env.get("STATE_DIRECTORY", ".")) / "offset"
        self.offline = OfflineDownloads(self, env)

    @staticmethod
    def number(env, name, default, zero=False):
        try:
            value = float(env.get(name, default))
        except ValueError:
            raise ValueError(f"{name} 必须是有效数值") from None
        if not math.isfinite(value) or value < 0 or (not zero and value == 0):
            raise ValueError(f"{name} 超出允许范围")
        return value

    def telegram(self, method, data, timeout=30):
        result = http_json(f"{self.tg}/{method}", data, timeout=timeout)
        if result.get("ok") is not True:
            raise RequestError("Telegram API 返回失败")
        return result.get("result")

    def send(self, chat_id, text, reply_markup=None):
        data = {"chat_id": chat_id, "text": text[:4000]}
        if reply_markup is not None:
            data["reply_markup"] = reply_markup
        try:
            self.telegram("sendMessage", data)
        except RequestError as exc:
            LOG.warning("消息发送失败：%s", exc)

    def api(self, endpoint, data=None):
        result = http_json(f"{self.url}{endpoint}", data, self.headers)
        if result.get("code") != 200:
            raise RequestError(
                "OpenList API 返回失败，请检查 Token 权限、目录和下载工具配置"
            )
        return result.get("data")

    def openlist(self, endpoint, data=None):
        return self.api(f"/api/admin/scan/{endpoint}", data)

    def register_commands(self):
        self.telegram("setMyCommands", {"commands": [
            {"command": "download", "description": "添加离线下载，点击后发送链接"},
            {"command": "downloads", "description": "查看离线下载配置和任务数量"},
            {"command": "refresh", "description": "刷新下载目录，更新文件列表"},
            {"command": "sync", "description": "开始 OpenList 扫描同步"},
            {"command": "status", "description": "查看扫描同步状态"},
            {"command": "help", "description": "查看命令与链接使用说明"},
            {"command": "start", "description": "开始使用，查看操作指引"},
        ], "scope": {"type": "all_private_chats"}})
        self.telegram("setChatMenuButton", {"menu_button": {"type": "commands"}})
        LOG.info("Telegram 命令菜单已注册")

    def progress(self):
        data = self.openlist("progress")
        if not isinstance(data, dict) or not isinstance(data.get("is_done"), bool):
            raise RequestError("OpenList 扫描状态缺少有效 is_done 字段")
        return data

    def sync(self, chat_id):
        try:
            if not self.progress()["is_done"]:
                self.send(chat_id, "OpenList 已有扫描任务，请使用 /status 查看。")
                return
            self.openlist("start", {"path": self.path, "limit": self.limit})
            self.send(chat_id, f"开始同步：{self.path}")
            deadline = time.monotonic() + self.scan_timeout
            while not self.stop.wait(self.interval):
                if time.monotonic() >= deadline:
                    self.send(
                        chat_id,
                        "等待扫描完成超时；OpenList 任务可能仍在运行，请使用 /status 查看。",
                    )
                    return
                data = self.progress()
                if data["is_done"]:
                    self.send(
                        chat_id, f"同步完成。\n扫描对象：{data.get('obj_count', 0)}"
                    )
                    return
        except RequestError as exc:
            self.send(
                chat_id, f"同步请求失败：{exc}。任务可能仍在运行，请使用 /status 查看。"
            )
        finally:
            self.scan_lock.release()

    def handle(self, update):
        message = update.get("message") or {}
        chat = message.get("chat") or {}
        # Only private messages from the allowlisted account may trigger actions.
        if (message.get("from") or {}).get("id") != self.user_id or chat.get(
            "type"
        ) != "private":
            return
        chat_id = chat.get("id")
        text = (message.get("text") or message.get("caption") or "").strip()
        self.handle_text(chat_id, text)

    def handle_text(self, chat_id, text):
        """Dispatch commands after the transport has authenticated the sender."""
        parts = text.split(maxsplit=1)
        command = parts[0].lower() if parts else ""
        if command in ("download", "/download") and len(parts) == 1:
            if not self.offline.path:
                self.send(chat_id, "请先在环境文件中设置 OFFLINE_DOWNLOAD_PATH。")
                return
            self.send(
                chat_id,
                f"请回复要下载的链接，目标目录：{self.offline.path}\n"
                "支持磁力、ed2k 和普通 HTTP(S) 直链，每行一条，最多 20 条。\n"
                "暂不支持 http://115cdn/ 链接。",
                reply_markup={
                    "force_reply": True,
                    "input_field_placeholder": "粘贴下载链接，每行一条",
                    "selective": True,
                },
            )
        elif command in ("refresh", "/refresh"):
            self.offline.manual_refresh(chat_id)
        elif command in ("sync", "/sync"):
            if not self.scan_lock.acquire(blocking=False):
                self.send(chat_id, "正在同步，请使用 /status 查看。")
                return
            threading.Thread(target=self.sync, args=(chat_id,), daemon=True).start()
        elif command in ("status", "/status"):
            try:
                data = self.progress()
                self.send(
                    chat_id,
                    f"同步状态：\n已扫描对象：{data.get('obj_count', 0)}\n是否完成：{data['is_done']}",
                )
            except RequestError as exc:
                self.send(chat_id, f"查询失败：{exc}")
        elif command in ("help", "/help", "/start"):
            self.send(chat_id, "可用命令：\n/download 链接 - 添加离线下载\n/downloads - 下载配置与任务数量\n/refresh - 刷新下载目录\n/sync - 开始同步\n/status - 查看扫描状态\n/help - 帮助\n\n也可直接发送磁力、ed2k、HTTP(S) 下载直链，每行一条，最多 20 条。暂不支持 http://115cdn/ 链接。链接由 OpenList 下载工具处理；网页分享链接不保证支持。")
        elif command in ("downloads", "/downloads"):
            self.send(chat_id, self.offline.status())
        else:
            try:
                links = extract_links(text)
            except ValueError as exc:
                self.send(chat_id, str(exc))
                return
            if links:
                self.offline.submit(chat_id, links)
            else:
                self.send(chat_id, "请发送完整下载链接，或用 /help 查看命令。")

    def run(self):
        delay = 1
        menu_retry_at = 0
        threading.Thread(target=self.offline.run, daemon=True).start()
        LOG.info("Telegram sync bot started")
        while not self.stop.is_set():
            try:
                if time.monotonic() >= menu_retry_at:
                    try:
                        self.register_commands()
                        menu_retry_at = float("inf")
                    except RequestError as exc:
                        LOG.warning("命令菜单注册失败：%s", exc)
                        menu_retry_at = time.monotonic() + 300
                params = {"timeout": 30, "allowed_updates": ["message"]}
                if self.offset is not None:
                    params["offset"] = self.offset
                updates = self.telegram("getUpdates", params, timeout=40)
                if not isinstance(updates, list):
                    raise RequestError("Telegram 更新格式错误")
                for update in updates:
                    if self.stop.is_set():
                        break
                    # Persist before dispatch: do not replay scan commands after restart.
                    # A crash in this window can lose a command; the user can resend it.
                    self.offset = update["update_id"] + 1
                    temporary = self.offset_file.with_suffix(".tmp")
                    temporary.write_text(str(self.offset))
                    temporary.replace(self.offset_file)
                    self.handle(update)
                delay = 1
            except RequestError as exc:
                LOG.warning("Telegram polling：%s", exc)
                self.stop.wait(delay)
                delay = min(delay * 2, 60)


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        bot = Bot(os.environ)
    except ValueError as exc:
        LOG.error("配置错误：%s", exc)
        return 1
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: bot.stop.set())
    bot.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
