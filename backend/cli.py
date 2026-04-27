#!/usr/bin/env python3
"""
管理后台 CLI - 查看用户和消息记录
用法: cd backend && python cli.py

交互逻辑：
  - 任意界面按 q 回退到上一层
  - 消息查看按 j/k 上下翻页，按 q 返回会话列表
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
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from utils.models import get_db_manager, User, UserSession, ConversationArchive

console = Console()


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
        existing_contents = {m.get("content", "") for m in messages if isinstance(m, dict)}
        for m in archive.messages:
            if isinstance(m, dict) and m.get("content", "") not in existing_contents:
                messages.append(m)

    return messages


def print_users(users):
    if not users:
        console.print("[yellow]暂无用户[/yellow]")
        return

    table = Table(title="用户列表", show_header=True, header_style="bold magenta")
    table.add_column("序号", style="cyan", width=6, justify="center")
    table.add_column("用户ID", style="green")
    table.add_column("创建时间", style="yellow")
    table.add_column("更新时间", style="dim")

    for i, u in enumerate(users, 1):
        table.add_row(
            str(i),
            u.user_id,
            str(u.created_at)[:19] if u.created_at else "",
            str(u.updated_at)[:19] if u.updated_at else "",
        )
    console.print(table)
    console.print(f"[dim]共 {len(users)} 位用户[/dim]")


def print_sessions(sessions):
    if not sessions:
        console.print("[yellow]该用户暂无会话[/yellow]")
        return

    table = Table(title="会话列表", show_header=True, header_style="bold magenta")
    table.add_column("序号", style="cyan", width=6, justify="center")
    table.add_column("会话ID", style="green")
    table.add_column("创建时间", style="yellow")
    table.add_column("最后活跃", style="yellow")

    for i, s in enumerate(sessions, 1):
        table.add_row(
            str(i),
            s.session_id,
            str(s.created_at)[:19] if s.created_at else "",
            str(s.last_active_at)[:19] if s.last_active_at else "",
        )
    console.print(table)
    console.print(f"[dim]共 {len(sessions)} 个会话[/dim]")


def show_messages(messages):
    """分页显示消息，支持上下翻页，按 q 返回上一层"""
    if not messages:
        console.print("[yellow]暂无消息[/yellow]")
        console.input("\n按 Enter 继续...")
        return

    # 预处理消息文本
    lines = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        role = m.get("role", "unknown")
        content = m.get("content", "")
        if not content:
            continue
        if role == "user":
            lines.append(("user", f"【用户】 {content}"))
        elif role == "assistant":
            lines.append(("ai", f"【AI】 {content}"))
        else:
            lines.append(("other", f"【{role}】 {content}"))
        lines.append(("sep", ""))

    total_lines = len(lines)
    page_size = max(1, console.size.height - 8)  # 根据终端高度自适应
    top = 0

    while True:
        console.clear()
        console.print(f"[bold cyan]消息记录[/bold cyan] [dim]({len(messages)} 条，滚动 {top+1}-{min(top+page_size, total_lines)}/{total_lines})[/dim]\n")

        # 渲染当前窗口
        for i in range(top, min(top + page_size, total_lines)):
            role, text = lines[i]
            if role == "user":
                console.print(f"[bold blue]{text}[/bold blue]")
            elif role == "ai":
                console.print(f"[bold green]{text}[/bold green]")
            elif role == "sep":
                console.print("")
            else:
                console.print(f"[bold dim]{text}[/bold dim]")

        console.print("\n[dim cyan][j]↓下滚  [k]↑上滚  [q]返回[/dim cyan]")
        choice = console.input(": ").strip().lower()

        if choice == "q":
            return
        elif choice == "j":
            if top + page_size < total_lines:
                top += 3
        elif choice == "k":
            if top > 0:
                top -= 3
        # 其他按键忽略，继续循环


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

        # === 第一层：用户列表 ===
        while True:
            console.clear()
            print_users(users)
            choice = console.input("\n请选择用户序号 ([cyan]q[/cyan] 退出): ").strip().lower()
            if choice == "q":
                break

            try:
                idx = int(choice) - 1
                if idx < 0 or idx >= len(users):
                    console.print("[red]无效的序号[/red]")
                    console.input("按 Enter 继续...")
                    continue
            except ValueError:
                console.print("[red]请输入数字[/red]")
                console.input("按 Enter 继续...")
                continue

            user = users[idx]

            # === 第二层：会话列表 ===
            while True:
                sessions = await list_sessions(db, user.user_id)
                console.clear()
                console.print(f"[bold cyan]用户: {user.user_id}[/bold cyan]\n")
                print_sessions(sessions)

                if not sessions:
                    console.input("\n按 Enter 返回...")
                    break

                s_choice = console.input("\n请选择会话序号 ([cyan]q[/cyan] 返回): ").strip().lower()
                if s_choice == "q":
                    break

                try:
                    s_idx = int(s_choice) - 1
                    if s_idx < 0 or s_idx >= len(sessions):
                        console.print("[red]无效的序号[/red]")
                        console.input("按 Enter 继续...")
                        continue
                except ValueError:
                    console.print("[red]请输入数字[/red]")
                    console.input("按 Enter 继续...")
                    continue

                session = sessions[s_idx]

                # === 第三层：消息查看 ===
                messages = await get_messages(db, redis_client, session.session_id)
                console.clear()
                console.print(f"[bold cyan]用户: {user.user_id} | 会话: {session.session_id}[/bold cyan]\n")
                show_messages(messages)
                # show_messages 内部按 q 返回，继续回到会话列表

    console.print("[dim]再见！[/dim]")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[dim]已退出[/dim]")
