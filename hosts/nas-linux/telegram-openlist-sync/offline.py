"""Link parsing and OpenList offline task monitoring (no cloud credentials)."""

import hashlib
import json
import posixpath
import re
import secrets
import threading
import time
from datetime import datetime
from urllib.parse import parse_qs, quote, urlsplit

from ui import messages
from request_policy import is_risk_error

MAX_REFRESH_SELECTIONS = 5


def parse_refresh_indices(text):
    text = text.strip()
    if not text:
        raise ValueError("必须填写序号。先用 /strm 获取列表，再发送 /refresh 1 3 5。")
    if len(text) > 256 or not re.fullmatch(r"[0-9]+(?:(?:\s*[,，]\s*|\s+)[0-9]+)*", text):
        raise ValueError("只支持正整数序号，用空格或逗号分隔，例如 /refresh 1 3 5；不支持范围或路径。")
    parts = re.split(r"[\s,，]+", text)
    if any(len(part) > 6 or int(part) < 1 for part in parts):
        raise ValueError("序号必须是 1 到 999999 之间的正整数。")
    indices = list(dict.fromkeys(int(part) for part in parts))
    if len(indices) > MAX_REFRESH_SELECTIONS:
        raise ValueError(f"每批最多选择 {MAX_REFRESH_SELECTIONS} 个文件夹，本次未执行任何刷新。")
    return indices


class RefreshCancelled(Exception):
    def __init__(self, count):
        self.count = count
        super().__init__("刷新已取消")


