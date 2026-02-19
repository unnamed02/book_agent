"""
Redis 数据定时 Compact 任务
每10分钟将 Redis 中的对话历史归档到数据库，保留最近10条消息
"""
import asyncio
import redis.asyncio as redis
import os
import json
import logging
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

                    # 将消息列表序列化为 JSON 字符串（SQLAlchemy 会自动转换为 JSONB）
                    archive_data = json.dumps(messages_to_archive, ensure_ascii=False)

                    # 保存到数据库
                    archive = ConversationArchive(
                        session_id=session_id,
                        messages=archive_data
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

        # 触发 Redis AOF 重写（后台异步执行）
        if archived_count > 0:
            try:
                await redis_client.bgrewriteaof()
                logger.info("已触发 Redis AOF 重写")
            except Exception as e:
                logger.warning(f"触发 AOF 重写失败: {e}")

        await redis_client.aclose()
        await db_manager.close()

        logger.info(f"Compact 任务完成，剩余 {remaining} 个会话待处理")
        return remaining

    except Exception as e:
        logger.error(f"Compact 任务失败: {e}")
        logger.info("Compact 任务完成")
        return 0


async def run_compact_scheduler():
    """运行定时 compact 任务（每 10 分钟）"""
    while True:
        try:
            await compact_redis_to_db()
        except Exception as e:
            logger.error(f"调度器错误: {e}")

        # 等待 10 分钟
        await asyncio.sleep(600)


if __name__ == "__main__":
    asyncio.run(run_compact_scheduler())
