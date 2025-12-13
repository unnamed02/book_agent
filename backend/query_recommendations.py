"""
查询推荐历史表和用户画像的工具脚本
"""
import asyncio
import sys
from sqlalchemy import select, func, desc, and_
from models import RecommendationHistory, UserPreference, FeedbackRecord, ReadingProgress, get_db_manager
from datetime import datetime, timedelta


async def query_all_recommendations():
    """查询所有推荐记录"""
    db_manager = get_db_manager()
    await db_manager.init_db()

    async with db_manager.async_session_maker() as session:
        result = await session.execute(
            select(RecommendationHistory)
            .order_by(desc(RecommendationHistory.recommended_at))
        )
        recommendations = result.scalars().all()

        print(f"\n{'='*80}")
        print(f"推荐历史记录总数: {len(recommendations)}")
        print(f"{'='*80}\n")

        for i, rec in enumerate(recommendations, 1):
            print(f"[{i}] ID: {rec.id}")
            print(f"    用户ID: {rec.user_id}")
            print(f"    会话ID: {rec.session_id}")
            print(f"    书名: {rec.book_title}")
            print(f"    作者: {rec.book_author}")
            print(f"    ISBN: {rec.book_isbn or '无'}")
            print(f"    类型: {rec.book_genre or '无'}")
            print(f"    推荐时间: {rec.recommended_at}")
            print(f"    用户查询: {rec.user_query[:50]}..." if rec.user_query and len(rec.user_query) > 50 else f"    用户查询: {rec.user_query}")
            print()


async def query_by_user(user_id: str):
    """按用户ID查询推荐记录"""
    db_manager = get_db_manager()
    await db_manager.init_db()

    async with db_manager.async_session_maker() as session:
        result = await session.execute(
            select(RecommendationHistory)
            .where(RecommendationHistory.user_id == user_id)
            .order_by(desc(RecommendationHistory.recommended_at))
        )
        recommendations = result.scalars().all()

        print(f"\n{'='*80}")
        print(f"用户 '{user_id}' 的推荐历史记录: {len(recommendations)} 条")
        print(f"{'='*80}\n")

        for i, rec in enumerate(recommendations, 1):
            print(f"[{i}] {rec.book_title} - {rec.book_author}")
            print(f"    ISBN: {rec.book_isbn or '无'}")
            print(f"    推荐时间: {rec.recommended_at}")
            print(f"    查询: {rec.user_query[:50]}..." if rec.user_query and len(rec.user_query) > 50 else f"    查询: {rec.user_query}")
            print()


async def query_recent_recommendations(days: int = 7):
    """查询最近N天的推荐记录"""
    db_manager = get_db_manager()
    await db_manager.init_db()

    cutoff_date = datetime.now() - timedelta(days=days)

    async with db_manager.async_session_maker() as session:
        result = await session.execute(
            select(RecommendationHistory)
            .where(RecommendationHistory.recommended_at >= cutoff_date)
            .order_by(desc(RecommendationHistory.recommended_at))
        )
        recommendations = result.scalars().all()

        print(f"\n{'='*80}")
        print(f"最近 {days} 天的推荐记录: {len(recommendations)} 条")
        print(f"{'='*80}\n")

        for i, rec in enumerate(recommendations, 1):
            print(f"[{i}] {rec.book_title} - {rec.book_author}")
            print(f"    用户: {rec.user_id}")
            print(f"    ISBN: {rec.book_isbn or '无'}")
            print(f"    时间: {rec.recommended_at}")
            print()