class RefreshLimitReached(Exception):
    pass


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
        self.interval = bot.number(env, "OFFLINE_POLL_INTERVAL", 60)
        self.timeout = bot.number(env, "OFFLINE_TIMEOUT", 86400)
        self.max_active = int(env.get("OFFLINE_MAX_ACTIVE_DOWNLOADS", "1"))
        if not 1 <= self.max_active <= 100:
            raise ValueError("OFFLINE_MAX_ACTIVE_DOWNLOADS 必须介于 1 和 100")
        self.refresh_recursive = env.get("OFFLINE_REFRESH_RECURSIVE", "true").lower()
        if self.refresh_recursive not in ("true", "false"):
            raise ValueError("OFFLINE_REFRESH_RECURSIVE 必须为 true 或 false")
        try:
            self.refresh_max_dirs = int(env.get("OFFLINE_REFRESH_MAX_DIRS", "100"))
            self.refresh_max_depth = int(env.get("OFFLINE_REFRESH_MAX_DEPTH", "6"))
            self.refresh_request_budget = int(env.get("OPENLIST_REFRESH_REQUEST_BUDGET", "200"))
        except ValueError:
            raise ValueError("刷新目录数、深度和请求次数上限必须是整数") from None
        if self.refresh_max_dirs < 1 or self.refresh_max_dirs > 1000000:
            raise ValueError("OFFLINE_REFRESH_MAX_DIRS 超出范围")
        if not 0 <= self.refresh_max_depth <= 100:
            raise ValueError("OFFLINE_REFRESH_MAX_DEPTH 必须介于 0 和 100")
        if not 1 <= self.refresh_request_budget <= 10000:
            raise ValueError("OPENLIST_REFRESH_REQUEST_BUDGET 必须介于 1 和 10000")
        self.state_file = bot.offset_file.parent / "offline-tasks.json"
        self.jobs = json.loads(self.state_file.read_text()) if self.state_file.exists() else {}
        self.lock = threading.Lock()
        self.submit_lock = threading.Lock()
        self.submitting_batches = set()
        self.refresh_lock = threading.Lock()
        self.active_refreshes = {}
        self.active_refreshes_lock = threading.Lock()

    def cancel_refresh(self, chat_id, token=None):
        with self.active_refreshes_lock:
            tasks = [task for key, task in self.active_refreshes.items()
                     if task["chat_id"] == chat_id and (token is None or key == token)]
            for task in tasks:
                task["cancel"].set()
        return len(tasks)

    def _check_cancel(self, task):
        if task is not None and (task["cancel"].is_set() or self.bot.stop.is_set()):
            raise RefreshCancelled(task["count"])

    def _refresh_list(self, path, page, task, force=True):
        self._check_cancel(task)
        if task is not None:
            if task.get("requests", 0) >= self.refresh_request_budget:
                raise RefreshLimitReached()
            task["requests"] = task.get("requests", 0) + 1
        try:
            with self.bot.requests.cancellable(task["cancel"] if task else None):
                data = self.bot.api("/api/fs/list", {
                    "path": path, "password": "", "page": page,
                    "per_page": 1000, "refresh": force and page == 1,
                })
        except self.bot.request_error:
            self._check_cancel(task)
            raise
        if task is not None and page == 1 and isinstance(data, dict):
            task["count"] += 1
        self._check_cancel(task)
        return data

    def run_refresh(self, path, chat_id, recursive=None, parent=None):
        paths = [path] if isinstance(path, str) else path
        label = "\n".join(paths)
        token = secrets.token_hex(8)
        task = {"chat_id": chat_id, "cancel": threading.Event(), "count": 0}
        with self.active_refreshes_lock:
            self.active_refreshes[token] = task
        try:
            preface = f"先更新父目录列表：{parent}\n" if parent else ""
            self.bot.send(chat_id, messages.notice("开始刷新", f"{preface}共 {len(paths)} 个目录，依次执行：\n{label}\n可随时取消整批后续刷新。", "working"),
                          reply_markup=messages.cancel_refresh_buttons(token))
            count, limited = 0, False
            if parent:
                count += self._refresh_one(parent, task)[0]
            for selected_path in paths:
                self._check_cancel(task)
                if task["count"] >= self.refresh_max_dirs:
                    limited = True
                    break
                if recursive is False:
                    refreshed, limited = self._refresh_one(selected_path, task)[0], False
                else:
                    refreshed, limited = self.refresh(selected_path, task)
                count += refreshed
                if limited:
                    break
            with self.active_refreshes_lock:
                self._check_cancel(task)
                self.active_refreshes.pop(token, None)
            return count, limited
        except RefreshLimitReached:
            return task["count"], True
        finally:
            with self.active_refreshes_lock:
                self.active_refreshes.pop(token, None)

    def refresh_tree(self, root, task=None):
        """Refresh root and every discovered descendant directory."""
        pending = [(root, 0)]
        visited = set()
        depth_limited = False
        while pending:
            self._check_cancel(task)
            path, depth = pending.pop()
            if path in visited:
                continue
            if (task["count"] if task is not None else len(visited)) >= self.refresh_max_dirs:
                return len(visited), True
            visited.add(path)
            page = 1
            while True:
                data = self._refresh_list(path, page, task)
                if not isinstance(data, dict) or not isinstance(data.get("content") or [], list):
                    raise self.bot.request_error("OpenList 目录响应格式错误")
                content = data.get("content") or []
                for item in content:
                    name = item.get("name") if isinstance(item, dict) else None
                    if isinstance(item, dict) and item.get("is_dir") and isinstance(name, str) and name not in ("", ".", "..") and "/" not in name:
                        if depth < self.refresh_max_depth:
                            pending.append((posixpath.join(path, name), depth + 1))
                        else:
                            depth_limited = True
                total = data.get("total", len(content))
                if not isinstance(total, int) or total < len(content):
                    raise self.bot.request_error("OpenList 目录总数格式错误")
                if page * 1000 >= total or not content:
                    break
                page += 1
        return len(visited), depth_limited

    def refresh(self, path, task=None):
        return self.refresh_tree(path, task) if self.refresh_recursive == "true" else (*self._refresh_one(path, task), False)

    def list_directories(self, root, task=None):
        """Return immediate child directories, newest first."""
        entries = []
        page = 1
        while True:
            if page > self.refresh_request_budget:
                raise self.bot.request_error("目录列表超过读取上限，未继续获取")
            # Browsing /strm uses the OpenList/local cache; explicit refresh stays fresh.
            data = self._refresh_list(root, page, task, force=task is not None)
            if not isinstance(data, dict) or not isinstance(data.get("content") or [], list):
                raise self.bot.request_error("OpenList 目录响应格式错误")
            content = data.get("content") or []
            for item in content:
                if not isinstance(item, dict) or not item.get("is_dir"):
                    continue
                name = item.get("name")
                if not isinstance(name, str) or name in ("", ".", "..") or "/" in name:
                    continue
                modified = item.get("modified")
                try:
                    timestamp = datetime.fromisoformat(str(modified).replace("Z", "+00:00")).timestamp()
                except (TypeError, ValueError, OverflowError, OSError):
                    timestamp = 0
                entries.append({"name": name, "modified": modified, "timestamp": timestamp})
            total = data.get("total", len(content))
            if not isinstance(total, int) or total < len(content):
                raise self.bot.request_error("OpenList 目录总数格式错误")
            if page * 1000 >= total or not content:
                break
            page += 1
        return sorted(entries, key=lambda item: (item["timestamp"], item["name"]), reverse=True)

    def refresh_downloaded_directory(self, job, directory_count=1):
        """TaskInfo has no result paths; select one newest child per successful link."""
        root = job["path"]
        chat_id = job["chat_id"]
        token = secrets.token_hex(8)
        control = {"chat_id": chat_id, "cancel": threading.Event(), "count": 0}
        with self.active_refreshes_lock:
            self.active_refreshes[token] = control
        try:
            self.bot.send(chat_id, messages.notice("离线任务已完成 · 查找刷新目录",
                          f"下载位置：{root}\n本批成功 {directory_count} 条链接，将按修改时间选择最新的 {directory_count} 个子目录。", "working"),
                          reply_markup=messages.cancel_refresh_buttons(token))
            directories = self.list_directories(root, control)
            self._check_cancel(control)
            selected = []
            seen = set()
            for item in directories:
                if item["timestamp"] != 0 and item["name"] not in seen:
                    selected.append(posixpath.join(root, item["name"]))
                    seen.add(item["name"])
                    if len(selected) == directory_count:
                        break
            if not selected:
                text = messages.notice("离线任务已完成", f"已更新目标目录列表：{root}\n"
                                       "没有找到具有有效修改时间的子目录，未执行子目录递归刷新。")
            elif control["count"] >= self.refresh_max_dirs:
                text = messages.notice("离线任务已完成 · 达到刷新上限",
                                       f"已更新目标目录列表：{root}\n已达到目录数量上限，未递归子目录。", "warning")
            else:
                label = "\n".join(selected)
                self.bot.send(chat_id, messages.notice("自动刷新所选目录",
                              f"{label}\n选择方式：最新修改时间（推测），依次刷新这 {len(selected)} 个目录及其子目录。", "working"),
                              reply_markup=messages.cancel_refresh_buttons(token))
                count, limited = 0, False
                started = []
                for target in selected:
                    self._check_cancel(control)
                    if control["count"] >= self.refresh_max_dirs:
                        limited = True
                        break
                    started.append(target)
                    refreshed, limited = self.refresh(target, control)
                    count += refreshed
                    if limited:
                        break
                text = messages.refresh_complete("\n".join(started), count, limited, self.refresh_recursive == "true", downloaded=True)
                if len(selected) < directory_count:
                    text += f"\n符合条件的子目录只有 {len(selected)} 个，少于本批成功的 {directory_count} 条链接，按实际数量刷新。"
                text += "\n\n选择方式：按下载目标目录中的最新修改时间选择，属于推测。"
            with self.active_refreshes_lock:
                self._check_cancel(control)
                self.active_refreshes.pop(token, None)
            return text
        except RefreshLimitReached:
            return messages.notice("离线任务已完成 · 达到刷新上限",
                                   f"目录：{root}\n已达到本批目录读取次数上限，后续刷新停止，尚未全部完成。", "warning")
        finally:
            with self.active_refreshes_lock:
                self.active_refreshes.pop(token, None)

    def _refresh_one(self, path, task=None):
        data = self._refresh_list(path, 1, task)
        if not isinstance(data, dict):
            raise self.bot.request_error("OpenList 目录响应格式错误")
        return (1,)

    def manual_refresh_batch(self, chat_id, paths, parent=None):
        paths = list(dict.fromkeys(paths))
        if not paths or len(paths) > MAX_REFRESH_SELECTIONS:
            self.bot.send(chat_id, messages.notice("刷新未执行", f"每批必须选择 1 到 {MAX_REFRESH_SELECTIONS} 个文件夹。", "warning"))
            return
        self.manual_refresh(chat_id, paths[0] if len(paths) == 1 else paths, parent=parent)

    def manual_refresh(self, chat_id, path=None, parent=None):
        path = path or self.path
        if not path:
            self.bot.send(chat_id, messages.notice("下载目录未配置", "请先在环境文件中设置 OFFLINE_DOWNLOAD_PATH。", "warning"))
            return
        if not self.refresh_lock.acquire(blocking=False):
            self.bot.send(chat_id, messages.notice("正在刷新", "已有目录刷新任务，请稍候。", "working"))
            return
        threading.Thread(target=self._manual_refresh, args=(chat_id, path, parent), daemon=True).start()

    def _manual_refresh(self, chat_id, path=None, parent=None):
        path = path or self.path
        label = path if isinstance(path, str) else "\n".join(path)
        try:
            count, limited = self.run_refresh(path, chat_id, parent=parent)
            text = messages.refresh_complete(label, count, limited, self.refresh_recursive == "true")
            if parent:
                text += f"\n\n已先更新父目录列表：{parent}（计入刷新目录数）"
        except RefreshCancelled as exc:
            text = messages.refresh_cancelled(label, exc.count)
        except self.bot.request_error as exc:
            text = messages.notice("目录刷新失败", f"所选目录：\n{label}\n{exc}\n后续目录未继续刷新。先用 /strm 获取列表，再用 /refresh 序号 重试。", "error")
        finally:
            self.refresh_lock.release()
        self.bot.send(chat_id, text)

    def save(self):
        temporary = self.state_file.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.jobs, ensure_ascii=False))
        temporary.replace(self.state_file)

    def submit(self, chat_id, links):
        if not self.path:
            self.bot.send(chat_id, messages.notice("下载目录未配置", "请先在环境文件中设置 OFFLINE_DOWNLOAD_PATH。", "warning"))
            return
        if not self.submit_lock.acquire(blocking=False):
            self.bot.send(chat_id, messages.notice("正在提交", "上一批链接正在提交，请稍后再发。", "working"))
            return
        threading.Thread(target=self._submit, args=(chat_id, links), daemon=True).start()

    def _submit(self, chat_id, links):
        batch_id = secrets.token_hex(16)
        with self.lock:
            self.submitting_batches.add(batch_id)
        try:
            with self.lock:
                if len(self.jobs) + len(links) > 100:
                    self.bot.send(chat_id, messages.notice("任务已满", "正在跟踪的任务过多，请等待已有任务完成。", "warning"))
                    return
            for index, link in enumerate(links, 1):
                if self.bot.stop.is_set():
                    return
                fingerprint = hashlib.sha256((self.path + "\0" + link).encode()).hexdigest()
                with self.lock:
                    duplicate = any(j["fingerprint"] == fingerprint for j in self.jobs.values())
                if duplicate:
                    self.bot.send(chat_id, messages.notice(f"第 {index} 条已跳过", "该链接已有正在跟踪的任务。"))
                    continue
                # Bound OpenList's own background pollers, not just this bot's API rate.
                while not self.bot.stop.is_set():
                    with self.lock:
                        active = sum(not j.get("outcome") for j in self.jobs.values())
                    if active < self.max_active:
                        break
                    self.bot.stop.wait(1)
                if self.bot.stop.is_set():
                    return
                try:
                    # One URL per request prevents ambiguous partial batch success.
                    data = self.bot.api("/api/fs/add_offline_download", {
                        "path": self.path, "urls": [link], "tool": self.tool,
                        "delete_policy": "delete_never",
                    })
                except self.bot.request_error as exc:
                    self.bot.send(chat_id, messages.notice(f"第 {index} 条提交未确认", f"{exc}\n请先检查 OpenList 任务列表，避免重复添加。", "warning"))
                    if self.bot.requests.remaining() > 0:
                        self.bot.send(chat_id, messages.notice("剩余链接暂停提交", "已进入请求冷却，剩余链接未提交；冷却结束后请核对任务再重新发送。", "warning"))
                        return
                    continue
                tasks = data.get("tasks") if isinstance(data, dict) else None
                if not isinstance(tasks, list) or not tasks or any(
                    not isinstance(t, dict) or not isinstance(t.get("id"), str) or not t["id"] for t in tasks
                ):
                    self.bot.send(chat_id, messages.notice(f"第 {index} 条接口已接受", "未返回可跟踪的任务 ID，无法判断下载是否结束，已停止本批后续提交。请在 OpenList 中查看结果。", "warning"))
                    return
                with self.lock:
                    for task in tasks:
                        self.jobs[task["id"]] = {
                            "chat_id": chat_id, "path": self.path,
                            "fingerprint": fingerprint, "created": time.time(),
                            "batch_id": batch_id,
                        }
                    self.save()
                self.bot.send(chat_id, messages.submitted(index, self.path))
        except OSError:
            self.bot.send(chat_id, messages.notice("任务状态保存失败", "请在 OpenList 中检查任务，不要直接重复提交。", "error"))
        finally:
            with self.lock:
                self.submitting_batches.discard(batch_id)
            self.submit_lock.release()

    def check(self):
        with self.lock:
            jobs = list(self.jobs.items())
        for task_id, job in jobs:
            if self.bot.stop.is_set():
                return
            if job.get("outcome"):
                continue
            if time.time() - job["created"] > self.timeout:
                outcome = "timeout"
            else:
                try:
                    task = self.bot.api("/api/task/offline_download/info?tid=" + quote(task_id, safe=""), {})
                    if not isinstance(task, dict):
                        continue
                    state = task.get("state")
                    # OpenListTeam/tache: succeeded=2, canceled=4, failed=7.
                    if state == 2:
                        outcome = "success"
                    elif state in (4, 7):
                        outcome = "failed"
                        if is_risk_error(task.get("error", "")):
                            self.bot.requests.report_task_risk()
                    else:
                        continue
                except self.bot.request_deferred:
                    return
                except self.bot.request_error:
                    # Retry status reads only; never resubmit download requests.
                    break
            with self.lock:
                job["outcome"] = outcome
                self.save()
        self._finish_batches()

    def _finish_batches(self):
        with self.lock:
            groups = {}
            for task_id, job in self.jobs.items():
                # Old state files did not record batches; retain one-link behavior.
                key = (job.get("batch_id", f"legacy:{task_id}"), job["chat_id"], job["path"])
                groups.setdefault(key, []).append((task_id, job))
        for (batch_id, _, _), entries in groups.items():
            if self.bot.stop.is_set():
                return
            with self.lock:
                if batch_id in self.submitting_batches:
                    continue
            if any(not job.get("outcome") for _, job in entries):
                continue
            # A URL can yield multiple task IDs. Count links, not returned task IDs.
            links = {}
            for task_id, job in entries:
                links.setdefault(job.get("fingerprint", task_id), []).append(job["outcome"])
            successful = sum(all(state == "success" for state in states) for states in links.values())
            job = entries[0][1]
            if successful:
                if self.bot.requests.remaining() > 0 or not self.refresh_lock.acquire(blocking=False):
                    continue  # Keep the batch persisted until the current refresh/cooldown finishes.
                try:
                    text = self.refresh_downloaded_directory(job, successful)
                except self.bot.request_deferred:
                    continue
                except RefreshCancelled as exc:
                    text = messages.refresh_cancelled(job["path"], exc.count, downloaded=True)
                except self.bot.request_error as exc:
                    if self.bot.requests.remaining() > 0:
                        self.bot.send(job["chat_id"], messages.notice("自动刷新已暂停",
                                      "OpenList 请求失败，已进入冷却。下载记录已保留，冷却结束后继续刷新。", "warning"))
                        continue
                    text = messages.notice("离线任务已完成 · 目录刷新失败", f"目录：{job['path']}\n{exc}\n先用 /strm 获取列表，再用 /refresh 序号 选择目录刷新。", "warning")
                finally:
                    self.refresh_lock.release()
            elif any(job["outcome"] == "timeout" for _, job in entries):
                text = messages.notice("离线任务监控超时", "OpenList 任务未被取消，请到后台查看。", "warning")
            else:
                text = messages.notice("离线任务已取消或失败", "请到 OpenList 后台查看具体原因。", "error")
            unsuccessful = len(links) - successful
            if successful and unsuccessful:
                text += f"\n\n本批成功 {successful} 条，失败、取消或监控超时 {unsuccessful} 条；未成功的链接不计入刷新数量。"
            if self.bot.stop.is_set():
                return
            with self.lock:
                for task_id, _ in entries:
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
        text = messages.download_status(self.path, self.tool, count)
        text += f"\n\n同时下载上限：{self.max_active} 条\n目录请求间隔：至少 {self.bot.requests.list_interval:g} 秒"
        if self.bot.requests.remaining() > 0:
            text += f"\n请求冷却中：剩余约 {int(self.bot.requests.remaining()) + 1} 秒"
        return text
