#!/usr/bin/env python3
"""
管理后台 CLI - 查看用户和消息记录
用法: cd backend && python cli.py
"""

import asyncio
import json
import os
import sys

# 加载环境变量
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


async def get_db():
    """获取数据库会话"""
    db_manager = get_db_manager()
    return db_manager.async_session_maker()


async def get_redis():
    """获取 Redis 连接"""
    try:
        import redis.asyncio as redis_lib
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        client = await redis_lib.from_url(redis_url, encoding="utf-8", decode_responses=True)
        await client.ping()
        return client
    except Exception:
        return None


async def list_users(db):
    """查询所有用户"""
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return result.scalars().all()


async def list_sessions(db, user_id):
    """查询用户的所有会话"""
    result = await db.execute(
        select(UserSession)
        .where(UserSession.user_id == user_id)
        .order_by(UserSession.last_active_at.desc())
    )
    return result.scalars().all()


async def get_messages(db, redis_client, session_id):
    """获取会话消息（Redis + 数据库归档）"""
    messages = []

    # 1. 从 Redis 获取活跃消息
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

    # 2. 从数据库获取归档消息
    result = await db.execute(
        select(ConversationArchive).where(ConversationArchive.session_id == session_id)
    )
    archive = result.scalar_one_or_none()
    if archive and archive.messages:
        # 归档消息可能和 Redis 重复，简单去重（按内容）
        existing_contents = {m.get("content", "") for m in messages}
        for m in archive.messages:
            if isinstance(m, dict) and m.get("content", "") not in existing_contents:
                messages.append(m)

    return messages


def print_users(users):
    """打印用户列表"""
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
    """打印会话列表"""
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


def print_messages(messages):
    """打印消息，支持上下滚动"""
    if not messages:
        console.print("[yellow]暂无消息[/yellow]")
        return

    lines = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        role = m.get("role", "unknown")
        content = m.get("content", "")
        if not content:
            continue

        if role == "user":
            lines.append(f"[bold blue]【用户】[/bold blue] {content}")
        elif role == "assistant":
            lines.append(f"[bold green]【AI】[/bold green] {content}")
        else:
            lines.append(f"[bold dim]【{role}】[/bold dim] {content}")
        lines.append("")

    text = Text.from_markup("\n".join(lines))
    panel = Panel(text, title=f"消息记录（共 {len(messages)} 条）", border_style="blue")

    # 使用系统 pager 支持上下滚动（Linux/Mac: less, Windows: more）
    with console.pager(styles=True):
        console.print(panel)


async def main():
    console.print("[bold cyan]=== AI馆员 管理后台 ===[/bold cyan]\n")

    db_manager = get_db_manager()
    async with db_manager.async_session_maker() as db:
        redis_client = await get_redis()
        if redis_client:
            console.print("[dim]Redis 已连接[/dim]")
        else:
            console.print("[dim]Redis 未连接，仅显示数据库归档消息[/dim]")

        # 获取所有用户
        users = await list_users(db)
        if not users:
            console.print("[yellow]数据库中没有用户记录[/yellow]")
            return

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

            # 查看用户会话
            while True:
                sessions = await list_sessions(db, user.user_id)
                console.clear()
                console.print(f"[bold cyan]用户: {user.user_id}[/bold cyan]")
                print_sessions(sessions)

                if not sessions:
                    console.input("\n按 Enter 返回...")
                    break

                s_choice = console.input("\n请选择会话序号 ([cyan]b[/cyan] 返回, [cyan]q[/cyan] 退出): ").strip().lower()
                if s_choice == "q":
                    return
                if s_choice == "b":
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

                # 查看消息
                messages = await get_messages(db, redis_client, session.session_id)
                console.clear()
                console.print(f"[bold cyan]用户: {user.user_id} | 会话: {session.session_id}[/bold cyan]\n")
                print_messages(messages)
                console.input("\n按 Enter 返回...")

    console.print("[dim]再见！[/dim]")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[dim]已退出[/dim]")
