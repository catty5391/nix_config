import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from bot import Bot, RequestError
from offline import extract_links, parse_refresh_indices
from ui import messages

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
                        STATE_DIRECTORY=self.temp.name, OFFLINE_DOWNLOAD_PATH="/115/Downloads",
                        OFFLINE_REFRESH_RECURSIVE="true", OFFLINE_REFRESH_MAX_DIRS="100")
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
        self.assertIn("strm", [c["command"] for c in commands])
        self.assertIn("reset", [c["command"] for c in commands])
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

    def test_long_unicode_messages_preserve_content_and_reply_prompt(self):
        self.bot.telegram = Mock()
        # Include both an oversized single line and newline-separated content.
        text = "📂" * 2500 + "\n" + "电影 <A&B>\n" * 700
        Bot.send(self.bot, 42, text, reply_markup={"force_reply": True})
        payloads = [call.args[1] for call in self.bot.telegram.call_args_list]
        self.assertGreater(len(payloads), 1)
        self.assertEqual("".join(p["text"] for p in payloads), text)
        for payload in payloads:
            self.assertLessEqual(len(payload["text"].encode("utf-16-le")) // 2, 4000)
            self.assertNotIn("parse_mode", payload)
        self.assertTrue(all("reply_markup" not in p for p in payloads[:-1]))
        self.assertEqual(payloads[-1]["reply_markup"], {"force_reply": True})

    def test_long_directory_list_fits_page_and_keeps_all_choices(self):
        self.bot.api = Mock(return_value={"content": [
            {"name": f"{index:02d}-" + "电影📂<A&B>" * 20, "is_dir": True,
             "modified": "2026-10-04T00:00:00Z"}
            for index in range(55)
        ], "total": 55})
        self.bot.send = Bot.send.__get__(self.bot)
        self.bot.telegram = Mock()
        self.bot.handle(self.message("/strm"))
        payloads = [call.args[1] for call in self.bot.telegram.call_args_list]
        rendered = "".join(p["text"] for p in payloads)
        self.assertEqual(len(payloads), 1)
        self.assertLessEqual(len(rendered.encode("utf-16-le")) // 2, 4000)
        self.assertIn("共 55 个", rendered)
        self.assertIn("第 1 / 6 页", rendered)
        self.assertIn("10. 45-", rendered)
        self.assertNotIn("11. 44-", rendered)
        self.assertIn("2026-10-04 08:00", rendered)
        self.assertIn("/refresh 1", payloads[-1]["text"])
        self.assertEqual(len(self.bot.strm_choices[42]["items"]), 55)

    def prepare_pages(self, count=23):
        self.bot.api = Mock(return_value={"content": [
            {"name": f"folder-{index:02d}", "is_dir": True, "modified": "2026-10-04T00:00:00Z"}
            for index in range(count)
        ], "total": count})
        self.bot.handle(self.message("/strm"))
        self.bot.telegram = Mock()
        return self.bot.strm_choices[42]["token"]

    def callback(self, token, page, user=42, kind="private"):
        return {"callback_query": {"id": "query-id", "from": {"id": user},
                "message": {"message_id": 100, "chat": {"id": 42, "type": kind}},
                "data": f"strm:{token}:{page}"}}

    def test_paging_uses_stable_snapshot_and_global_refresh_number(self):
        token = self.prepare_pages()
        self.bot.handle(self.callback(token, 1))
        calls = self.bot.telegram.call_args_list
        self.assertEqual(calls[0].args[0], "answerCallbackQuery")
        self.assertEqual(calls[1].args[0], "editMessageText")
        payload = calls[1].args[1]
        self.assertEqual(payload["message_id"], 100)
        self.assertIn("第 2 / 3 页", payload["text"])
        self.assertIn("11. folder-12", payload["text"])
        self.assertIn("20. folder-03", payload["text"])
        self.assertNotIn("21. folder-02", payload["text"])
        buttons = payload["reply_markup"]["inline_keyboard"][0]
        self.assertEqual([b["callback_data"] for b in buttons], [f"strm:{token}:0", f"strm:{token}:2"])
        self.bot.api.assert_called_once()
        with patch.object(self.bot.offline, "manual_refresh") as refresh:
            self.bot.handle(self.message("/refresh 11"))
            refresh.assert_called_once_with(42, "/strm/folder-12", parent="/strm")

    def test_last_page_and_single_page_buttons(self):
        token = self.prepare_pages()
        self.bot.handle(self.callback(token, 2))
        payload = self.bot.telegram.call_args.args[1]
        self.assertIn("21. folder-02", payload["text"])
        self.assertIn("23. folder-00", payload["text"])
        self.assertEqual(len(payload["reply_markup"]["inline_keyboard"][0]), 1)
        self.assertEqual(payload["reply_markup"]["inline_keyboard"][0][0]["callback_data"], f"strm:{token}:1")
        self.prepare_pages(10)
        self.assertEqual(self.bot.send.call_args.kwargs["reply_markup"], messages.reset_buttons(self.bot.reset_token))

    def test_reset_remains_available_while_directory_worker_is_blocked(self):
        entered = threading.Event()
        release = threading.Event()

        def blocked_listing(chat_id):
            entered.set()
            release.wait(3)

        self.bot.telegram = Mock()
        with patch.object(self.bot, "show_strm_directories", side_effect=blocked_listing):
            worker = threading.Thread(target=self.bot.command_worker, daemon=True)
            worker.start()
            try:
                self.bot.dispatch(self.message("/strm"))
                self.assertTrue(entered.wait(1))
                self.bot.dispatch(self.message("/reset"))
                self.assertTrue(self.bot.stop.is_set())
                self.assertTrue(self.bot.restart_requested)
            finally:
                self.bot.stop.set()
                release.set()
                worker.join(2)
            self.assertFalse(worker.is_alive())

    def test_reset_buttons_require_current_token_and_authorization(self):
        self.bot.telegram = Mock()
        for user, kind, token in ((43, "private", self.bot.reset_token),
                                  (42, "group", self.bot.reset_token),
                                  (42, "private", "old-token")):
            update = self.callback("unused", 0, user=user, kind=kind)
            update["callback_query"]["data"] = f"reset:{token}"
            self.bot.dispatch(update)
            self.assertFalse(self.bot.restart_requested)
        for user, kind in ((43, "private"), (42, "group")):
            self.bot.dispatch(self.message("/reset", user=user, kind=kind))
            self.assertFalse(self.bot.restart_requested)
        update = self.callback("unused", 0)
        update["callback_query"]["data"] = f"reset:{self.bot.reset_token}"
        self.bot.dispatch(update)
        self.assertTrue(self.bot.restart_requested)

    def test_reset_survives_notification_failure_and_keeps_saved_jobs(self):
        self.create_job()
        before = self.bot.offline.state_file.read_bytes()
        self.bot.telegram = Mock(side_effect=RequestError("HTTP 502"))
        with self.assertLogs("telegram-openlist-sync", level="WARNING"):
            self.bot.request_reset(42, "query-id")
        self.assertTrue(self.bot.stop.is_set())
        self.assertTrue(self.bot.restart_requested)
        self.assertEqual(self.bot.offline.state_file.read_bytes(), before)
        restarted = Bot(self.env)
        self.assertIn("task1", restarted.offline.jobs)
        self.assertFalse(restarted.stop.is_set())
        self.assertNotEqual(restarted.reset_token, self.bot.reset_token)

    def test_reset_returns_restart_exit_code_and_persists_update_offset(self):
        update = dict(self.message("/reset"), update_id=100)
        self.bot.register_commands = Mock()
        self.bot.telegram = Mock(side_effect=lambda method, *args, **kwargs:
                                 [update] if method == "getUpdates" else True)
        with patch("bot.threading.Thread"):
            self.assertEqual(self.bot.run(), 75)
        self.assertEqual(self.bot.offset_file.read_text(), "101")
        self.assertEqual(Bot(self.env).offset, 101)

    def test_no_new_openlist_requests_after_reset(self):
        self.bot.telegram = Mock()
        self.bot.request_reset(42)
        with patch("bot.http_json") as request:
            with self.assertRaises(RequestError):
                self.bot.api("/api/fs/list", {"path": "/strm"})
            request.assert_not_called()

    def test_shutdown_during_refresh_keeps_download_monitoring(self):
        self.create_job()
        self.bot.api = Mock(return_value={"state": 2})

        def interrupted_refresh(path, task=None):
            self.bot.stop.set()
            raise RequestError("bot 正在重置或停止")

        with patch.object(self.bot.offline, "list_directories", side_effect=interrupted_refresh):
            self.bot.offline.check()
        self.assertIn("task1", Bot(self.env).offline.jobs)

    def test_cancel_during_blocked_request_stops_recursion_and_releases_lock(self):
        entered = threading.Event()
        release = threading.Event()
        self.bot.telegram = Mock()

        def blocked_request(endpoint, data):
            entered.set()
            release.wait(3)
            return {"content": [{"name": "child", "is_dir": True}], "total": 1001}

        self.bot.api = Mock(side_effect=blocked_request)
        self.bot.offline.refresh_lock.acquire()
        worker = threading.Thread(target=self.bot.offline._manual_refresh, args=(42,), daemon=True)
        worker.start()
        try:
            self.assertTrue(entered.wait(1))
            self.bot.dispatch(self.message("/cancel_refresh"))
            self.assertTrue(self.bot.offline.refresh_lock.locked())
            self.assertFalse(self.bot.stop.is_set())
            self.assertIn("已请求取消", self.bot.telegram.call_args.args[1]["text"])
        finally:
            release.set()
            worker.join(2)
        self.assertFalse(worker.is_alive())
        self.bot.api.assert_called_once()
        self.assertFalse(self.bot.offline.refresh_lock.locked())
        self.assertFalse(self.bot.offline.active_refreshes)
        self.assertIn("刷新已取消", self.bot.send.call_args.args[1])
        self.assertIn("已刷新目录数：1", self.bot.send.call_args.args[1])

    def test_cancel_button_is_task_specific_and_authorized(self):
        self.bot.telegram = Mock()

        def on_start(chat_id, text, reply_markup=None):
            if reply_markup is None:
                return
            data = reply_markup["inline_keyboard"][0][0]["callback_data"]
            for user, kind in ((43, "private"), (42, "group")):
                update = self.callback("unused", 0, user=user, kind=kind)
                update["callback_query"]["data"] = data
                self.bot.dispatch(update)
                self.assertFalse(next(iter(self.bot.offline.active_refreshes.values()))["cancel"].is_set())
            update = self.callback("unused", 0)
            update["callback_query"]["data"] = data
            self.bot.dispatch(update)
            self.old_cancel_data = data

        self.bot.send = Mock(side_effect=on_start)
        self.bot.api = Mock()
        self.bot.offline.refresh_lock.acquire()
        self.bot.offline._manual_refresh(42)
        self.bot.api.assert_not_called()
        self.assertIn("刷新已取消", self.bot.send.call_args.args[1])
        # An old button must not cancel a subsequent task, even in the same chat.
        self.bot.send = Mock()
        self.bot.api = Mock(return_value={"content": [], "total": 0})
        def old_button(chat_id, text, reply_markup=None):
            if reply_markup:
                update = self.callback("unused", 0)
                update["callback_query"]["data"] = self.old_cancel_data
                self.bot.dispatch(update)
        self.bot.send.side_effect = old_button
        self.bot.offline.refresh_lock.acquire()
        self.bot.offline._manual_refresh(42)
        self.assertIn("刷新完成", self.bot.send.call_args.args[1])
        self.bot.api.assert_called_once()

    def test_cancel_auto_refresh_does_not_retry_completed_download(self):
        self.create_job()
        def response(endpoint, data=None):
            if endpoint.startswith("/api/task/"):
                return {"state": 2}
            self.assertEqual(self.bot.offline.cancel_refresh(42), 1)
            return {"content": [{"name": "child", "is_dir": True}], "total": 1}
        self.bot.api = Mock(side_effect=response)
        self.bot.offline.check()
        self.assertEqual(self.bot.api.call_count, 2)
        self.assertIn("离线任务已完成 · 刷新已取消", self.bot.send.call_args.args[1])
        self.assertFalse(Bot(self.env).offline.jobs)
        self.bot.offline.check()
        self.assertEqual(self.bot.api.call_count, 2)

    def test_cancel_single_directory_request_on_timeout(self):
        self.bot.offline.refresh_recursive = "false"
        def timeout(endpoint, data):
            self.bot.offline.cancel_refresh(42)
            raise RequestError("HTTP 504")
        self.bot.api = Mock(side_effect=timeout)
        self.bot.offline.refresh_lock.acquire()
        self.bot.offline._manual_refresh(42)
        self.assertIn("刷新已取消", self.bot.send.call_args.args[1])
        self.assertNotIn("刷新失败", self.bot.send.call_args.args[1])
        self.assertFalse(self.bot.offline.refresh_lock.locked())

    def test_cancel_without_task_is_harmless(self):
        self.bot.telegram = Mock()
        self.bot.dispatch(self.message("/cancel_refresh"))
        self.assertIn("没有正在执行", self.bot.telegram.call_args.args[1]["text"])
        self.assertFalse(self.bot.restart_requested)

    def test_repeated_page_click_is_acknowledged_without_duplicate_edit(self):
        token = self.prepare_pages()
        self.bot.handle(self.callback(token, 1))
        self.bot.telegram.reset_mock()
        self.bot.handle(self.callback(token, 1))
        self.bot.telegram.assert_called_once_with("answerCallbackQuery", {"callback_query_id": "query-id"})

    def test_callback_requires_authorized_private_chat(self):
        token = self.prepare_pages()
        for user, kind in ((43, "private"), (42, "group")):
            self.bot.telegram.reset_mock()
            self.bot.handle(self.callback(token, 1, user=user, kind=kind))
            self.bot.telegram.assert_called_once()
            self.assertEqual(self.bot.telegram.call_args.args[0], "answerCallbackQuery")
            self.assertTrue(self.bot.telegram.call_args.args[1]["show_alert"])

    def test_expired_old_and_invalid_page_buttons_do_not_edit(self):
        old_token = self.prepare_pages()
        token = self.prepare_pages()
        for value, page in ((old_token, 1), (token, 3), (token, -1), (token, "bad"), (token, "²")):
            self.bot.telegram.reset_mock()
            self.bot.handle(self.callback(value, page))
            self.bot.telegram.assert_called_once()
            self.assertTrue(self.bot.telegram.call_args.args[1]["show_alert"])
        self.bot.strm_choices[42]["created"] -= 901
        self.bot.telegram.reset_mock()
        self.bot.handle(self.callback(token, 1))
        self.bot.telegram.assert_called_once()
        self.assertIn("已过期", self.bot.telegram.call_args.args[1]["text"])

    def test_empty_list_invalidates_old_choices(self):
        self.prepare_pages()
        self.bot.api.return_value = {"content": [], "total": 0}
        self.bot.handle(self.message("/strm"))
        self.assertNotIn(42, self.bot.strm_choices)

    def test_page_edit_failure_reports_retry_without_losing_choices(self):
        token = self.prepare_pages()
        self.bot.telegram.side_effect = [True, RequestError("HTTP 400")]
        with self.assertLogs("telegram-openlist-sync", level="WARNING"):
            self.bot.handle(self.callback(token, 1))
        self.assertIn("翻页失败", self.bot.send.call_args.args[1])
        self.assertEqual(self.bot.strm_choices[42]["token"], token)

    def test_display_time_handles_invalid_values(self):
        for value in (None, "not-a-date", "0000-01-01T00:00:00Z"):
            self.assertEqual(messages.modified_time(value), "未知")

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

    def create_batch(self, count=3, responses=None):
        self.bot.api = Mock(side_effect=responses if responses is not None else [
            {"tasks": [{"id": f"task{index}"}]} for index in range(count)])
        self.bot.offline.submit_lock.acquire()
        self.bot.offline._submit(42, [f"https://example.com/{index}" for index in range(count)])

    def batch_api(self, states):
        def response(endpoint, data=None):
            if endpoint.startswith("/api/task/"):
                return {"state": states[endpoint.split("tid=", 1)[1]]}
            if data["path"] == "/115/Downloads":
                return {"content": [
                    {"name": name, "is_dir": True, "modified": f"2026-10-0{day}T00:00:00Z"}
                    for name, day in (("older", 1), ("third", 2), ("second", 3), ("first", 4))
                ], "total": 4}
            return {"content": [], "total": 0}
        return Mock(side_effect=response)

    def test_batch_waits_for_all_links_and_resumes_after_restart(self):
        self.create_batch()
        self.assertEqual(len({j["batch_id"] for j in self.bot.offline.jobs.values()}), 1)
        self.bot.api = self.batch_api({"task0": 2, "task1": 1, "task2": 1})
        self.bot.offline.check()
        self.assertEqual(self.bot.api.call_count, 3)
        self.assertTrue(all(c.args[0].startswith("/api/task/") for c in self.bot.api.call_args_list))
        self.assertEqual(self.bot.offline.jobs["task0"]["outcome"], "success")
        self.bot = Bot(self.env)
        self.bot.send = Mock()
        # task0 need not be fetched again; its success was persisted before restart.
        self.bot.api = self.batch_api({"task1": 2, "task2": 2})
        self.bot.offline.check()
        paths = [c.args[1]["path"] for c in self.bot.api.call_args_list if c.args[0] == "/api/fs/list"]
        self.assertEqual(paths, ["/115/Downloads", "/115/Downloads/first", "/115/Downloads/second", "/115/Downloads/third"])
        self.assertFalse(self.bot.offline.jobs)
        self.assertFalse(Bot(self.env).offline.jobs)
        self.assertIn("本批成功 3 条链接", self.bot.send.call_args_list[0].args[1])
        calls = self.bot.api.call_count
        self.bot.offline.check()
        self.assertEqual(self.bot.api.call_count, calls)

    def test_batch_excludes_failed_and_canceled_links(self):
        self.create_batch()
        self.bot.api = self.batch_api({"task0": 2, "task1": 7, "task2": 4})
        self.bot.offline.check()
        paths = [c.args[1]["path"] for c in self.bot.api.call_args_list if c.args[0] == "/api/fs/list"]
        self.assertEqual(paths, ["/115/Downloads", "/115/Downloads/first"])
        self.assertIn("本批成功 1 条", self.bot.send.call_args.args[1])
        self.assertIn("监控超时 2 条", self.bot.send.call_args.args[1])

    def test_batch_excludes_unconfirmed_submission_and_duplicate_links(self):
        self.create_batch(responses=[{"tasks": [{"id": "task0"}]}, RequestError("HTTP 502"), {"tasks": []}])
        self.assertEqual(len(self.bot.offline.jobs), 1)
        self.bot.api = Mock()
        self.bot.offline.submit_lock.acquire()
        self.bot.offline._submit(42, ["https://example.com/0"])
        self.bot.api.assert_not_called()
        self.bot.api = self.batch_api({"task0": 2})
        self.bot.offline.check()
        self.assertEqual([c.args[1]["path"] for c in self.bot.api.call_args_list if c.args[0] == "/api/fs/list"],
                         ["/115/Downloads", "/115/Downloads/first"])

    def test_multiple_task_ids_for_one_link_count_as_one_directory(self):
        self.create_batch(1, responses=[{"tasks": [{"id": "task0"}, {"id": "task1"}]}])
        self.bot.api = self.batch_api({"task0": 2, "task1": 2})
        self.bot.offline.check()
        self.assertEqual([c.args[1]["path"] for c in self.bot.api.call_args_list if c.args[0] == "/api/fs/list"],
                         ["/115/Downloads", "/115/Downloads/first"])

    def test_batch_cannot_finish_while_submission_is_still_in_progress(self):
        submissions = 0
        def response(endpoint, data=None):
            nonlocal submissions
            self.assertEqual(endpoint, "/api/fs/add_offline_download")
            # The first accepted link must not be refreshed while another is being submitted.
            if submissions:
                self.bot.offline.check()
            result = {"tasks": [{"id": f"task{submissions}"}]}
            submissions += 1
            return result
        self.bot.api = Mock(side_effect=response)
        self.bot.offline.submit_lock.acquire()
        self.bot.offline._submit(42, ["https://example.com/a", "https://example.com/b"])
        self.assertEqual(submissions, 2)
        self.assertEqual(len(self.bot.offline.jobs), 2)
        self.assertFalse(self.bot.offline.submitting_batches)

    def test_batch_timeout_does_not_block_successful_links_forever(self):
        self.create_batch(2)
        self.bot.offline.jobs["task1"]["created"] = time.time() - self.bot.offline.timeout - 1
        self.bot.api = self.batch_api({"task0": 2})
        self.bot.offline.check()
        self.assertFalse(self.bot.offline.jobs)
        self.assertIn("本批成功 1 条", self.bot.send.call_args.args[1])
        self.assertIn("监控超时 1 条", self.bot.send.call_args.args[1])

    def test_auto_batch_cancel_stops_later_directories_without_retry(self):
        self.create_batch()
        responder = self.batch_api({"task0": 2, "task1": 2, "task2": 2})
        def response(endpoint, data=None):
            result = responder(endpoint, data)
            if data and data.get("path") == "/115/Downloads/first":
                self.bot.offline.cancel_refresh(42)
            return result
        self.bot.api = Mock(side_effect=response)
        self.bot.offline.check()
        self.assertEqual([c.args[1]["path"] for c in self.bot.api.call_args_list if c.args[0] == "/api/fs/list"],
                         ["/115/Downloads", "/115/Downloads/first"])
        self.assertFalse(Bot(self.env).offline.jobs)
        self.assertIn("刷新已取消", self.bot.send.call_args.args[1])

    def test_auto_batch_shares_limit_across_parent_and_selected_directories(self):
        self.create_batch()
        self.bot.offline.refresh_max_dirs = 2
        self.bot.api = self.batch_api({"task0": 2, "task1": 2, "task2": 2})
        self.bot.offline.check()
        self.assertEqual([c.args[1]["path"] for c in self.bot.api.call_args_list if c.args[0] == "/api/fs/list"],
                         ["/115/Downloads", "/115/Downloads/first"])
        self.assertIn("达到目录数量上限", self.bot.send.call_args.args[1])

    def test_auto_batch_with_fewer_available_directories_reports_shortfall(self):
        self.create_batch(5)
        self.bot.api = self.batch_api({f"task{i}": 2 for i in range(5)})
        self.bot.offline.check()
        paths = [c.args[1]["path"] for c in self.bot.api.call_args_list if c.args[0] == "/api/fs/list"]
        self.assertEqual(len(paths), 5)  # One parent listing, four actual child directories.
        self.assertIn("子目录只有 4 个", self.bot.send.call_args.args[1])

    def test_old_jobs_without_batch_metadata_keep_single_link_behavior(self):
        self.create_batch(2)
        for job in self.bot.offline.jobs.values():
            del job["batch_id"]
        self.bot.offline.save()
        self.bot = Bot(self.env)
        self.bot.send = Mock()
        self.bot.api = self.batch_api({"task0": 2, "task1": 1})
        self.bot.offline.check()
        self.assertEqual(set(self.bot.offline.jobs), {"task1"})
        self.assertEqual([c.args[1]["path"] for c in self.bot.api.call_args_list if c.args[0] == "/api/fs/list"],
                         ["/115/Downloads", "/115/Downloads/first"])

    def test_separate_messages_do_not_merge_refresh_batches(self):
        self.create_batch(2)
        self.bot.api = Mock(return_value={"tasks": [{"id": "separate"}]})
        self.submit()
        self.assertEqual(len({j["batch_id"] for j in self.bot.offline.jobs.values()}), 2)
        self.bot.api = self.batch_api({"task0": 2, "task1": 1, "separate": 2})
        self.bot.offline.check()
        self.assertEqual(set(self.bot.offline.jobs), {"task0", "task1"})
        self.assertEqual([c.args[1]["path"] for c in self.bot.api.call_args_list if c.args[0] == "/api/fs/list"],
                         ["/115/Downloads", "/115/Downloads/first"])

    def test_completion_refreshes_only_newest_child_tree(self):
        self.create_job()
        # Previously persisted jobs may still contain a directory snapshot.
        self.bot.offline.jobs["task1"]["before"] = ["old"]
        self.bot.api = Mock(side_effect=[
            {"state": 2},
            {"content": [
                {"name": "old", "is_dir": True, "modified": "2025-01-01T00:00:00Z"},
                {"name": "new", "is_dir": True, "modified": "2026-01-01T00:00:00Z"},
                {"name": "file.mkv", "is_dir": False, "modified": "2026-10-01T00:00:00Z"},
            ], "total": 3},
            {"content": [{"name": "child", "is_dir": True}], "total": 1},
            {"content": [], "total": 0},
        ])
        self.bot.offline.check()
        self.assertEqual(self.bot.api.call_count, 4)
        self.assertEqual([c.args[1]["path"] for c in self.bot.api.call_args_list[1:]],
                         ["/115/Downloads", "/115/Downloads/new", "/115/Downloads/new/child"])
        self.assertFalse(self.bot.offline.jobs)
        self.assertIn("已完成", self.bot.send.call_args.args[1])
        self.assertIn("已递归刷新", self.bot.send.call_args.args[1])
        self.assertIn("刷新目录数：2", self.bot.send.call_args.args[1])
        self.assertIn("推测", self.bot.send.call_args.args[1])

    def test_auto_refresh_uses_recorded_download_destination_for_old_jobs(self):
        self.create_job()
        self.bot.path = "/CustomSTRM"
        self.bot.offline.jobs["task1"]["path"] = "/115/OldDownloads"
        self.bot.api = Mock(side_effect=[{"state": 2}, {
            "content": [{"name": "a", "is_dir": True, "modified": "2026-10-04"}], "total": 1},
            {"content": [], "total": 0}])
        self.bot.offline.check()
        requests = self.bot.api.call_args_list[1:]
        self.assertEqual([call.args[1]["path"] for call in requests], ["/115/OldDownloads", "/115/OldDownloads/a"])
        self.assertTrue(all(call.args[1]["refresh"] for call in requests))
        self.assertIn("下载位置：/115/OldDownloads", self.bot.send.call_args_list[1].args[1])

    def test_auto_refresh_without_dated_directory_does_not_recurse(self):
        for content in ([], [{"name": "movie.mkv", "is_dir": False}],
                        [{"name": "unknown", "is_dir": True, "modified": "bad"}]):
            with self.subTest(content=content):
                self.create_job()
                self.bot.api = Mock(side_effect=[{"state": 2}, {"content": content, "total": len(content)}])
                self.bot.offline.check()
                self.assertEqual(self.bot.api.call_count, 2)
                self.assertIn("未执行子目录递归", self.bot.send.call_args.args[1])

    def test_auto_refresh_directory_budget_includes_parent_listing(self):
        self.create_job()
        self.bot.offline.refresh_max_dirs = 1
        self.bot.api = Mock(side_effect=[{"state": 2}, {
            "content": [{"name": "new", "is_dir": True, "modified": "2026-10-04"}], "total": 1}])
        self.bot.offline.check()
        self.assertEqual(self.bot.api.call_count, 2)
        self.assertIn("达到刷新上限", self.bot.send.call_args.args[1])

    def test_cancel_after_auto_selection_does_not_start_child_refresh(self):
        self.create_job()
        self.bot.api = Mock(side_effect=[{"state": 2}, {
            "content": [{"name": "new", "is_dir": True, "modified": "2026-10-04"}], "total": 1}])
        def cancel_when_selected(chat_id, text, **kwargs):
            if "自动刷新所选目录" in text:
                self.bot.offline.cancel_refresh(chat_id)
        self.bot.send.side_effect = cancel_when_selected
        self.bot.offline.check()
        self.assertEqual(self.bot.api.call_count, 2)
        self.assertIn("刷新已取消", self.bot.send.call_args.args[1])

    def test_completion_refresh_failure_does_not_resubmit(self):
        self.create_job()
        self.bot.api = Mock(side_effect=[{"state": 2}, RequestError("HTTP 500")])
        self.bot.offline.check()
        self.assertFalse(self.bot.offline.jobs)
        self.assertIn("已完成", self.bot.send.call_args.args[1])
        self.assertIn("/refresh", self.bot.send.call_args.args[1])
        self.assertEqual(self.bot.api.call_count, 2)

    def test_refresh_recurses_all_subdirectories_and_paginates(self):
        self.bot.api = Mock(side_effect=[
            {"content": [{"name": "a", "is_dir": True}, {"name": "b", "is_dir": True}], "total": 1001},
            {"content": [], "total": 1001},
            {"content": [{"name": "a2", "is_dir": True}], "total": 1},
            {"content": [], "total": 0},
            {"content": [], "total": 0},
        ])
        count, limited = self.bot.offline.refresh("/115/Downloads")
        self.assertEqual(count, 4)
        self.assertFalse(limited)
        requests = self.bot.api.call_args_list
        self.assertTrue(requests[0].args[1]["refresh"])
        self.assertFalse(requests[1].args[1]["refresh"])
        self.assertEqual(requests[1].args[1]["page"], 2)
        self.assertEqual({call.args[1]["path"] for call in requests}, {
            "/115/Downloads", "/115/Downloads/a", "/115/Downloads/b", "/115/Downloads/b/a2",
        })

    def test_refresh_directory_limit(self):
        self.bot.offline.refresh_max_dirs = 1
        self.bot.api = Mock(return_value={"content": [{"name": "child", "is_dir": True}], "total": 1})
        count, limited = self.bot.offline.refresh("/115/Downloads")
        self.assertEqual((count, limited), (1, True))

    def test_refresh_command_and_authorization(self):
        with patch.object(self.bot.offline, "manual_refresh") as refresh:
            self.bot.handle(self.message("/refresh", user=43))
            self.bot.handle(self.message("/refresh", kind="group"))
            refresh.assert_not_called()
            self.bot.handle(self.message("/refresh"))
            refresh.assert_not_called()
            self.assertIn("必须填写序号", self.bot.send.call_args.args[1])

    def test_refresh_batch_parsing(self):
        for value in ("1 3 5", "1,3,5", "1， 3, 5", " 1\n3\t5 "):
            self.assertEqual(parse_refresh_indices(value), [1, 3, 5])
        self.assertEqual(parse_refresh_indices("1 01 2,1"), [1, 2])
        self.assertEqual(parse_refresh_indices("1 2 3 4 5"), [1, 2, 3, 4, 5])

    def test_invalid_refresh_input_never_starts_any_task(self):
        self.prepare_pages()
        for value in ("", "  ", "0", "-1", "1.5", "²", "１２", "abc", "1 abc", "1-5", "1,,2",
                      "1,", ",1", "1 /strm", "1 99", "1 2 3 4 5 6", "9" * 300):
            with self.subTest(value=value), patch.object(self.bot.offline, "manual_refresh_batch") as refresh:
                self.bot.handle(self.message("/refresh " + value))
                refresh.assert_not_called()

    def test_batch_resolves_all_indices_and_preserves_order(self):
        self.prepare_pages()
        with patch.object(self.bot.offline, "manual_refresh_batch") as refresh:
            self.bot.handle(self.message("/refresh 11,1 11,3"))
            refresh.assert_called_once_with(42, ["/strm/folder-12", "/strm/folder-22", "/strm/folder-20"], parent="/strm")

    def test_expired_batch_and_unauthorized_batch_do_not_start(self):
        self.prepare_pages()
        with patch.object(self.bot.offline, "manual_refresh_batch") as refresh:
            self.bot.handle(self.message("/refresh 1 2", user=43))
            self.bot.handle(self.message("/refresh 1 2", kind="group"))
            self.bot.strm_choices[42]["created"] -= 901
            self.bot.handle(self.message("/refresh 1 2"))
            refresh.assert_not_called()

    def test_batch_recurses_roots_serially(self):
        self.bot.api = Mock(side_effect=[
            {"content": [{"name": "child", "is_dir": True}], "total": 1},
            {"content": [], "total": 0}, {"content": [], "total": 0},
        ])
        self.bot.offline.refresh_lock.acquire()
        self.bot.offline._manual_refresh(42, ["/strm/a", "/strm/b"])
        self.assertEqual([c.args[1]["path"] for c in self.bot.api.call_args_list],
                         ["/strm/a", "/strm/a/child", "/strm/b"])
        self.assertIn("刷新目录数：3", self.bot.send.call_args.args[1])
        self.assertFalse(self.bot.offline.refresh_lock.locked())

    def test_cancel_batch_prevents_later_roots(self):
        def cancel_first(endpoint, data):
            self.assertEqual(self.bot.offline.cancel_refresh(42), 1)
            return {"content": [], "total": 0}
        self.bot.api = Mock(side_effect=cancel_first)
        self.bot.offline.refresh_lock.acquire()
        self.bot.offline._manual_refresh(42, ["/strm/a", "/strm/b"])
        self.bot.api.assert_called_once()
        self.assertIn("刷新已取消", self.bot.send.call_args.args[1])
        self.assertFalse(self.bot.offline.refresh_lock.locked())
        self.assertFalse(self.bot.offline.active_refreshes)

    def test_batch_uses_shared_directory_limit(self):
        self.bot.offline.refresh_max_dirs = 2
        self.bot.api = Mock(return_value={"content": [], "total": 0})
        count, limited = self.bot.offline.run_refresh(["/strm/a", "/strm/b", "/strm/c"], 42)
        self.assertEqual((count, limited), (2, True))
        self.assertEqual(self.bot.api.call_count, 2)

    def test_manual_batch_refreshes_parent_once_without_traversing_siblings(self):
        self.bot.api = Mock(side_effect=[
            {"content": [{"name": "unselected", "is_dir": True}], "total": 1},
            {"content": [], "total": 0}, {"content": [], "total": 0},
        ])
        count, limited = self.bot.offline.run_refresh(["/strm/a", "/strm/b"], 42, parent="/strm")
        self.assertEqual((count, limited), (3, False))
        self.assertEqual([call.args[1]["path"] for call in self.bot.api.call_args_list],
                         ["/strm", "/strm/a", "/strm/b"])
        self.assertTrue(all(call.args[1]["refresh"] for call in self.bot.api.call_args_list))

    def test_parent_failure_or_cancellation_prevents_child_refresh(self):
        for cancel in (False, True):
            def response(endpoint, data):
                if cancel:
                    self.bot.offline.cancel_refresh(42)
                    return {"content": [], "total": 0}
                raise RequestError("HTTP 500")
            self.bot.api = Mock(side_effect=response)
            self.bot.offline.refresh_lock.acquire()
            self.bot.offline._manual_refresh(42, ["/strm/a", "/strm/b"], parent="/strm")
            self.bot.api.assert_called_once()
            self.assertEqual(self.bot.api.call_args.args[1]["path"], "/strm")
            self.assertFalse(self.bot.offline.refresh_lock.locked())
            self.assertIn("刷新已取消" if cancel else "刷新失败", self.bot.send.call_args.args[1])

    def test_parent_refresh_counts_towards_manual_batch_budget(self):
        self.bot.offline.refresh_max_dirs = 1
        self.bot.api = Mock(return_value={"content": [], "total": 0})
        self.assertEqual(self.bot.offline.run_refresh("/strm/a", 42, parent="/strm"), (1, True))
        self.bot.api.assert_called_once()

    def test_batch_failure_stops_remaining_roots_and_unlocks(self):
        self.bot.api = Mock(side_effect=RequestError("HTTP 500"))
        self.bot.offline.refresh_lock.acquire()
        self.bot.offline._manual_refresh(42, ["/strm/a", "/strm/b"])
        self.bot.api.assert_called_once()
        self.assertIn("后续目录未继续", self.bot.send.call_args.args[1])
        self.assertFalse(self.bot.offline.refresh_lock.locked())

    def test_overlapping_manual_batches_do_not_start_another_worker(self):
        self.bot.offline.refresh_lock.acquire()
        try:
            with patch("offline.threading.Thread") as worker:
                self.bot.offline.manual_refresh_batch(42, ["/strm/a", "/strm/b"])
                worker.assert_not_called()
        finally:
            self.bot.offline.refresh_lock.release()

    def test_strm_lists_directories_by_modified_time(self):
        self.bot.api = Mock(return_value={"content": [
            {"name": "old", "is_dir": True, "modified": "2024-01-01T00:00:00Z"},
            {"name": "new", "is_dir": True, "modified": "2025-01-01T00:00:00Z"},
            {"name": "movie.mkv", "is_dir": False, "modified": "2026-01-01T00:00:00Z"},
        ], "total": 3})
        self.bot.handle(self.message("/strm"))
        self.assertIn("1. new", self.bot.send.call_args.args[1])
        self.assertIn("2. old", self.bot.send.call_args.args[1])
        self.assertIn("/refresh 1", self.bot.send.call_args.args[1])
        self.assertEqual(self.bot.strm_choices[42]["items"], ["/strm/new", "/strm/old"])

    def test_strm_uses_scan_mount_instead_of_offline_directory(self):
        bot = Bot(dict(self.env, SCAN_PATH="/CustomSTRM"))
        bot.send = Mock()
        bot.api = Mock(return_value={"content": [], "total": 0})
        bot.handle(self.message("/strm"))
        self.assertEqual(bot.api.call_args.args[1]["path"], "/CustomSTRM")
        self.assertEqual(bot.path, "/CustomSTRM")

    def test_strm_does_not_require_offline_path(self):
        self.bot.offline.path = ""
        self.bot.api = Mock(return_value={"content": [], "total": 0})
        self.bot.handle(self.message("/strm"))
        self.bot.api.assert_called_once()
        self.assertEqual(self.bot.api.call_args.args[1]["path"], "/strm")

    def test_selected_strm_folder_does_not_refresh_sibling_or_root_tree(self):
        self.bot.api = Mock(side_effect=[
            {"content": [{"name": "selected", "is_dir": True, "modified": "2026-10-04"},
                         {"name": "other", "is_dir": True, "modified": "2026-01-01"},
                         {"name": "", "is_dir": True, "modified": "2026-10-05"}], "total": 3},
            {"content": [{"name": "other", "is_dir": True}], "total": 1},
            {"content": [{"name": "child", "is_dir": True}], "total": 1},
            {"content": [], "total": 0},
        ])
        self.bot.handle(self.message("/strm"))
        with patch("offline.threading.Thread") as worker:
            self.bot.handle(self.message("/refresh 1"))
            self.bot.offline._manual_refresh(*worker.call_args.kwargs["args"])
        self.assertEqual([call.args[1]["path"] for call in self.bot.api.call_args_list],
                         ["/strm", "/strm", "/strm/selected", "/strm/selected/child"])

    def test_missing_storage_diagnostic_omits_response_secrets(self):
        result = {"code": 500, "message": "storage not found; secret-token"}
        with patch("bot.http_json", return_value=result), self.assertLogs("telegram-openlist-sync", level="WARNING") as logs:
            with self.assertRaisesRegex(RequestError, "挂载路径及大小写"):
                self.bot.api("/api/fs/list", {"path": "/STRM"})
        self.assertIn("/api/fs/list", logs.output[0])
        self.assertIn("/STRM", logs.output[0])
        self.assertNotIn("secret-token", logs.output[0])

    def test_refresh_selected_strm_directory(self):
        with patch.object(self.bot.offline, "manual_refresh") as refresh:
            self.bot.strm_choices[42] = {"created": time.monotonic(), "items": ["/STRM/new"]}
            self.bot.handle(self.message("/refresh 1"))
            refresh.assert_called_once_with(42, "/STRM/new", parent="/strm")

    def test_expired_strm_choice_is_rejected(self):
        with patch.object(self.bot.offline, "manual_refresh") as refresh:
            self.bot.strm_choices[42] = {"created": time.monotonic() - 901, "items": ["/STRM/new"]}
            self.bot.handle(self.message("/refresh 1"))
            refresh.assert_not_called()
            self.assertIn("已过期", self.bot.send.call_args.args[1])

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
