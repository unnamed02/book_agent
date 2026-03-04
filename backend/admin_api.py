"""
管理端 API
提供后台管理功能，包括用户管理、荐购管理、统计分析等
"""

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_
from utils.models import get_db, User, UserSession, PurchaseRecommendation, ConversationArchive
from dotenv import load_dotenv
import logging
from typing import List, Optional
from datetime import datetime, timedelta

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Book Agent Admin API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# ==================== 数据模型 ====================

class PurchaseRecommendationResponse(BaseModel):
    """荐购表单响应"""
    id: int
    user_id: str
    book_title: str
    author: Optional[str] = None
    notes: Optional[str] = None
    contact: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    """用户响应"""
    user_id: str
    created_at: datetime
    updated_at: datetime
    session_count: int = 0

    class Config:
        from_attributes = True


class UpdatePurchaseRecommendationRequest(BaseModel):
    """更新荐购状态请求"""
    status: str  # pending, approved, rejected


class SystemStatsResponse(BaseModel):
    """系统统计信息"""
    total_users: int
    total_sessions: int
    total_recommendations: int
    pending_recommendations: int
    approved_recommendations: int
    rejected_recommendations: int
    recommendations_7days: int


class RecommendationStatsResponse(BaseModel):
    """荐购统计信息"""
    total: int
    pending: int
    approved: int
    rejected: int
    average_processing_time_hours: Optional[float] = None


# ==================== 健康检查 ====================

@app.get("/")
async def root():
    """健康检查端点"""
    return {"status": "ok", "message": "Admin API is running"}


# ==================== 用户管理 ====================

@app.get("/users", response_model=List[UserResponse])
async def get_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """获取用户列表（分页）"""
    try:
        # 计算偏移量
        offset = (page - 1) * page_size

        # 获取用户及其会话数
        query = select(User).offset(offset).limit(page_size)
        result = await db.execute(query)
        users = result.scalars().all()

        # 为每个用户查询会话数
        users_response = []
        for user in users:
            session_query = select(func.count(UserSession.id)).where(
                UserSession.user_id == user.user_id
            )
            session_result = await db.execute(session_query)
            session_count = session_result.scalar() or 0

            users_response.append(UserResponse(
                user_id=user.user_id,
                created_at=user.created_at,
                updated_at=user.updated_at,
                session_count=session_count
            ))

        return users_response

    except Exception as e:
        logger.error(f"获取用户列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/users/total")
async def get_users_total(db: AsyncSession = Depends(get_db)):
    """获取用户总数"""
    try:
        query = select(func.count(User.user_id))
        result = await db.execute(query)
        total = result.scalar() or 0
        return {"total": total}
    except Exception as e:
        logger.error(f"获取用户总数失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/users/{user_id}")
