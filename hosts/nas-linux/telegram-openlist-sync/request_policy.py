"""One cancellable request gate for all OpenList traffic; no automatic write retries."""

import json
import math
import posixpath
import threading
import time
from collections import OrderedDict
from contextlib import contextmanager


class RequestError(Exception):
    """Safe diagnostic without response bodies, URLs or credentials."""

    def __init__(self, message, *, status=None, retry_after=0, risk=False):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after
        self.risk = risk


class RequestDeferred(RequestError):
    """The circuit is open; keep completed download jobs for later refresh."""


def is_risk_error(message):
    value = str(message).lower()
    return any(word in value for word in (
        "风控", "频繁", "验证码", "安全验证", "访问受限", "too many requests",
        "rate limit", "captcha", "risk control", "429",
    ))


class OpenListRequests:
    def __init__(self, bot, env):
        self.bot = bot
        self.interval = bot.number(env, "OPENLIST_REQUEST_INTERVAL", 10)
        self.list_interval = bot.number(env, "OPENLIST_LIST_INTERVAL", 30)
        self.submit_interval = bot.number(env, "OPENLIST_SUBMIT_INTERVAL", 60)
        self.refresh_interval = bot.number(env, "OPENLIST_PATH_REFRESH_INTERVAL", 300)
        self.cache_ttl = bot.number(env, "OPENLIST_LIST_CACHE_TTL", 300)
        self.risk_cooldown = bot.number(env, "OPENLIST_RISK_COOLDOWN", 1800)
        self.backoff = bot.number(env, "OPENLIST_ERROR_BACKOFF", 30)
        self.state_file = bot.offset_file.parent / "openlist-request-state.json"
        self.lock = threading.Lock()
        self.local = threading.local()
        self.cache = OrderedDict()
        self.last_refresh = OrderedDict()
        self.next_request = self.next_list = self.next_submit = 0
        self.blocked_until = 0
        self.failures = 0
        if self.state_file.exists():
            state = json.loads(self.state_file.read_text())
            self.blocked_until = float(state["blocked_until"])
            self.failures = int(state.get("failures", 0))
            if not math.isfinite(self.blocked_until) or not 0 <= self.failures <= 20:
                raise ValueError("OpenList 请求冷却状态无效")

    @contextmanager
    def cancellable(self, event):
        previous = getattr(self.local, "cancel", None)
        self.local.cancel = event
        try:
            yield
        finally:
            self.local.cancel = previous

    def _check(self):
        cancel = getattr(self.local, "cancel", None)
        if self.bot.stop.is_set() or (cancel is not None and cancel.is_set()):
            raise RequestError("请求等待已取消")
        remaining = self.remaining()
        if remaining > 0:
            raise RequestDeferred(f"OpenList 请求冷却中，约 {math.ceil(remaining)} 秒后恢复")

    def remaining(self):
        return max(0, self.blocked_until - time.time())

    def _save(self):
        temporary = self.state_file.with_suffix(".tmp")
        temporary.write_text(json.dumps({"blocked_until": self.blocked_until, "failures": self.failures}))
        temporary.replace(self.state_file)

    def _fail(self, exc):
        self.failures = min(self.failures + 1, 20)
        delay = min(self.backoff * 2 ** (self.failures - 1), 900)
        if exc.risk or exc.status in (403, 429):
            delay = max(delay, self.risk_cooldown)
        delay = max(delay, exc.retry_after)
        self.blocked_until = max(self.blocked_until, time.time() + delay)
        self._save()

    def report_task_risk(self):
        with self.lock:
            self._fail(RequestError("离线任务返回风控或限流信息", risk=True))

    def call(self, endpoint, data, operation):
        """Serialize wire requests, reuse read caches, and honor stop/cancel during waits."""
        is_list = endpoint == "/api/fs/list" and isinstance(data, dict)
        is_submit = endpoint == "/api/fs/add_offline_download"
        key = path = None
        force = False
        if is_list:
            path = posixpath.normpath(data["path"])
            key = (path, data.get("page", 1), data.get("per_page", 1000), data.get("password", ""))
            force = bool(data.get("refresh"))
        while True:
            self._check()
            if not self.lock.acquire(timeout=0.2):
                continue
            try:
                self._check()
                cached = self.cache.get(key) if is_list else None
                if not force and cached and time.monotonic() - cached[0] < self.cache_ttl:
                    self.cache.move_to_end(key)
                    return cached[1]
                due = self.next_request
                if is_list:
                    due = max(due, self.next_list)
                    if force and path in self.last_refresh:
                        due = max(due, self.last_refresh[path] + self.refresh_interval)
                if is_submit:
                    due = max(due, self.next_submit)
                delay = due - time.monotonic()
                if delay <= 0:
                    return self._perform(operation, is_list, is_submit, path, key, force)
            finally:
                self.lock.release()
            # Release the gate while sleeping, so a slow directory refresh does not
            # prevent task-status reads from freeing download slots.
            self.bot.stop.wait(min(0.2, delay))

    def _perform(self, operation, is_list, is_submit, path, key, force):
        try:
            result = operation()
        except RequestError as exc:
            self._fail(exc)
            raise
        finally:
            now = time.monotonic()
            self.next_request = now + self.interval
            if is_list:
                self.next_list = now + self.list_interval
            if is_submit:
                self.next_submit = now + self.submit_interval
        if self.failures:
            self.blocked_until = self.failures = 0
            self._save()
        if is_list:
            if force:
                for old in list(self.cache):
                    if old[0] == path:
                        del self.cache[old]
                self.last_refresh[path] = now
                self.last_refresh.move_to_end(path)
                while len(self.last_refresh) > 1000:
                    self.last_refresh.popitem(last=False)
            self.cache[key] = (now, result)
            self.cache.move_to_end(key)
            while len(self.cache) > 128:
                self.cache.popitem(last=False)
        return result
