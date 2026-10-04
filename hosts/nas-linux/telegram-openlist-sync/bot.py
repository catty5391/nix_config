"""Standard-library-only Telegram bot; all configuration is read at runtime."""

import json
import logging
import math
import os
import posixpath
import queue
import secrets
import signal
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from offline import OfflineDownloads, extract_links, parse_refresh_indices
from ui import messages

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
        self.path = env.get("SCAN_PATH", "/strm")
        if not self.path.startswith("/"):
            raise ValueError("SCAN_PATH 必须以 / 开头")
        self.limit = self.number(env, "SCAN_LIMIT", 0, zero=True)
        self.interval = self.number(env, "SCAN_POLL_INTERVAL", 2)
        self.scan_timeout = self.number(env, "SCAN_TIMEOUT", 3600)
        self.stop = threading.Event()
        self.restart_requested = False
        self.reset_token = secrets.token_hex(8)
        self.commands = queue.Queue(maxsize=20)
        self.scan_lock = threading.Lock()
        self.offset_file = Path(env.get("STATE_DIRECTORY", ".")) / "offset"
        self.offline = OfflineDownloads(self, env)
        self.strm_choices = {}
        self.strm_choices_lock = threading.Lock()

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
        if self.stop.is_set():
            return
        parts = list(messages.chunks(text))
        for index, part in enumerate(parts):
            data = {"chat_id": chat_id, "text": part}
            if reply_markup is not None and index == len(parts) - 1:
                data["reply_markup"] = reply_markup
            try:
                self.telegram("sendMessage", data)
            except RequestError as exc:
                LOG.warning("消息发送失败：%s", exc)
                break

    def api(self, endpoint, data=None):
        if self.stop.is_set():
            raise RequestError("bot 正在重置或停止")
        api_path = endpoint.split("?", 1)[0]
        directory = data.get("path") if isinstance(data, dict) else None
        try:
            result = http_json(f"{self.url}{endpoint}", data, self.headers)
        except RequestError as exc:
            LOG.warning("OpenList 请求失败：endpoint=%s path=%r error=%s", api_path, directory, exc)
            raise
        if result.get("code") != 200:
            code = result.get("code")
            code = code if type(code) is int else "unknown"
            # Classify known errors without echoing response bodies or credentials.
            missing_storage = "storage not found" in str(result.get("message", "")).lower()
            reason = (
                "找不到对应存储，请检查 OpenList 挂载路径及大小写"
                if missing_storage else "请检查 Token 权限、目录和下载工具配置"
            )
            LOG.warning("OpenList API 失败：endpoint=%s path=%r code=%s reason=%s", api_path, directory, code, reason)
            raise RequestError(f"OpenList API 返回失败（{code}）：{reason}")
        return result.get("data")

    def openlist(self, endpoint, data=None):
        return self.api(f"/api/admin/scan/{endpoint}", data)

    def register_commands(self):
        self.telegram("setMyCommands", {"commands": [
            {"command": "download", "description": "添加离线下载，点击后发送链接"},
            {"command": "downloads", "description": "查看离线下载配置和任务数量"},
            {"command": "refresh", "description": "按序号刷新文件夹，每批最多 5 个"},
            {"command": "cancel_refresh", "description": "取消正在执行的目录刷新"},
            {"command": "strm", "description": "按修改时间选择 STRM 文件夹"},
            {"command": "sync", "description": "开始 OpenList 扫描同步"},
            {"command": "status", "description": "查看扫描同步状态"},
            {"command": "reset", "description": "重启 bot，恢复卡住的操作"},
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
                self.send(chat_id, messages.notice("正在同步", "OpenList 已有扫描任务，请使用 /status 查看。", "working"))
                return
            self.openlist("start", {"path": self.path, "limit": self.limit})
            self.send(chat_id, messages.scan_started(self.path))
            deadline = time.monotonic() + self.scan_timeout
            while not self.stop.wait(self.interval):
                if time.monotonic() >= deadline:
                    self.send(
                        chat_id,
                        messages.notice("等待同步超时", "OpenList 任务可能仍在运行，请使用 /status 查看。", "warning"),
                    )
                    return
                data = self.progress()
                if data["is_done"]:
                    self.send(
                        chat_id, messages.scan_complete(data.get('obj_count', 0))
                    )
                    return
        except RequestError as exc:
            self.send(
                chat_id, messages.notice("同步请求失败", f"{exc}\n任务可能仍在运行，请使用 /status 查看。", "error")
            )
        finally:
            self.scan_lock.release()

    def handle(self, update):
        if "callback_query" in update:
            self.handle_strm_callback(update["callback_query"])
            return
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
        if command in ("reset", "/reset"):
            self.request_reset(chat_id)
        elif command in ("cancel_refresh", "/cancel_refresh"):
            self.request_cancel_refresh(chat_id)
        elif command in ("download", "/download") and len(parts) == 1:
            if not self.offline.path:
                self.send(chat_id, messages.notice("下载目录未配置", "请先在环境文件中设置 OFFLINE_DOWNLOAD_PATH。", "warning"))
                return
            self.send(
                chat_id,
                messages.download_prompt(self.offline.path),
                reply_markup={
                    "force_reply": True,
                    "input_field_placeholder": "粘贴下载链接，每行一条",
                    "selective": True,
                },
            )
        elif command in ("strm", "/strm"):
            self.show_strm_directories(chat_id)
        elif command in ("refresh", "/refresh"):
            try:
                indices = parse_refresh_indices(parts[1] if len(parts) == 2 else "")
            except ValueError as exc:
                self.send(chat_id, messages.notice("刷新未执行", str(exc), "warning"))
                return
            self.refresh_strm_choices(chat_id, indices)
        elif command in ("sync", "/sync"):
            if not self.scan_lock.acquire(blocking=False):
                self.send(chat_id, messages.notice("正在同步", "请使用 /status 查看进度。", "working"))
                return
            threading.Thread(target=self.sync, args=(chat_id,), daemon=True).start()
        elif command in ("status", "/status"):
            try:
                data = self.progress()
                self.send(
                    chat_id,
                    messages.scan_status(data),
                )
            except RequestError as exc:
                self.send(chat_id, messages.notice("查询失败", str(exc), "error"))
        elif command in ("help", "/help", "/start"):
            self.send(chat_id, messages.help_text(), reply_markup=messages.reset_buttons(self.reset_token))
        elif command in ("downloads", "/downloads"):
            self.send(chat_id, self.offline.status())
        else:
            try:
                links = extract_links(text)
            except ValueError as exc:
                self.send(chat_id, messages.notice("链接未提交", str(exc), "warning"))
                return
            if links:
                self.offline.submit(chat_id, links)
            else:
                self.send(chat_id, messages.notice("操作提示", "请发送完整下载链接，或用 /help 查看命令。"))

    def show_strm_directories(self, chat_id):
        with self.strm_choices_lock:
            self.strm_choices.pop(chat_id, None)
        try:
            directories = self.offline.list_directories(self.path)
        except RequestError as exc:
            self.send(chat_id, messages.notice("读取 STRM 目录失败", str(exc), "error"))
            return
        if not directories:
            self.send(chat_id, messages.notice("暂无文件夹", f"{self.path} 下没有找到子文件夹。"))
            return
        token = secrets.token_hex(6)
        with self.strm_choices_lock:
            self.strm_choices[chat_id] = {
                "created": time.monotonic(),
                "items": [posixpath.join(self.path, item["name"]) for item in directories],
                "directories": directories,
                "root": self.path,
                "token": token,
                "page": 0,
            }
        self.send(chat_id, messages.directory_list(self.path, directories),
                  reply_markup=messages.directory_buttons(token, 0, len(directories), self.reset_token))

    def request_reset(self, chat_id, query_id=None):
        """Exit with failure so systemd restarts the process and all its threads."""
        if self.restart_requested:
            return
        self.restart_requested = True
        self.stop.set()
        LOG.info("授权用户请求重置 bot")
        # Set stop first: a notification failure must never prevent recovery.
        try:
            if query_id:
                self.telegram("answerCallbackQuery", {"callback_query_id": query_id}, timeout=3)
        except RequestError:
            pass
        try:
            self.telegram("sendMessage", {"chat_id": chat_id, "text": messages.reset_notice()}, timeout=3)
        except RequestError as exc:
            LOG.warning("重置通知发送失败：%s", exc)

    def request_cancel_refresh(self, chat_id, token=None, query_id=None):
        count = self.offline.cancel_refresh(chat_id, token)
        text = (f"已请求取消 {count} 个刷新任务。当前请求返回或超时后停止，完成时会通知你。"
                if count else "没有正在执行的刷新任务，或该按钮对应的任务已经结束。")
        try:
            if query_id:
                self.telegram("answerCallbackQuery", {"callback_query_id": query_id, "text": text, "show_alert": True}, timeout=3)
            else:
                self.telegram("sendMessage", {"chat_id": chat_id, "text": messages.notice("取消刷新", text)}, timeout=3)
        except RequestError as exc:
            LOG.warning("取消刷新通知发送失败：%s", exc)

    def dispatch(self, update):
        """Keep reset reachable even while an OpenList request blocks the worker."""
        query = update.get("callback_query") or {}
        message = update.get("message") or {}
        text = (message.get("text") or message.get("caption") or "").strip().split(maxsplit=1)
        is_control = (text and text[0].lower() in ("reset", "/reset", "cancel_refresh", "/cancel_refresh")) or str(query.get("data", "")).startswith(("reset:", "cancel_refresh:"))
        if is_control:
            self.handle(update)  # The usual private-chat and allowlist checks still apply.
            return
        sender = (query or message).get("from") or {}
        chat = (query.get("message") or message).get("chat") or {}
        if sender.get("id") != self.user_id or chat.get("type") != "private":
            return
        try:
            self.commands.put_nowait(update)
        except queue.Full:
            try:
                self.telegram("sendMessage", {
                    "chat_id": chat["id"],
                    "text": messages.notice("操作队列已满", "本次操作未执行，请稍后重发；若持续卡住可用 /reset。", "warning"),
                }, timeout=3)
            except RequestError:
                LOG.warning("操作队列已满，通知发送失败")

    def command_worker(self):
        while not self.stop.is_set():
            try:
                update = self.commands.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                if not self.stop.is_set():
                    self.handle(update)
            except Exception as exc:
                # Do not log exception bodies, which can contain URLs or credentials.
                LOG.warning("命令处理失败：%s", type(exc).__name__)
            finally:
                self.commands.task_done()

    def answer_callback(self, query_id, text=None):
        data = {"callback_query_id": query_id}
        if text:
            data.update(text=text, show_alert=True)
        try:
            self.telegram("answerCallbackQuery", data)
        except RequestError as exc:
            LOG.warning("分页按钮响应失败：%s", exc)

    def handle_strm_callback(self, query):
        message = query.get("message") or {}
        chat = message.get("chat") or {}
        if (query.get("from") or {}).get("id") != self.user_id or chat.get("type") != "private":
            self.answer_callback(query["id"], "仅限授权账户私聊使用。")
            return
        chat_id = chat.get("id")
        if str(query.get("data", "")).startswith("cancel_refresh:"):
            self.request_cancel_refresh(chat_id, query["data"].split(":", 1)[1], query["id"])
            return
        if str(query.get("data", "")).startswith("reset:"):
            if query["data"] == f"reset:{self.reset_token}":
                self.request_reset(chat_id, query["id"])
            else:
                self.answer_callback(query["id"], "Reset 按钮已过期，请发送 /start 获取新按钮，或使用 /reset。")
            return
        parts = str(query.get("data", "")).split(":")
        if (len(parts) != 3 or parts[0] != "strm" or not parts[2].isascii()
                or not parts[2].isdigit() or len(parts[2]) > 6):
            self.answer_callback(query["id"], "无效的分页操作，请发送 /strm。")
            return
        with self.strm_choices_lock:
            choice = self.strm_choices.get(chat_id)
        if (not choice or choice.get("token") != parts[1]
                or time.monotonic() - choice["created"] > 900):
            self.answer_callback(query["id"], "文件夹列表已过期，请发送 /strm 重新获取。")
            return
        page = int(parts[2])
        total = len(choice["directories"])
        if page * messages.DIRECTORY_PAGE_SIZE >= total:
            self.answer_callback(query["id"], "页码超出范围，请发送 /strm 重新获取。")
            return
        self.answer_callback(query["id"])
        text = messages.directory_list(choice["root"], choice["directories"], page)
        # Repeated clicks must not cause Telegram's 'message is not modified' error.
        if choice["page"] == page:
            return
        try:
            self.telegram("editMessageText", {
                "chat_id": chat_id, "message_id": message["message_id"], "text": text,
                "reply_markup": messages.directory_buttons(choice["token"], page, total, self.reset_token),
            })
            choice["page"] = page
        except RequestError as exc:
            LOG.warning("STRM 翻页失败：%s", exc)
            self.send(chat_id, messages.notice("翻页失败", "请重试按钮，或发送 /strm 重新获取。", "warning"))

    def refresh_strm_choices(self, chat_id, indices):
        with self.strm_choices_lock:
            choice = self.strm_choices.get(chat_id)
        if not choice or time.monotonic() - choice["created"] > 900:
            self.send(chat_id, messages.notice("文件夹列表已过期", "请先发送 /strm 重新获取。", "warning"))
            return
        if any(index < 1 or index > len(choice["items"]) for index in indices):
            self.send(chat_id, messages.notice("编号无效", f"编号范围：1 到 {len(choice['items'])}，本批次未执行任何刷新。", "warning"))
            return
        self.offline.manual_refresh_batch(chat_id, [choice["items"][index - 1] for index in indices])

    def run(self):
        delay = 1
        menu_retry_at = 0
        threading.Thread(target=self.offline.run, daemon=True).start()
        threading.Thread(target=self.command_worker, daemon=True).start()
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
                params = {"timeout": 30, "allowed_updates": ["message", "callback_query"]}
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
                    self.dispatch(update)
                delay = 1
            except RequestError as exc:
                LOG.warning("Telegram polling：%s", exc)
                self.stop.wait(delay)
                delay = min(delay * 2, 60)
        return 75 if self.restart_requested else 0


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        bot = Bot(os.environ)
    except ValueError as exc:
        LOG.error("配置错误：%s", exc)
        return 1
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: bot.stop.set())
    return bot.run()


if __name__ == "__main__":
    raise SystemExit(main())