async def get_user_details(
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    """获取用户详情"""
    try:
        query = select(User).where(User.user_id == user_id)
        result = await db.execute(query)
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        # 获取用户的会话数
        session_query = select(func.count(UserSession.id)).where(
            UserSession.user_id == user_id
        )
        session_result = await db.execute(session_query)
        session_count = session_result.scalar() or 0

        # 获取用户的荐购记录数
        rec_query = select(func.count(PurchaseRecommendation.id)).where(
            PurchaseRecommendation.user_id == user_id
        )
        rec_result = await db.execute(rec_query)
        rec_count = rec_result.scalar() or 0

        return {
            "user_id": user.user_id,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
            "session_count": session_count,
            "recommendation_count": rec_count
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取用户详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 荐购管理 ====================

@app.get("/recommendations", response_model=List[PurchaseRecommendationResponse])
async def get_recommendations(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """获取荐购列表"""
    try:
        offset = (page - 1) * page_size

        # 构建查询条件
        conditions = []
        if status:
            conditions.append(PurchaseRecommendation.status == status)

        query = select(PurchaseRecommendation)
        if conditions:
            query = query.where(and_(*conditions))

        query = query.order_by(desc(PurchaseRecommendation.created_at)).offset(offset).limit(page_size)

        result = await db.execute(query)
        recommendations = result.scalars().all()

        return recommendations

    except Exception as e:
        logger.error(f"获取荐购列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/recommendations/total")
async def get_recommendations_total(
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """获取荐购总数"""
    try:
        conditions = []
        if status:
            conditions.append(PurchaseRecommendation.status == status)

        query = select(func.count(PurchaseRecommendation.id))
        if conditions:
            query = query.where(and_(*conditions))

        result = await db.execute(query)
        total = result.scalar() or 0

        return {"total": total}

    except Exception as e:
        logger.error(f"获取荐购总数失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/recommendations/{recommendation_id}", response_model=PurchaseRecommendationResponse)
async def get_recommendation_details(
    recommendation_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取荐购详情"""
    try:
        query = select(PurchaseRecommendation).where(
            PurchaseRecommendation.id == recommendation_id
        )
        result = await db.execute(query)
        recommendation = result.scalar_one_or_none()

        if not recommendation:
            raise HTTPException(status_code=404, detail="荐购记录不存在")

        return recommendation

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取荐购详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/recommendations/{recommendation_id}")
async def update_recommendation_status(
    recommendation_id: int,
    request: UpdatePurchaseRecommendationRequest,
    db: AsyncSession = Depends(get_db)
):
    """更新荐购状态"""
    try:
        # 验证状态值
        valid_statuses = ["pending", "approved", "rejected"]
        if request.status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"无效的状态值，必须是: {', '.join(valid_statuses)}"
            )

        query = select(PurchaseRecommendation).where(
            PurchaseRecommendation.id == recommendation_id
        )
        result = await db.execute(query)
        recommendation = result.scalar_one_or_none()

        if not recommendation:
            raise HTTPException(status_code=404, detail="荐购记录不存在")

        recommendation.status = request.status
        await db.commit()
        await db.refresh(recommendation)

        logger.info(f"荐购 {recommendation_id} 状态已更新为: {request.status}")

        return {
            "success": True,
            "message": "状态更新成功",
            "recommendation": recommendation
        }

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"更新荐购状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 统计分析 ====================

@app.get("/stats/system", response_model=SystemStatsResponse)
async def get_system_stats(db: AsyncSession = Depends(get_db)):
    """获取系统统计信息"""
    try:
        # 总用户数
        user_query = select(func.count(User.user_id))
        user_result = await db.execute(user_query)
        total_users = user_result.scalar() or 0

        # 总会话数
        session_query = select(func.count(UserSession.id))
        session_result = await db.execute(session_query)
        total_sessions = session_result.scalar() or 0

        # 总荐购数
        total_rec_query = select(func.count(PurchaseRecommendation.id))
        total_rec_result = await db.execute(total_rec_query)
        total_recommendations = total_rec_result.scalar() or 0

        # 各状态荐购数
        pending_query = select(func.count(PurchaseRecommendation.id)).where(
            PurchaseRecommendation.status == "pending"
        )
        pending_result = await db.execute(pending_query)
        pending_recommendations = pending_result.scalar() or 0

        approved_query = select(func.count(PurchaseRecommendation.id)).where(
            PurchaseRecommendation.status == "approved"
        )
        approved_result = await db.execute(approved_query)
        approved_recommendations = approved_result.scalar() or 0

        rejected_query = select(func.count(PurchaseRecommendation.id)).where(
            PurchaseRecommendation.status == "rejected"
        )
        rejected_result = await db.execute(rejected_query)
        rejected_recommendations = rejected_result.scalar() or 0

        # 7天内荐购数
        seven_days_ago = datetime.now() - timedelta(days=7)
        seven_days_query = select(func.count(PurchaseRecommendation.id)).where(
            PurchaseRecommendation.created_at >= seven_days_ago
        )
        seven_days_result = await db.execute(seven_days_query)
        recommendations_7days = seven_days_result.scalar() or 0

        return SystemStatsResponse(
            total_users=total_users,
            total_sessions=total_sessions,
            total_recommendations=total_recommendations,
            pending_recommendations=pending_recommendations,
            approved_recommendations=approved_recommendations,
            rejected_recommendations=rejected_recommendations,
            recommendations_7days=recommendations_7days
        )

    except Exception as e:
        logger.error(f"获取系统统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats/recommendations", response_model=RecommendationStatsResponse)
async def get_recommendation_stats(db: AsyncSession = Depends(get_db)):
    """获取荐购统计信息（包括平均处理时间）"""
    try:
        # 总数
        total_query = select(func.count(PurchaseRecommendation.id))
        total_result = await db.execute(total_query)
        total = total_result.scalar() or 0

        # 各状态数
        pending_query = select(func.count(PurchaseRecommendation.id)).where(
            PurchaseRecommendation.status == "pending"
        )
        pending_result = await db.execute(pending_query)
        pending = pending_result.scalar() or 0

        approved_query = select(func.count(PurchaseRecommendation.id)).where(
            PurchaseRecommendation.status == "approved"
        )
        approved_result = await db.execute(approved_query)
        approved = approved_result.scalar() or 0

        rejected_query = select(func.count(PurchaseRecommendation.id)).where(
            PurchaseRecommendation.status == "rejected"
        )
        rejected_result = await db.execute(rejected_query)
        rejected = rejected_result.scalar() or 0

        # 计算平均处理时间（已审核的荐购）
        avg_time_query = select(
            func.avg(
                func.cast(
                    PurchaseRecommendation.updated_at - PurchaseRecommendation.created_at,
                    type_=None
                )
            )
        ).where(PurchaseRecommendation.status != "pending")

        avg_time_result = await db.execute(avg_time_query)
        avg_time = avg_time_result.scalar()

        average_processing_time_hours = None
        if avg_time:
            # 转换为小时
            total_seconds = avg_time.total_seconds()
            average_processing_time_hours = round(total_seconds / 3600, 2)

        return RecommendationStatsResponse(
            total=total,
            pending=pending,
            approved=approved,
            rejected=rejected,
            average_processing_time_hours=average_processing_time_hours
        )

    except Exception as e:
        logger.error(f"获取荐购统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 对话历史 ====================

@app.get("/conversations/{user_id}")
async def get_user_conversations(
    user_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """获取用户的对话历史"""
    try:
        offset = (page - 1) * page_size

        # 获取用户的会话列表
        query = select(UserSession).where(
            UserSession.user_id == user_id
        ).order_by(desc(UserSession.last_active_at)).offset(offset).limit(page_size)

        result = await db.execute(query)
        sessions = result.scalars().all()

        sessions_data = []
        for session in sessions:
            # 获取该会话的对话归档
            archive_query = select(ConversationArchive).where(
                ConversationArchive.session_id == session.session_id
            )
            archive_result = await db.execute(archive_query)
            archive = archive_result.scalar_one_or_none()

            sessions_data.append({
                "session_id": session.session_id,
                "created_at": session.created_at,
                "last_active_at": session.last_active_at,
                "messages_count": len(archive.messages) if archive and archive.messages else 0,
                "has_archive": archive is not None
            })

        return {
            "user_id": user_id,
            "sessions": sessions_data,
            "page": page,
            "page_size": page_size
        }

    except Exception as e:
        logger.error(f"获取用户对话历史失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/conversations/session/{session_id}")
async def get_session_details(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """获取指定会话的详情和消息"""
    try:
        # 获取会话信息
        session_query = select(UserSession).where(
            UserSession.session_id == session_id
        )
        session_result = await db.execute(session_query)
        session = session_result.scalar_one_or_none()

        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")

        # 获取对话归档
        archive_query = select(ConversationArchive).where(
            ConversationArchive.session_id == session_id
        )
        archive_result = await db.execute(archive_query)
        archive = archive_result.scalar_one_or_none()

        return {
            "session_id": session.session_id,
            "user_id": session.user_id,
            "created_at": session.created_at,
            "last_active_at": session.last_active_at,
            "messages": archive.messages if archive else [],
            "archived_at": archive.archived_at if archive else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取会话详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