async def query_statistics():
    """查询统计信息"""
    db_manager = get_db_manager()
    await db_manager.init_db()

    async with db_manager.async_session_maker() as session:
        # 总推荐数
        total_result = await session.execute(
            select(func.count(RecommendationHistory.id))
        )
        total_count = total_result.scalar()

        # 用户数
        user_result = await session.execute(
            select(func.count(func.distinct(RecommendationHistory.user_id)))
        )
        user_count = user_result.scalar()

        # 推荐的不同书籍数
        book_result = await session.execute(
            select(func.count(func.distinct(RecommendationHistory.book_title)))
        )
        book_count = book_result.scalar()

        # 有ISBN的记录数
        isbn_result = await session.execute(
            select(func.count(RecommendationHistory.id))
            .where(RecommendationHistory.book_isbn.isnot(None))
            .where(RecommendationHistory.book_isbn != '')
        )
        isbn_count = isbn_result.scalar()

        # 最近7天的推荐数
        cutoff_date = datetime.now() - timedelta(days=7)
        recent_result = await session.execute(
            select(func.count(RecommendationHistory.id))
            .where(RecommendationHistory.recommended_at >= cutoff_date)
        )
        recent_count = recent_result.scalar()

        print(f"\n{'='*80}")
        print("推荐历史统计")
        print(f"{'='*80}")
        print(f"总推荐数: {total_count}")
        print(f"用户数: {user_count}")
        print(f"不同书籍数: {book_count}")
        print(f"含ISBN的记录: {isbn_count} ({isbn_count/total_count*100:.1f}%)" if total_count > 0 else "含ISBN的记录: 0")
        print(f"最近7天推荐: {recent_count}")
        print(f"{'='*80}\n")


async def query_by_isbn(isbn: str):
    """按ISBN查询推荐记录"""
    db_manager = get_db_manager()
    await db_manager.init_db()

    async with db_manager.async_session_maker() as session:
        result = await session.execute(
            select(RecommendationHistory)
            .where(RecommendationHistory.book_isbn == isbn)
            .order_by(desc(RecommendationHistory.recommended_at))
        )
        recommendations = result.scalars().all()

        print(f"\n{'='*80}")
        print(f"ISBN '{isbn}' 的推荐记录: {len(recommendations)} 条")
        print(f"{'='*80}\n")

        if recommendations:
            first_rec = recommendations[0]
            print(f"书名: {first_rec.book_title}")
            print(f"作者: {first_rec.book_author}")
            print(f"类型: {first_rec.book_genre or '无'}")
            print(f"\n推荐历史:")

            for i, rec in enumerate(recommendations, 1):
                print(f"  [{i}] 用户: {rec.user_id}, 时间: {rec.recommended_at}")
        else:
            print("未找到该ISBN的推荐记录")


async def query_user_profile(user_id: str):
    """查询用户画像和偏好"""
    db_manager = get_db_manager()
    await db_manager.init_db()

    async with db_manager.async_session_maker() as session:
        print(f"\n{'='*80}")
        print(f"用户画像: {user_id}")
        print(f"{'='*80}\n")

        # 1. 查询用户偏好
        pref_result = await session.execute(
            select(UserPreference)
            .where(UserPreference.user_id == user_id)
            .order_by(desc(UserPreference.weight))
        )
        preferences = pref_result.scalars().all()

        if preferences:
            print("📊 用户偏好（按权重排序）:")
            print("-" * 80)

            # 按类型分组
            genres = [p for p in preferences if p.preference_type == "genre"]
            topics = [p for p in preferences if p.preference_type == "topic"]
            authors = [p for p in preferences if p.preference_type == "author"]

            if genres:
                print("\n  类型偏好:")
                for pref in genres[:5]:
                    # 应用时间衰减
                    days_since = (datetime.now() - pref.last_reinforced_at).days if pref.last_reinforced_at else 0
                    decay_factor = pref.decay_rate ** (days_since / 30)
                    current_weight = pref.weight * decay_factor
                    print(f"    • {pref.preference_value}: 权重 {current_weight:.3f} (原始: {pref.weight:.3f}, {days_since}天前)")

            if topics:
                print("\n  主题偏好:")
                for pref in topics[:5]:
                    days_since = (datetime.now() - pref.last_reinforced_at).days if pref.last_reinforced_at else 0
                    decay_factor = pref.decay_rate ** (days_since / 30)
                    current_weight = pref.weight * decay_factor
                    print(f"    • {pref.preference_value}: 权重 {current_weight:.3f} (原始: {pref.weight:.3f}, {days_since}天前)")

            if authors:
                print("\n  作者偏好:")
                for pref in authors[:5]:
                    days_since = (datetime.now() - pref.last_reinforced_at).days if pref.last_reinforced_at else 0
                    decay_factor = pref.decay_rate ** (days_since / 30)
                    current_weight = pref.weight * decay_factor
                    print(f"    • {pref.preference_value}: 权重 {current_weight:.3f} (原始: {pref.weight:.3f}, {days_since}天前)")

            # 生成用户画像摘要
            print("\n" + "=" * 80)
            print("👤 用户画像摘要:")
            print("=" * 80)

            top_genres = [p.preference_value for p in genres[:3]]
            top_topics = [p.preference_value for p in topics[:3]]
            top_authors = [p.preference_value for p in authors[:3]]

            profile_parts = []
            if top_genres:
                profile_parts.append(f"喜欢 {', '.join(top_genres)}")
            if top_authors:
                profile_parts.append(f"喜爱作者: {', '.join(top_authors)}")
            if top_topics:
                profile_parts.append(f"关注主题: {', '.join(top_topics)}")

            if profile_parts:
                print("; ".join(profile_parts))
            else:
                print("暂无明显偏好")

        else:
            print("该用户暂无偏好记录")

        # 2. 查询推荐统计
        print("\n" + "=" * 80)
        print("📚 推荐统计:")
        print("=" * 80)

        total_recs = await session.execute(
            select(func.count(RecommendationHistory.id))
            .where(RecommendationHistory.user_id == user_id)
        )
        total_count = total_recs.scalar()

        recent_recs = await session.execute(
            select(func.count(RecommendationHistory.id))
            .where(RecommendationHistory.user_id == user_id)
            .where(RecommendationHistory.recommended_at >= datetime.now() - timedelta(days=30))
        )
        recent_count = recent_recs.scalar()

        print(f"总推荐数: {total_count}")
        print(f"最近30天推荐: {recent_count}")

        # 3. 查询反馈统计
        feedback_result = await session.execute(
            select(FeedbackRecord)
            .join(RecommendationHistory)
            .where(RecommendationHistory.user_id == user_id)
        )
        feedbacks = feedback_result.scalars().all()

        if feedbacks:
            avg_rating = sum(f.rating for f in feedbacks) / len(feedbacks)
            print(f"反馈数: {len(feedbacks)}")
            print(f"平均评分: {avg_rating:.2f}/5")

        print(f"{'='*80}\n")


