"""
查看 Redis 中保存的会话信息
"""
import asyncio
import redis.asyncio as redis
import json
import os


async def check_redis():
    """查看 Redis 中的会话数据"""
    print('=' * 50)
    print('Redis Session Data')
    print('=' * 50)

    try:
        # 连接 Redis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        client = await redis.from_url(redis_url, encoding='utf-8', decode_responses=True)
        await client.ping()
        print(f'\nRedis connected: {redis_url}\n')

        # 获取所有 conversation: 开头的键
        keys = await client.keys('conversation:*')

        print(f'Found {len(keys)} session records:\n')

        if len(keys) == 0:
            print('No session data')
        else:
            for key in keys:
                print(f'Key: {key}')

                # 获取 List 类型的数据
                list_len = await client.llen(key)
                if list_len > 0:
                    print(f'  Messages: {list_len}')

                    # 显示最近的10条消息
                    start_index = max(0, list_len - 10)
                    messages_json = await client.lrange(key, start_index, -1)

                    for i, msg_json in enumerate(messages_json, start=start_index + 1):
                        try:
                            msg_data = json.loads(msg_json)
                            msg_type = msg_data.get('type', 'unknown')
                            content = msg_data.get('content', '')
                            print(f'    [{i}] {msg_type}: {content}')
                        except json.JSONDecodeError:
                            print(f'    [{i}] Invalid JSON: {msg_json[:50]}...')

                    if list_len > 10:
                        print(f'    ... (showing last 10 of {list_len} messages)')

                # 获取 TTL
                ttl = await client.ttl(key)
                if ttl > 0:
                    hours = ttl // 3600
                    minutes = (ttl % 3600) // 60
                    print(f'  Expires in: {hours}h {minutes}m')

                print()

        await client.aclose()

    except Exception as e:
        print(f'Error: {e}')


if __name__ == "__main__":
    asyncio.run(check_redis())
