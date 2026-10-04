"""Plain-text message layouts; paths and names never become HTML/Markdown."""

from datetime import datetime, timedelta, timezone


ICONS = {"info": "ℹ️", "working": "⏳", "success": "✅", "warning": "⚠️", "error": "❌"}
DIRECTORY_PAGE_SIZE = 10


def card(title, *sections, icon="ℹ️"):
    return "\n\n".join([f"{icon} {title}", *(str(s) for s in sections if s)])


def notice(title, text, kind="info"):
    return card(title, text, icon=ICONS[kind])


def download_prompt(path):
    return card(
        "添加离线下载", f"📂 保存位置\n{path}",
        "请回复下载链接，每行一条，最多 20 条。\n支持：磁力 · ed2k · HTTP(S) 直链",
        "暂不支持 http://115cdn/ 链接。", icon="📥",
    )


def help_text():
    return card(
        "OpenList 小助手",
        "📥 离线下载\n/download — 添加下载链接\n/downloads — 查看下载配置与任务数量",
        "📂 目录刷新\n/strm — 按修改时间选择文件夹\n/refresh 1 3 5 — 批量刷新指定文件夹\n必须填写序号，用空格或逗号分隔，每批最多 5 个；重复序号自动去重。",
        "🔄 扫描同步\n/sync — 开始同步\n/status — 查看扫描状态",
        "🛠 恢复操作\n/reset — 重启 bot，清除卡住的操作与分页状态",
        "/cancel_refresh — 取消当前正在执行的目录刷新",
        "💡 直接发送链接也能下载，每行一条，最多 20 条。\n"
        "支持磁力、ed2k、HTTP(S) 直链；暂不支持 http://115cdn/。\n"
        "链接由 OpenList 下载工具处理，网页分享链接不保证支持。",
        "/help — 查看此说明", icon="👋",
    )


def scan_started(path):
    return card("开始同步", f"📂 扫描位置\n{path}", "完成后会通知你。查看进度：/status", icon="🔄")


def scan_status(data):
    state = "已完成" if data["is_done"] else "进行中"
    return card("同步状态", f"状态：{state}\n已扫描对象：{data.get('obj_count', 0)}", icon="📊")


def scan_complete(count):
    return card("同步完成", f"扫描对象：{count}", icon="✅")


def download_status(path, tool, count):
    return card("离线下载", f"📂 保存位置\n{path or '未配置'}",
                f"下载工具：{tool}\n正在跟踪：{count} 个任务", icon="📥")


def submitted(index, path):
    return card(f"第 {index} 条已提交", f"📂 保存位置\n{path}", "等待 OpenList 下载，完成后会通知你。", icon="📥")


def refresh_complete(path, count, limited, recursive=True, downloaded=False):
    scope = "已递归刷新目录" if recursive else "已刷新目录"
    title = "离线任务已完成" if downloaded else "目录刷新完成"
    return card(title, f"📂 {scope}\n{path}", f"刷新目录数：{count}",
                "⚠️ 达到目录数量上限，未继续递归。" if limited else "",
                icon="⚠️" if limited else "✅")


def modified_time(value):
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if stamp.tzinfo is not None:
            stamp = stamp.astimezone(timezone(timedelta(hours=8)))
        return stamp.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError, OverflowError):
        return "未知"


def display_name(value, limit=120):
    # Bound display length so a page can be edited as one Telegram message.
    text = str(value).replace("\n", " ").replace("\r", " ")
    return text if len(text) <= limit else text[:limit - 1] + "…"


def directory_list(root, directories, page=0):
    total = len(directories)
    pages = (total + DIRECTORY_PAGE_SIZE - 1) // DIRECTORY_PAGE_SIZE
    start = page * DIRECTORY_PAGE_SIZE
    rows = [f"{index}. {display_name(item['name'])}\n"
            f"   修改：{modified_time(item.get('modified'))}"
            for index, item in enumerate(directories[start:start + DIRECTORY_PAGE_SIZE], start + 1)]
    return card(
        "STRM 文件夹", f"位置：{display_name(root, 200)}\n最新修改在前 · 共 {total} 个\n第 {page + 1} / {pages} 页 · 每页 10 个\n时间：北京时间",
        "\n\n".join(rows),
        f"发送 /refresh 序号 刷新对应文件夹及其子目录。\n例如：/refresh {start + 1}\n支持多个序号（空格或逗号分隔），每批最多 5 个，不可留空。\n列表有效期 15 分钟，重新获取：/strm", icon="📂",
    )


def reset_buttons(token):
    return {"inline_keyboard": [[{"text": "🔄 Reset bot", "callback_data": f"reset:{token}"}]]}


def cancel_refresh_buttons(token):
    return {"inline_keyboard": [[{"text": "⏹ 取消本次刷新", "callback_data": f"cancel_refresh:{token}"}]]}


def refresh_cancelled(path, count, downloaded=False):
    title = "离线任务已完成 · 刷新已取消" if downloaded else "刷新已取消"
    return notice(title, f"目录：{path}\n已刷新目录数：{count}\n已完成的刷新保留，后续目录不再继续。", "warning")


def reset_notice():
    return notice("正在重启 bot", "约 10 秒后可重新发送 /start。\n"
                  "已保存的下载任务会继续跟踪，等待中的命令需重新发送。\n"
                  "OpenList 已接收的任务仍会运行；若刚才正在提交链接，请先到后台确认结果，避免重复提交。", "working")


def directory_buttons(token, page, total, reset_token=None):
    buttons = []
    if page > 0:
        buttons.append({"text": "⬅️ 上一页", "callback_data": f"strm:{token}:{page - 1}"})
    if (page + 1) * DIRECTORY_PAGE_SIZE < total:
        buttons.append({"text": "下一页 ➡️", "callback_data": f"strm:{token}:{page + 1}"})
    rows = [buttons] if buttons else []
    if reset_token:
        rows.extend(reset_buttons(reset_token)["inline_keyboard"])
    return {"inline_keyboard": rows}


def chunks(text):
    """Keep every character, preferring newline boundaries within 4000 UTF-16 units."""
    start = 0
    while start < len(text):
        end = start
        units = 0
        newline = None
        while end < len(text):
            width = 2 if ord(text[end]) > 0xFFFF else 1
            if units + width > 4000:
                break
            units += width
            end += 1
            if text[end - 1] == "\n":
                newline = end
        if end < len(text) and newline is not None:
            end = newline
        yield text[start:end]
        start = end