async def list_all_users():
    """列出所有用户"""
    db_manager = get_db_manager()
    await db_manager.init_db()

    async with db_manager.async_session_maker() as session:
        # 从推荐历史中获取所有用户
        result = await session.execute(
            select(RecommendationHistory.user_id, func.count(RecommendationHistory.id).label('count'))
            .group_by(RecommendationHistory.user_id)
            .order_by(desc('count'))
        )
        users = result.all()

        print(f"\n{'='*80}")
        print(f"所有用户列表 (共 {len(users)} 个)")
        print(f"{'='*80}\n")

        for user_id, count in users:
            print(f"  • {user_id}: {count} 条推荐记录")

        print(f"\n{'='*80}\n")


async def main():
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python query_recommendations.py all              # 查询所有推荐记录")
        print("  python query_recommendations.py user <user_id>   # 按用户ID查询推荐记录")
        print("  python query_recommendations.py recent [days]    # 查询最近N天的记录(默认7天)")
        print("  python query_recommendations.py stats            # 查询统计信息")
        print("  python query_recommendations.py isbn <isbn>      # 按ISBN查询")
        print("  python query_recommendations.py profile <user_id> # 查询用户画像和偏好")
        print("  python query_recommendations.py users            # 列出所有用户")
        return

    command = sys.argv[1]

    try:
        if command == "all":
            await query_all_recommendations()
        elif command == "user":
            if len(sys.argv) < 3:
                print("错误: 需要提供用户ID")
                return
            await query_by_user(sys.argv[2])
        elif command == "recent":
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
            await query_recent_recommendations(days)
        elif command == "stats":
            await query_statistics()
        elif command == "isbn":
            if len(sys.argv) < 3:
                print("错误: 需要提供ISBN")
                return
            await query_by_isbn(sys.argv[2])
        elif command == "profile":
            if len(sys.argv) < 3:
                print("错误: 需要提供用户ID")
                return
            await query_user_profile(sys.argv[2])
        elif command == "users":
            await list_all_users()
        else:
            print(f"未知命令: {command}")
    except Exception as e:
        print(f"查询出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
