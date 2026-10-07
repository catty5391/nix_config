import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from bot import Bot
from request_policy import OpenListRequests, RequestDeferred, RequestError


class RequestPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.now = 1000.0
        self.bot = SimpleNamespace(number=Bot.number, offset_file=Path(self.temp.name) / "offset",
                                   stop=Mock(is_set=Mock(return_value=False)))
        self.bot.stop.wait.side_effect = self.advance
        for name in ("time", "monotonic"):
            patcher = patch(f"request_policy.time.{name}", side_effect=lambda: self.now)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.policy = OpenListRequests(self.bot, {})

    def advance(self, seconds):
        self.now += seconds
        return False

    def test_all_endpoints_share_gate_and_heavy_requests_have_extra_spacing(self):
        arrivals = []
        def operation():
            arrivals.append(self.now)
            return {"content": [], "total": 0}
        self.policy.call("/api/fs/list", {"path": "/a", "refresh": True}, operation)
        self.policy.call("/api/fs/list", {"path": "/b", "refresh": True}, operation)
        self.policy.call("/api/task/offline_download/info", {}, operation)
        self.policy.call("/api/fs/add_offline_download", {}, operation)
        self.policy.call("/api/fs/add_offline_download", {}, operation)
        self.policy.call("/api/fs/list", {"path": "/a", "refresh": True}, operation)
        self.assertEqual(arrivals, [1000, 1030, 1040, 1050, 1110, 1300])

    def test_cache_reuses_reads_but_force_refresh_invalidates_old_pages(self):
        first = Mock(return_value={"content": ["first"]})
        self.policy.call("/api/fs/list", {"path": "/a", "refresh": True}, first)
        other = Mock(return_value={"content": ["old-page"]})
        self.policy.call("/api/fs/list", {"path": "/a", "page": 2}, other)
        wire = Mock(return_value={"content": ["new"]})
        self.assertEqual(self.policy.call("/api/fs/list", {"path": "/a/.", "refresh": False}, wire), {"content": ["first"]})
        wire.assert_not_called()
        self.policy.call("/api/fs/list", {"path": "/a", "refresh": True}, wire)
        self.assertEqual(self.now, 1300)
        page = Mock(return_value={"content": ["new-page"]})
        self.policy.call("/api/fs/list", {"path": "/a", "page": 2}, page)
        page.assert_called_once()

    def test_rate_limit_honors_retry_after_and_survives_restart(self):
        failure = Mock(side_effect=RequestError("HTTP 429", status=429, retry_after=3600))
        with self.assertRaises(RequestError):
            self.policy.call("/api/fs/list", {"path": "/a"}, failure)
        self.assertEqual(self.policy.remaining(), 3600)
        restarted = OpenListRequests(self.bot, {})
        operation = Mock()
        with self.assertRaises(RequestDeferred):
            restarted.call("/api/fs/add_offline_download", {}, operation)
        operation.assert_not_called()
        failure.assert_called_once()
        self.advance(3600)
        restarted.call("/api/task/offline_download/info", {}, operation)
        operation.assert_called_once()
        self.assertEqual(restarted.remaining(), 0)

    def test_errors_back_off_without_retrying_the_failed_operation(self):
        failure = Mock(side_effect=RequestError("HTTP 502", status=502))
        for duration in (30, 60, 120):
            with self.assertRaises(RequestError):
                self.policy.call("/api/fs/add_offline_download", {}, failure)
            self.assertEqual(self.policy.remaining(), duration)
            with self.assertRaises(RequestDeferred):
                self.policy.call("/api/fs/add_offline_download", {}, failure)
            self.advance(max(duration, 60))
        self.assertEqual(failure.call_count, 3)

    def test_cancel_during_throttle_wait_does_not_send_or_start_cooldown(self):
        cancel = threading.Event()
        self.policy.next_list = self.now + 300
        def wait(seconds):
            cancel.set()
            return False
        self.bot.stop.wait.side_effect = wait
        operation = Mock()
        with self.policy.cancellable(cancel), self.assertRaisesRegex(RequestError, "取消"):
            self.policy.call("/api/fs/list", {"path": "/a"}, operation)
        operation.assert_not_called()
        self.assertEqual(self.policy.remaining(), 0)

    def test_wait_releases_gate_so_task_reads_can_free_download_slots(self):
        self.policy.next_list = self.now + 30
        status = Mock(return_value={"state": 2})
        visited = False
        def wait(seconds):
            nonlocal visited
            if not visited:
                visited = True
                # This would deadlock if the waiting directory request held the gate.
                self.assertTrue(self.policy.lock.acquire(blocking=False))
                self.policy.lock.release()
                self.policy.call("/api/task/offline_download/info", {}, status)
            return self.advance(seconds)
        self.bot.stop.wait.side_effect = wait
        self.policy.call("/api/fs/list", {"path": "/a"}, Mock(return_value={}))
        status.assert_called_once()

    def test_invalid_intervals_are_rejected(self):
        for value in ("0", "-1", "nan", "inf", "invalid"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                OpenListRequests(self.bot, {"OPENLIST_REQUEST_INTERVAL": value})
