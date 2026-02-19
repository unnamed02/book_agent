"""
Redis 交互式命令行工具
"""
import asyncio
import redis.asyncio as redis
import json
import os
import sys


def format_bytes(bytes_value):
    """格式化字节数为可读格式"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} TB"


async def show_memory(client):
    """显示内存使用情况"""
    info = await client.info('memory')
    used_memory = info.get('used_memory', 0)
    used_memory_human = info.get('used_memory_human', 'N/A')
    used_memory_rss = info.get('used_memory_rss', 0)
    used_memory_peak = info.get('used_memory_peak', 0)
    used_memory_peak_human = info.get('used_memory_peak_human', 'N/A')
    maxmemory = info.get('maxmemory', 0)
    maxmemory_human = info.get('maxmemory_human', 'N/A') if maxmemory > 0 else 'unlimited'

    print('\nMemory Usage:')
    print(f'  Current: {used_memory_human} ({format_bytes(used_memory)})')
    print(f'  RSS: {format_bytes(used_memory_rss)}')
    print(f'  Peak: {used_memory_peak_human} ({format_bytes(used_memory_peak)})')
    print(f'  Max: {maxmemory_human}')

    if maxmemory > 0:
        usage_percent = (used_memory / maxmemory) * 100
        print(f'  Usage: {usage_percent:.2f}%')


async def show_keys(client):
    """显示所有键统计"""
    db_info = await client.info('keyspace')
    total_keys = 0
    if 'db0' in db_info:
        total_keys = db_info['db0'].get('keys', 0)
    print(f'\nTotal Keys: {total_keys}')


async def list_sessions(client, limit=10):
    """列出会话"""
    keys = await client.keys('conversation:*')
    print(f'\nFound {len(keys)} conversation sessions:')

    if len(keys) == 0:
        print('  No session data')
        return

    total_messages = 0
    for i, key in enumerate(keys[:limit], 1):
        list_len = await client.llen(key)
        total_messages += list_len
        ttl = await client.ttl(key)
        ttl_str = 'no expiration' if ttl == -1 else f'{ttl // 3600}h {(ttl % 3600) // 60}m'
        print(f'  [{i}] {key} - {list_len} messages - {ttl_str}')

    if len(keys) > limit:
        print(f'  ... and {len(keys) - limit} more')

    print(f'\nTotal: {len(keys)} sessions, {total_messages} messages')


async def show_session(client, session_id):
    """显示会话详情"""
    key = f'conversation:{session_id}'
    list_len = await client.llen(key)

    if list_len == 0:
        print(f'\nSession not found: {session_id}')
        return

    print(f'\nSession: {session_id}')
    print(f'Messages: {list_len}')

    ttl = await client.ttl(key)
    if ttl > 0:
        print(f'Expires in: {ttl // 3600}h {(ttl % 3600) // 60}m')
    elif ttl == -1:
        print('No expiration')

    print('\nRecent messages:')
    start_index = max(0, list_len - 10)
    messages_json = await client.lrange(key, start_index, -1)

    for i, msg_json in enumerate(messages_json, start=start_index + 1):
        try:
            msg_data = json.loads(msg_json)
            msg_type = msg_data.get('type', 'unknown')
            content = msg_data.get('content', '')
            if len(content) > 80:
                content = content[:80] + '...'
            print(f'  [{i}] {msg_type}: {content}')
        except json.JSONDecodeError:
            print(f'  [{i}] Invalid JSON')

    if list_len > 10:
        print(f'  ... (showing last 10 of {list_len} messages)')


async def show_compact_queue(client):
    """显示 compact 队列"""
    compact_list = await client.smembers('needs_compact_list')
    print(f'\nCompact Queue: {len(compact_list)} sessions waiting')

    if compact_list:
        for i, key in enumerate(list(compact_list)[:10], 1):
            list_len = await client.llen(key)
            print(f'  [{i}] {key} - {list_len} messages')

        if len(compact_list) > 10:
            print(f'  ... and {len(compact_list) - 10} more')


def print_help():
    """打印帮助信息"""
    print('\nAvailable commands:')
    print('  memory              - Show memory usage')
    print('  keys                - Show total keys count')
    print('  list [limit]        - List sessions (default limit: 10)')
    print('  show <session_id>   - Show session details')
    print('  compact             - Show compact queue')
    print('  help                - Show this help')
    print('  exit                - Exit the tool')


async def main():
    """主函数"""
    print('=' * 60)
    print('Redis Interactive CLI Tool')
    print('=' * 60)

    try:
        # 连接 Redis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        client = await redis.from_url(redis_url, encoding='utf-8', decode_responses=True)
        await client.ping()
        print(f'\nConnected to: {redis_url}')
        print('Type "help" for available commands\n')

        while True:
            try:
                # 读取用户输入
                command = input('redis> ').strip()

                if not command:
                    continue

                parts = command.split()
                cmd = parts[0].lower()

                if cmd == 'exit' or cmd == 'quit':
                    print('Goodbye!')
                    break

                elif cmd == 'help':
                    print_help()

                elif cmd == 'memory':
                    await show_memory(client)

                elif cmd == 'keys':
                    await show_keys(client)

                elif cmd == 'list':
                    limit = int(parts[1]) if len(parts) > 1 else 10
                    await list_sessions(client, limit)

                elif cmd == 'show':
                    if len(parts) < 2:
                        print('Usage: show <session_id>')
                    else:
                        await show_session(client, parts[1])

                elif cmd == 'compact':
                    await show_compact_queue(client)

                else:
                    print(f'Unknown command: {cmd}')
                    print('Type "help" for available commands')

            except KeyboardInterrupt:
                print('\nUse "exit" to quit')
            except Exception as e:
                print(f'Error: {e}')

        await client.aclose()

    except Exception as e:
        print(f'Connection error: {e}')
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
