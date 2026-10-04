"""Link parsing and OpenList offline task monitoring (no cloud credentials)."""

import hashlib
import json
import re
import threading
import time
from urllib.parse import parse_qs, quote, urlsplit


def extract_links(text):
    """Accept complete links separated by whitespace; never lowercase a URL."""
    links = []
    for match in re.finditer(r'(?:magnet:\?|ed2k://|https?://)[^\s<>"`]+', text, re.I):
        link = match.group().rstrip("，。；！")
        # Common prose wrappers; keep balanced parentheses inside HTTP URLs.
        while link.endswith(")") and link.count(")") > link.count("("):
            link = link[:-1]
        if link.endswith("]") and "[" not in link:
            link = link[:-1]
        try:
            parsed = urlsplit(link)
            if parsed.scheme.lower() == "magnet":
                valid = any(re.fullmatch(r"urn:btih:(?:[0-9a-f]{40}|[a-z2-7]{32})|urn:btmh:1220[0-9a-f]{64}", xt, re.I)
                            for xt in parse_qs(parsed.query).get("xt", []))
            elif parsed.scheme.lower() == "ed2k":
                valid = bool(re.fullmatch(r"ed2k://\|file\|[^|]+\|[0-9]+\|[0-9a-f]{32}\|(?:[^\s]*)/", link, re.I))
            else:
                valid = bool(parsed.hostname) and not parsed.username and not parsed.password
                parsed.port  # Validate the port without modifying signed URLs.
        except ValueError:
            valid = False
        if valid and parsed.scheme.lower() in ("http", "https") and parsed.hostname.lower().rstrip(".") == "115cdn":
            raise ValueError("暂不支持 http://115cdn/ 链接，请发送磁力或 ed2k 链接；本条消息中的链接均未提交。")
        if not valid:
            raise ValueError("链接格式不正确，请发送完整的磁力、ed2k 或 HTTP(S) 链接；每条链接单独一行。")
        if link not in links:
            links.append(link)
    if len(links) > 20:
        raise ValueError("每次最多发送 20 条链接。")
    return links


