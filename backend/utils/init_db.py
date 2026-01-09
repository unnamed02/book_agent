"""
数据库初始化脚本
用于创建所有表和索引
"""

import asyncio
import sys
from utils.models import DatabaseManager, Base, get_db_manager
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def init_database():
    """初始化数据库"""
    try:
        logger.info("开始初始化数据库...")

        # 获取数据库管理器
        db_manager = get_db_manager()

        # 创建所有表
        await db_manager.init_db()

        logger.info("✅ 数据库表创建成功!")
        logger.info("已创建的表:")
        logger.info("  - user_preferences (用户偏好表)")
        logger.info("  - recommendation_history (推荐历史表)")
        logger.info("  - feedback_records (反馈记录表)")
        logger.info("  - reading_progress (阅读进度表)")

        # 关闭连接
        await db_manager.close()

        return True

    except Exception as e:
        logger.error(f"❌ 数据库初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def reset_database():
    """重置数据库(删除所有表并重建)"""
    try:
        logger.warning("⚠️  警告: 即将删除所有数据库表!")
        response = input("确认要重置数据库吗? (yes/no): ")

        if response.lower() != "yes":
            logger.info("取消操作")
            return False

        logger.info("开始重置数据库...")

        db_manager = get_db_manager()

        # 删除所有表
        async with db_manager.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            logger.info("✅ 已删除所有表")

        # 重建所有表
        async with db_manager.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("✅ 已重建所有表")

        await db_manager.close()

        logger.info("✅ 数据库重置完成!")
        return True

    except Exception as e:
        logger.error(f"❌ 数据库重置失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def check_database():
    """检查数据库连接和表"""
    try:
        logger.info("检查数据库连接...")

        db_manager = get_db_manager()

        # 测试连接
        async with db_manager.async_session_maker() as session:
            from sqlalchemy import text
            result = await session.execute(text("SELECT 1"))
            logger.info("✅ 数据库连接成功!")

        # 检查表是否存在
        async with db_manager.engine.begin() as conn:
            from sqlalchemy import inspect

            def get_table_names(connection):
                inspector = inspect(connection)
                return inspector.get_table_names()

            tables = await conn.run_sync(get_table_names)

            logger.info(f"当前数据库中的表 ({len(tables)}):")
            for table in tables:
                logger.info(f"  - {table}")

            expected_tables = [
                "user_preferences",
                "recommendation_history",
                "feedback_records",
                "reading_progress"
            ]

            missing_tables = [t for t in expected_tables if t not in tables]

            if missing_tables:
                logger.warning(f"缺失的表: {', '.join(missing_tables)}")
                logger.info("请运行: python init_db.py --init")
                return False
            else:
                logger.info("✅ 所有必需的表都已存在!")
                return True

        await db_manager.close()

    except Exception as e:
        logger.error(f"❌ 数据库检查失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def print_usage():
    """打印使用说明"""
    print("""
数据库初始化脚本

用法:
    python init_db.py [command]

命令:
    --init      初始化数据库(创建表)
    --reset     重置数据库(删除所有表并重建) ⚠️ 危险操作
    --check     检查数据库状态
    --help      显示此帮助信息

示例:
    # 首次运行,初始化数据库
    python init_db.py --init

    # 检查数据库状态
    python init_db.py --check

    # 重置数据库(会删除所有数据!)
    python init_db.py --reset

环境变量:
    DATABASE_URL    数据库连接URL
                    默认: sqlite+aiosqlite:///./book_agent.db
                    示例: postgresql+asyncpg://user:pass@localhost/dbname
    """)


async def main():
    """主函数"""
    if len(sys.argv) < 2:
        print_usage()
        return

    command = sys.argv[1]

    if command == "--init":
        success = await init_database()
        sys.exit(0 if success else 1)

    elif command == "--reset":
        success = await reset_database()
        sys.exit(0 if success else 1)

    elif command == "--check":
        success = await check_database()
        sys.exit(0 if success else 1)

    elif command == "--help" or command == "-h":
        print_usage()
        sys.exit(0)

    else:
        print(f"未知命令: {command}")
        print_usage()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
