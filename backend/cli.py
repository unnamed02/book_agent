#!/usr/bin/env python3
"""
管理后台 CLI - 查看用户和消息记录
用法: cd backend && python cli.py

交互：
  - ↑/↓ 方向键选择/滚动
  - Enter 确认进入
  - q 返回上一层（任意界面）
"""

import asyncio
import json
import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from sqlalchemy import select
from rich.console import Console
from rich.text import Text
from rich.panel import Panel

from utils.models import get_db_manager, User, UserSession, ConversationArchive

console = Console()


def read_key():
    """读取单个按键，跨平台支持方向键"""
    import readchar
    c = readchar.readchar()
    if c == '\x03':
        raise KeyboardInterrupt
    if c in ('\x00', '\xe0'):
        # Windows 特殊键
        c2 = readchar.readchar()
        if c2 == 'H':
            return 'UP'
        if c2 == 'P':
            return 'DOWN'
        return f'SPEC_{c2}'
    if c == '\x1b':
        # Unix Escape 序列
        c2 = readchar.readchar()
        if c2 == '[':
            c3 = readchar.readchar()
            if c3 == 'A':
                return 'UP'
            if c3 == 'B':
                return 'DOWN'
            return f'ESC_[{c3}'
        return f'ESC_{c2}'
    return c


def get_page_size():
    """获取终端可显示行数"""
    try:
        return max(5, console.size.height - 4)
    except Exception:
        try:
            return max(5, os.get_terminal_size().lines - 4)
        except Exception:
            return 20


async def get_redis():
    try:
        import redis.asyncio as redis_lib
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        client = await redis_lib.from_url(redis_url, encoding="utf-8", decode_responses=True)
        await client.ping()
        return client
    except Exception:
        return None


async def list_users(db):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return result.scalars().all()


async def list_sessions(db, user_id):
    result = await db.execute(
        select(UserSession)
        .where(UserSession.user_id == user_id)
        .order_by(UserSession.last_active_at.desc())
    )
    return result.scalars().all()


async def get_messages(db, redis_client, session_id):
    messages = []

    if redis_client:
        try:
            key = f"conversation:{session_id}"
            raw_msgs = await redis_client.lrange(key, 0, -1)
            for m in raw_msgs:
                if m and m.strip():
                    try:
                        messages.append(json.loads(m))
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            console.print(f"[red]Redis 读取失败: {e}[/red]")

    result = await db.execute(
        select(ConversationArchive).where(ConversationArchive.session_id == session_id)
    )
    archive = result.scalar_one_or_none()
    if archive and archive.messages:
        existing = {m.get("content", "") for m in messages if isinstance(m, dict)}
        for m in archive.messages:
            if isinstance(m, dict) and m.get("content", "") not in existing:
                messages.append(m)

    return messages


def select_list(items, title):
    """
    列表选择器
    items: [(display_text, data), ...]
    返回选中的 data 或 None（按 q）
    """
    if not items:
        console.print("[yellow]暂无数据[/yellow]")
        console.input("按 Enter 继续...")
        return None

    selected = 0
    while True:
        console.clear()
        console.print(f"[bold cyan]{title}[/bold cyan]  [dim](↑↓选择 Enter确认 q返回)[/dim]\n")

        for i, (display, _) in enumerate(items):
            if i == selected:
                console.print(f" [reverse bold]> {display}[/reverse bold]")
            else:
                console.print(f"   {display}")

        key = read_key()
        if key == 'UP':
            selected = max(0, selected - 1)
        elif key == 'DOWN':
            selected = min(len(items) - 1, selected + 1)
        elif key in ('\r', '\n'):
            return items[selected][1]
        elif key == 'q':
            return None


def scroll_view(lines, title):
    """
    内容滚动查看器
    lines: list of Text 或 str
    """
    if not lines:
        console.print("[yellow]暂无内容[/yellow]")
        console.input("按 Enter 继续...")
        return

    top = 0
    page_size = get_page_size()
    total = len(lines)

    while True:
        console.clear()
        console.print(f"[bold cyan]{title}[/bold cyan]  [dim](↑↓滚动 q返回)[/dim]\n")

        for i in range(top, min(top + page_size, total)):
            line = lines[i]
            if isinstance(line, Text):
                console.print(line)
            else:
                console.print(line)

        console.print(f"\n[dim]行 {top + 1}-{min(top + page_size, total)} / {total}[/dim]")

        key = read_key()
        if key == 'UP':
            top = max(0, top - 1)
        elif key == 'DOWN':
            if top + page_size < total:
                top += 1
        elif key == 'q':
            return


def format_messages(messages):
    """把消息格式化成可滚动的 Text 列表"""
    lines = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        role = m.get("role", "unknown")
        content = m.get("content", "")
        if not content:
            continue

        if role == "user":
            prefix = "[bold blue]【用户】[/bold blue] "
            indent = "        "
        elif role == "assistant":
            prefix = "[bold green]【AI】[/bold green] "
            indent = "      "
        else:
            prefix = f"[bold dim]【{role}】[/bold dim] "
            indent = "        "

        first = True
        for line in content.split('\n'):
            if line.strip():
                if first:
                    lines.append(Text.from_markup(prefix + line))
                    first = False
                else:
                    lines.append(Text.from_markup(indent + line))
        lines.append(Text(""))
    return lines


async def main():
    console.print("[bold cyan]=== AI馆员 管理后台 ===[/bold cyan]\n")

    db_manager = get_db_manager()
    async with db_manager.async_session_maker() as db:
        redis_client = await get_redis()
        if redis_client:
            console.print("[dim]Redis 已连接[/dim]\n")
        else:
            console.print("[dim]Redis 未连接，仅显示数据库归档消息[/dim]\n")

        users = await list_users(db)
        if not users:
            console.print("[yellow]数据库中没有用户记录[/yellow]")
            return

        # 准备用户列表项
        user_items = []
        for u in users:
            created = str(u.created_at)[:19] if u.created_at else ""
            display = f"{u.user_id:20s}  {created}"
            user_items.append((display, u))

        # === 第一层：选择用户 ===
        while True:
            user = select_list(user_items, "用户列表")
            if user is None:
                break

            sessions = await list_sessions(db, user.user_id)
            if not sessions:
                console.print("[yellow]该用户暂无会话[/yellow]")
                console.input("按 Enter 继续...")
                continue

            # 准备会话列表项
            session_items = []
            for s in sessions:
                last = str(s.last_active_at)[:19] if s.last_active_at else ""
                display = f"{s.session_id:30s}  {last}"
                session_items.append((display, s))

            # === 第二层：选择会话 ===
            while True:
                session = select_list(session_items, f"用户: {user.user_id}")
                if session is None:
                    break

                messages = await get_messages(db, redis_client, session.session_id)
                lines = format_messages(messages)

                # === 第三层：查看消息 ===
                scroll_view(lines, f"用户: {user.user_id} | 会话: {session.session_id}")
                # 按 q 返回会话列表

    console.print("[dim]再见！[/dim]")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[dim]已退出[/dim]")
