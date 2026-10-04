import tempfile
import unittest
from unittest.mock import Mock, patch

from bot import Bot, RequestError
from offline import extract_links

MAGNET = "magnet:?xt=urn:btih:" + "A" * 40 + "&dn=MixedCase&tr=https%3A%2F%2FTracker"
ED2K = "ed2k://|file|MyFile.mkv|123|" + "B" * 32 + "|/"


class LinkTests(unittest.TestCase):
    def test_batch_preserves_case_and_deduplicates(self):
        self.assertEqual(extract_links(f"下载：\n{MAGNET}\n{ED2K}\n{MAGNET}"), [MAGNET, ED2K])

    def test_signed_http_and_wrappers(self):
        link = "https://cdn.example/File(1).mkv?sign=AbC%2Fdef&x=2"
        self.assertEqual(extract_links(f"({link})"), [link])

    def test_115cdn_variants_rejected(self):
        for link in ("http://115cdn/file", "https://115cdn/file", "HTTP://115CDN/file", "http://115cdn.:80/file"):
            with self.subTest(link=link), self.assertRaisesRegex(ValueError, "暂不支持"):
                extract_links(link)

    def test_invalid_links(self):
        for link in ("magnet:?xt=bad", "ed2k://|file|bad|/", "https://user:password@example.com/a"):
            with self.subTest(link=link), self.assertRaises(ValueError):
                extract_links(link)

    def test_batch_limit(self):
        with self.assertRaises(ValueError):
            extract_links("\n".join(f"https://example.com/{n}" for n in range(21)))


class BotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = dict(TELEGRAM_BOT_TOKEN="test", ALLOWED_USER_ID="42",
                        OPENLIST_URL="http://localhost:5244", OPENLIST_TOKEN="test",
                        STATE_DIRECTORY=self.temp.name, OFFLINE_DOWNLOAD_PATH="/115/Downloads")
        self.bot = Bot(self.env)
        self.bot.send = Mock()

    def message(self, text, user=42, kind="private"):
        return {"message": {"from": {"id": user}, "chat": {"id": 42, "type": kind}, "text": text}}

    def test_authorization(self):
        with patch.object(self.bot.offline, "submit") as submit:
            self.bot.handle(self.message(MAGNET, user=43))
            self.bot.handle(self.message(MAGNET, kind="group"))
            submit.assert_not_called()

    def test_dispatch_preserves_url(self):
        with patch.object(self.bot.offline, "submit") as submit:
            self.bot.handle(self.message("/download " + MAGNET))
            submit.assert_called_once_with(42, [MAGNET])

    def test_115cdn_message_is_not_submitted(self):
        with patch.object(self.bot.offline, "submit") as submit:
            self.bot.handle(self.message(MAGNET + "\nhttp://115cdn/example"))
            submit.assert_not_called()
        self.assertIn("暂不支持", self.bot.send.call_args.args[1])

    def test_menu(self):
        self.bot.telegram = Mock()
        self.bot.register_commands()
        commands = self.bot.telegram.call_args_list[0].args[1]["commands"]
        self.assertIn("download", [c["command"] for c in commands])
        self.assertIn("refresh", [c["command"] for c in commands])
        self.assertEqual(self.bot.telegram.call_args_list[1].args[0], "setChatMenuButton")
        self.assertEqual(self.bot.telegram.call_args_list[0].args[1]["scope"], {"type": "all_private_chats"})

    def test_download_menu_prompts_then_accepts_reply(self):
        with patch.object(self.bot.offline, "submit") as submit:
            self.bot.handle(self.message("/download"))
            submit.assert_not_called()
            self.assertTrue(self.bot.send.call_args.kwargs["reply_markup"]["force_reply"])
            self.assertIn("/115/Downloads", self.bot.send.call_args.args[1])
            reply = self.message(MAGNET)
            reply["message"]["reply_to_message"] = {"message_id": 123}
            self.bot.handle(reply)
            submit.assert_called_once_with(42, [MAGNET])

    def test_prompt_markup_sent_to_telegram(self):
        self.bot.telegram = Mock()
        Bot.send(self.bot, 42, "发送链接", reply_markup={"force_reply": True})
        self.bot.telegram.assert_called_once_with("sendMessage", {
            "chat_id": 42, "text": "发送链接", "reply_markup": {"force_reply": True},
        })

    def test_unauthorized_user_gets_no_prompt(self):
        self.bot.handle(self.message("/download", user=43))
        self.bot.send.assert_not_called()

    def submit(self):
        self.bot.offline.submit_lock.acquire()
        self.bot.offline._submit(42, [MAGNET])

    def test_submit_payload_and_restart(self):
        self.bot.api = Mock(return_value={"tasks": [{"id": "task1"}]})
        self.submit()
        self.assertEqual(self.bot.api.call_args.args, ("/api/fs/add_offline_download", {
            "path": "/115/Downloads", "urls": [MAGNET], "tool": "115 Cloud", "delete_policy": "delete_never"}))
        self.bot.api.assert_called_once()
        self.assertNotIn("before", self.bot.offline.jobs["task1"])
        restored = Bot(self.env)
        self.assertIn("task1", restored.offline.jobs)
        self.assertNotIn(MAGNET, restored.offline.state_file.read_text())

    def test_no_retry_on_uncertain_submission(self):
        self.bot.api = Mock(side_effect=RequestError("HTTP 502"))
        self.submit()
        self.assertEqual(self.bot.api.call_count, 1)
        self.assertEqual(self.bot.offline.jobs, {})
        self.assertIn("提交未确认", self.bot.send.call_args.args[1])

    def test_missing_task_id_is_not_completion(self):
        self.bot.api = Mock(return_value={"tasks": None})
        self.submit()
        self.assertIn("未返回", self.bot.send.call_args.args[1])
        self.assertFalse(self.bot.offline.jobs)

    def create_job(self):
        self.bot.api = Mock(return_value={"tasks": [{"id": "task1"}]})
        self.submit()

    def test_completion_refreshes_task_destination(self):
        self.create_job()
        # Previously persisted jobs may still contain a directory snapshot.
        self.bot.offline.jobs["task1"]["before"] = ["old"]
        self.bot.api = Mock(return_value={"state": 2})
        self.bot.offline.check()
        self.assertEqual(self.bot.api.call_count, 2)
        self.bot.api.assert_called_with("/api/fs/list", {"path": "/115/Downloads", "password": "", "page": 1, "per_page": 1, "refresh": True})
        self.assertFalse(self.bot.offline.jobs)
        self.assertIn("已完成", self.bot.send.call_args.args[1])
        self.assertIn("已刷新", self.bot.send.call_args.args[1])

    def test_completion_refresh_failure_does_not_resubmit(self):
        self.create_job()
        self.bot.api = Mock(side_effect=[{"state": 2}, RequestError("HTTP 500")])
        self.bot.offline.check()
        self.assertFalse(self.bot.offline.jobs)
        self.assertIn("已完成", self.bot.send.call_args.args[1])
        self.assertIn("/refresh", self.bot.send.call_args.args[1])
        self.assertEqual(self.bot.api.call_count, 2)

    def test_refresh_command_and_authorization(self):
        with patch.object(self.bot.offline, "manual_refresh") as refresh:
            self.bot.handle(self.message("/refresh", user=43))
            self.bot.handle(self.message("/refresh", kind="group"))
            refresh.assert_not_called()
            self.bot.handle(self.message("/refresh"))
            refresh.assert_called_once_with(42)

    def test_manual_refresh_reports_failure_and_releases_lock(self):
        self.bot.offline.refresh_lock.acquire()
        self.bot.api = Mock(side_effect=RequestError("HTTP 500"))
        self.bot.offline._manual_refresh(42)
        self.assertFalse(self.bot.offline.refresh_lock.locked())
        self.assertIn("刷新失败", self.bot.send.call_args.args[1])

    def test_manual_refresh_requires_config(self):
        self.bot.offline.path = ""
        self.bot.api = Mock()
        self.bot.offline.manual_refresh(42)
        self.bot.api.assert_not_called()
        self.assertIn("OFFLINE_DOWNLOAD_PATH", self.bot.send.call_args.args[1])

    def test_retryable_task_state_is_not_failure(self):
        self.create_job()
        self.bot.api = Mock(return_value={"state": 5, "error": "sensitive"})
        self.bot.send.reset_mock()
        self.bot.offline.check()
        self.assertIn("task1", self.bot.offline.jobs)
        self.bot.send.assert_not_called()

    def test_failed_task_does_not_refresh_or_echo_error(self):
        self.create_job()
        self.bot.api = Mock(return_value={"state": 7, "error": "sensitive"})
        self.bot.offline.check()
        self.bot.api.assert_called_once()
        self.assertNotIn("sensitive", self.bot.send.call_args.args[1])

    def test_status_failure_keeps_task_for_retry(self):
        self.create_job()
        self.bot.api = Mock(side_effect=RequestError("HTTP 500"))
        self.bot.offline.check()
        self.assertIn("task1", self.bot.offline.jobs)

    def test_unconfigured_download_does_not_break_sync(self):
        self.env.pop("OFFLINE_DOWNLOAD_PATH")
        bot = Bot(self.env)
        bot.send = Mock()
        bot.offline.submit(42, [MAGNET])
        self.assertIn("OFFLINE_DOWNLOAD_PATH", bot.send.call_args.args[1])

    def test_invalid_path(self):
        with self.assertRaises(ValueError):
            Bot(dict(self.env, OFFLINE_DOWNLOAD_PATH="/115/../other"))


if __name__ == "__main__":
    unittest.main()