class OfflineDownloads:
    def __init__(self, bot, env):
        self.bot = bot
        self.path = env.get("OFFLINE_DOWNLOAD_PATH", "").strip()
        if self.path and (not self.path.startswith("/") or ".." in self.path.split("/")):
            raise ValueError("OFFLINE_DOWNLOAD_PATH 必须是 OpenList 中的绝对目录路径")
        self.tool = env.get("OFFLINE_DOWNLOAD_TOOL", "115 Cloud").strip()
        if not self.tool:
            raise ValueError("OFFLINE_DOWNLOAD_TOOL 不能为空")
        self.interval = bot.number(env, "OFFLINE_POLL_INTERVAL", 15)
        self.timeout = bot.number(env, "OFFLINE_TIMEOUT", 86400)
        self.state_file = bot.offset_file.parent / "offline-tasks.json"
        self.jobs = json.loads(self.state_file.read_text()) if self.state_file.exists() else {}
        self.lock = threading.Lock()
        self.submit_lock = threading.Lock()
        self.refresh_lock = threading.Lock()

    def refresh(self, path):
        self.bot.api("/api/fs/list", {
            "path": path, "password": "", "page": 1,
            "per_page": 1, "refresh": True,
        })

    def manual_refresh(self, chat_id):
        if not self.path:
            self.bot.send(chat_id, "请先在环境文件中设置 OFFLINE_DOWNLOAD_PATH。")
            return
        if not self.refresh_lock.acquire(blocking=False):
            self.bot.send(chat_id, "正在刷新下载目录，请稍候。")
            return
        threading.Thread(target=self._manual_refresh, args=(chat_id,), daemon=True).start()

    def _manual_refresh(self, chat_id):
        try:
            self.refresh(self.path)
            self.bot.send(chat_id, f"已刷新下载目录：{self.path}")
        except self.bot.request_error as exc:
            self.bot.send(chat_id, f"目录刷新失败：{exc}，可用 /refresh 重试。")
        finally:
            self.refresh_lock.release()

    def save(self):
        temporary = self.state_file.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.jobs, ensure_ascii=False))
        temporary.replace(self.state_file)

    def submit(self, chat_id, links):
        if not self.path:
            self.bot.send(chat_id, "请先在环境文件中设置 OFFLINE_DOWNLOAD_PATH。")
            return
        if not self.submit_lock.acquire(blocking=False):
            self.bot.send(chat_id, "上一批链接正在提交，请稍后再发。")
            return
        threading.Thread(target=self._submit, args=(chat_id, links), daemon=True).start()

    def _submit(self, chat_id, links):
        try:
            with self.lock:
                if len(self.jobs) + len(links) > 100:
                    self.bot.send(chat_id, "正在跟踪的任务过多，请等待已有任务完成。")
                    return
            for index, link in enumerate(links, 1):
                if self.bot.stop.is_set():
                    return
                fingerprint = hashlib.sha256((self.path + "\0" + link).encode()).hexdigest()
                with self.lock:
                    duplicate = any(j["fingerprint"] == fingerprint for j in self.jobs.values())
                if duplicate:
                    self.bot.send(chat_id, f"第 {index} 条链接已有正在跟踪的任务，已跳过。")
                    continue
                try:
                    # One URL per request prevents ambiguous partial batch success.
                    data = self.bot.api("/api/fs/add_offline_download", {
                        "path": self.path, "urls": [link], "tool": self.tool,
                        "delete_policy": "delete_never",
                    })
                except self.bot.request_error as exc:
                    self.bot.send(chat_id, f"第 {index} 条提交未确认：{exc}。请先检查 OpenList 任务列表，避免重复添加。")
                    continue
                tasks = data.get("tasks") if isinstance(data, dict) else None
                if not isinstance(tasks, list) or not tasks or any(
                    not isinstance(t, dict) or not isinstance(t.get("id"), str) or not t["id"] for t in tasks
                ):
                    self.bot.send(chat_id, f"第 {index} 条接口已接受，但未返回可跟踪的任务 ID；请在 OpenList 中查看结果。")
                    continue
                with self.lock:
                    for task in tasks:
                        self.jobs[task["id"]] = {
                            "chat_id": chat_id, "path": self.path,
                            "fingerprint": fingerprint, "created": time.time(),
                        }
                    self.save()
                self.bot.send(chat_id, f"第 {index} 条已提交到 {self.path}，等待 OpenList 下载。")
        except OSError:
            self.bot.send(chat_id, "任务状态保存失败，请在 OpenList 中检查任务；不要直接重复提交。")
        finally:
            self.submit_lock.release()

    def check(self):
        with self.lock:
            jobs = list(self.jobs.items())
        for task_id, job in jobs:
            if self.bot.stop.is_set():
                return
            if time.time() - job["created"] > self.timeout:
                text = "离线任务监控超时；OpenList 任务未被取消，请到后台查看。"
            else:
                try:
                    task = self.bot.api("/api/task/offline_download/info?tid=" + quote(task_id, safe=""), {})
                    if not isinstance(task, dict):
                        continue
                    state = task.get("state")
                    # OpenListTeam/tache: succeeded=2, canceled=4, failed=7.
                    if state == 2:
                        try:
                            self.refresh(job["path"])
                            text = f"OpenList 离线任务已完成，已刷新目录：{job['path']}"
                        except self.bot.request_error as exc:
                            text = f"OpenList 离线任务已完成：{job['path']}\n目录刷新失败：{exc}，可用 /refresh 重试。"
                    elif state in (4, 7):
                        text = "OpenList 离线任务已取消或失败，请到后台查看具体原因。"
                    else:
                        continue
                except self.bot.request_error:
                    # Retry status reads only; never resubmit download requests.
                    continue
            with self.lock:
                del self.jobs[task_id]
                self.save()
            self.bot.send(job["chat_id"], text)

    def run(self):
        while not self.bot.stop.is_set():
            try:
                self.check()
            except OSError:
                # Keep the polling thread alive on temporary state-directory failures.
                pass
            self.bot.stop.wait(self.interval)

    def status(self):
        with self.lock:
            count = len(self.jobs)
        return f"离线下载目录：{self.path or '未配置'}\n下载工具：{self.tool}\n正在跟踪：{count} 个任务"
