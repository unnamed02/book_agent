"""
查看数据库中的用户和会话信息
"""
import asyncio
from models import get_db_manager, User, UserSession
from sqlalchemy import select


async def check_database():
    """查看数据库中的用户和会话数据"""
    print('=' * 50)
    print('Database User and Session Data')
    print('=' * 50)

    db_manager = get_db_manager()

    async with db_manager.async_session_maker() as session:
        # 查询用户
        result = await session.execute(select(User))
        users = result.scalars().all()
        print(f'\nUsers: {len(users)}')
        for user in users:
            print(f'  - {user.user_id}')
            print(f'    Created: {user.created_at}')
            print(f'    Updated: {user.updated_at}')

        # 查询会话
        result = await session.execute(select(UserSession))
        sessions = result.scalars().all()
        print(f'\nSessions: {len(sessions)}')
        for s in sessions:
            print(f'  - Session ID: {s.session_id}')
            print(f'    User ID: {s.user_id}')
            print(f'    Created: {s.created_at}')
            print(f'    Last Active: {s.last_active_at}')
            print()

    await db_manager.close()


if __name__ == "__main__":
    asyncio.run(check_database())
