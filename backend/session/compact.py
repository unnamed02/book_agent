import asyncio
import redis.asyncio as redis
import os
import json
import logging
from typing import List
from sqlalchemy.dialects.postgresql import insert
from utils.models import get_db_manager, ConversationArchive

logger = logging.getLogger(__name__)

# --- 提取常量 ---
KEEP_LATEST_COUNT = 20          # Redis 中保留的最新消息数
COMPACT_THRESHOLD = KEEP_LATEST_COUNT + 200  # 触发 Compact 的最小消息数 (220)


async def upsert_messages_to_db(db, session_id: str, messages: List):
    """
    使用 PostgreSQL Upsert 将消息插入或追加到数据库，并立即提交
    注意：db session 从外部传入，减少连接创建开销
    """
    if messages and isinstance(messages[0], str):
        messages = [json.loads(m) for m in messages]

    stmt = insert(ConversationArchive).values(
        session_id=session_id,
        messages=messages
    )

    stmt = stmt.on_conflict_do_update(
        index_elements=['session_id'],
        set_={
            'messages': ConversationArchive.messages.op('||')(stmt.excluded.messages)
        }
    )

    await db.execute(stmt)
    await db.commit()  # 单条提交，保证原子性落盘


async def compact_redis_to_db():
    logger.info("开始 Redis compact 任务...")
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        redis_client = await redis.from_url(redis_url, encoding="utf-8", decode_responses=True)

        keys = await redis_client.smembers('needs_compact_list')
        if not keys:
            await redis_client.aclose()
            logger.info("Compact 任务完成")
            return 0

        archived_count = 0
        db_manager = get_db_manager()
        
        # 外层开启 DB Session，整个循环复用同一个连接
        async with db_manager.async_session_maker() as db:
            for key in keys:
                try:
                    session_id = key.replace('conversation:', '')
                    list_len = await redis_client.llen(key)

                    if list_len < COMPACT_THRESHOLD:
                        await redis_client.srem('needs_compact_list', key)
                        continue

                    # 提取旧消息
                    messages_to_archive = await redis_client.lrange(key, 0, list_len - KEEP_LATEST_COUNT - 1)
                    if not messages_to_archive:
                        continue

                    # 传入 db 参数进行 Upsert
                    await upsert_messages_to_db(db, session_id, messages_to_archive)

                    # DB 提交成功后，再清理 Redis
                    await redis_client.ltrim(key, -KEEP_LATEST_COUNT, -1)
                    await redis_client.srem('needs_compact_list', key)

                    archived_count += 1
                    logger.info(f"已归档会话: {session_id}，保留最后 {KEEP_LATEST_COUNT} 条")

                except Exception as e:
                    logger.error(f"归档会话失败 {key}: {e}")
                    continue

        remaining = await redis_client.scard('needs_compact_list')
        await redis_client.aclose()
        logger.info(f"Compact 任务完成，归档 {archived_count} 个会话，剩余 {remaining} 个待处理")
        return archived_count

    except Exception as e:
        logger.error(f"Compact 任务失败: {e}")
        return 0


async def merge_archive_sessions():
    logger.info("开始处理合并归档队列...")
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        redis_client = await redis.from_url(redis_url, encoding="utf-8", decode_responses=True)

        keys = await redis_client.smembers('merge_archive_list')
        if not keys:
            await redis_client.aclose()
            return 0

        merged_count = 0
        db_manager = get_db_manager()

        # 外层开启 DB Session
        async with db_manager.async_session_maker() as db:
            for key in keys:
                try:
                    session_id = key.replace('conversation:', '')
                    current_messages = await redis_client.lrange(key, 0, -1)
                    
                    if not current_messages:
                        await redis_client.srem('merge_archive_list', key)
                        continue

                    # 传入 db 参数进行 Upsert
                    await upsert_messages_to_db(db, session_id, current_messages)

                    # 彻底删除清理 Redis
                    await redis_client.delete(key)
                    await redis_client.srem('merge_archive_list', key)

                    merged_count += 1
                    logger.info(f"已合并归档会话: {session_id}")

                except Exception as e:
                    logger.error(f"合并归档会话失败 {key}: {e}")
                    continue

        await redis_client.aclose()
        logger.info(f"合并归档任务完成，归档 {merged_count} 个会话")
        return merged_count

    except Exception as e:
        logger.error(f"合并归档任务失败: {e}")
        return 0


async def run_compact_scheduler():
    """运行定时 compact 任务（每 10 分钟）"""
    while True:
        try:
            await merge_archive_sessions()
            await compact_redis_to_db()

        except Exception as e:
            logger.error(f"调度器错误: {e}")

        await asyncio.sleep(600)

if __name__ == "__main__":
    asyncio.run(run_compact_scheduler())