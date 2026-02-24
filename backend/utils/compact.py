"""
Redis 数据定时 Compact 任务
每10分钟将 Redis 中的对话历史归档到数据库，保留最近10条消息
"""
import asyncio
import redis.asyncio as redis
import os
import json
import logging
from sqlalchemy import select
from utils.models import get_db_manager, ConversationArchive

logger = logging.getLogger(__name__)


async def compact_redis_to_db():
    """将 Redis 数据 compact 到数据库

    Returns:
        int: 剩余待处理的会话数量
    """
    logger.info("开始 Redis compact 任务...")

    try:
        # 连接 Redis（使用 decode_responses 自动解码）
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        redis_client = await redis.from_url(redis_url, decode_responses=True)
        await redis_client.ping()
        logger.info(f"Redis 连接成功: {redis_url}")

        # 从 needs_compact_list Set 中获取需要 compact 的会话键
        keys = await redis_client.smembers('needs_compact_list')
        logger.info(f"发现 {len(keys)} 个会话在 compact 队列中")

        if len(keys) == 0:
            await redis_client.aclose()
            return 0

        # 连接数据库
        db_manager = get_db_manager()
        async with db_manager.async_session_maker() as db:
            archived_count = 0

            for key in keys:
                try:
                    # 提取 session_id
                    session_id = key.replace('conversation:', '')

                    # 获取列表长度
                    list_len = await redis_client.llen(key)

                    # 只获取前面的消息（除了最后 20 条）
                    if list_len < 220:
                        # 消息太少，跳过并从队列移除
                        await redis_client.srem('needs_compact_list', key)
                        continue

                    messages_to_archive = await redis_client.lrange(key, 0, list_len - 21)

                    if not messages_to_archive:
                        logger.warning(f"获取会话消息失败: {session_id}")
                        continue

                    # 将 Redis 字符串列表 parse 成对象列表
                    messages_to_archive = [json.loads(m) for m in messages_to_archive]

                    # 保存到数据库（直接传 List，SQLAlchemy 自动处理 JSONB 序列化）
                    archive = ConversationArchive(
                        session_id=session_id,
                        messages=messages_to_archive
                    )
                    db.add(archive)

                    # 保留最近 20 条消息（5 轮对话）
                    await redis_client.ltrim(key, -20, -1)

                    # 从 compact 队列中移除
                    await redis_client.srem('needs_compact_list', key)

                    archived_count += 1
                    logger.info(f"已归档会话: {session_id} ({len(messages_to_archive)} 条消息，保留最后 20 条)")

                except Exception as e:
                    logger.error(f"归档会话失败 {key}: {e}")
                    continue

            # 提交数据库事务
            if archived_count > 0:
                await db.commit()
                logger.info(f"成功归档 {archived_count} 个会话")
            else:
                logger.info(f"没有需要归档的会话")

        # 获取剩余待处理数量
        remaining = await redis_client.scard('needs_compact_list')

        await redis_client.aclose()
        await db_manager.close()

        logger.info(f"Compact 任务完成，剩余 {remaining} 个会话待处理")
        return archived_count  # 返回归档数量而不是剩余数量

    except Exception as e:
        logger.error(f"Compact 任务失败: {e}")
        logger.info("Compact 任务完成")
        return 0


async def merge_archive_sessions():
    """处理合并归档队列：归档当前会话并合并所有历史记录"""
    logger.info("开始处理合并归档队列...")

    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        redis_client = await redis.from_url(redis_url, decode_responses=True)
        await redis_client.ping()

        # 获取合并归档队列
        keys = await redis_client.smembers('merge_archive_list')
        logger.info(f"发现 {len(keys)} 个会话在合并归档队列中")

        if len(keys) == 0:
            await redis_client.aclose()
            return 0

        db_manager = get_db_manager()
        async with db_manager.async_session_maker() as db:
            merged_count = 0

            for key in keys:
                try:
                    session_id = key.replace('conversation:', '')

                    # 获取当前会话的所有消息
                    current_messages = await redis_client.lrange(key, 0, -1)
                    if not current_messages:
                        logger.warning(f"会话 {session_id} 没有消息，跳过")
                        await redis_client.srem('merge_archive_list', key)
                        continue

                    # 将 Redis 字符串列表 parse 成对象列表
                    current_messages = [json.loads(m) for m in current_messages]

                    # 查询该 session_id 的所有历史归档记录
                    result = await db.execute(
                        select(ConversationArchive)
                        .where(ConversationArchive.session_id == session_id)
                        .order_by(ConversationArchive.archived_at)
                    )
                    old_archives = result.scalars().all()

                    # 合并所有历史消息
                    all_messages = []
                    for archive in old_archives:
                        try:
                            all_messages.extend(archive.messages)
                        except Exception as e:
                            logger.error(f"解析历史归档失败: {e}")

                    # 添加当前会话消息
                    all_messages.extend(current_messages)

                    # 保存合并后的归档（直接传 List，SQLAlchemy 自动处理 JSONB 序列化）
                    merged_archive = ConversationArchive(
                        session_id=session_id,
                        messages=all_messages
                    )
                    db.add(merged_archive)

                    # 删除旧的归档记录
                    for archive in old_archives:
                        await db.delete(archive)

                    # 删除 Redis 中的会话数据
                    await redis_client.delete(key)

                    # 从队列中移除
                    await redis_client.srem('merge_archive_list', key)

                    merged_count += 1
                    logger.info(f"已合并归档会话: {session_id} (合并了 {len(old_archives)} 条历史记录，共 {len(all_messages)} 条消息)")
            
                except Exception as e:
                    logger.error(f"合并归档会话失败 {key}: {e}")
                    continue

            if merged_count > 0:
                await db.commit()
                logger.info(f"成功合并归档 {merged_count} 个会话")

        await redis_client.aclose()
        await db_manager.close()

        logger.info(f"合并归档任务完成")
        return merged_count

    except Exception as e:
        logger.error(f"合并归档任务失败: {e}")
        return 0


async def run_compact_scheduler():
    """运行定时 compact 任务（每 10 分钟）"""
    while True:
        try:
            # 先处理合并归档队列
            merged_count = await merge_archive_sessions()
            # 再处理普通 compact 队列
            compacted_count = await compact_redis_to_db()

            # 如果有任何归档操作，触发 Redis AOF 重写
            if merged_count > 0 or compacted_count > 0:
                try:
                    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
                    redis_client = await redis.from_url(redis_url, decode_responses=True)
                    await redis_client.bgrewriteaof()
                    logger.info("已触发 Redis AOF 重写")
                    await redis_client.aclose()
                except Exception as e:
                    logger.warning(f"触发 AOF 重写失败: {e}")

        except Exception as e:
            logger.error(f"调度器错误: {e}")

        # 等待 10 分钟
        await asyncio.sleep(600)


if __name__ == "__main__":
    asyncio.run(run_compact_scheduler())
