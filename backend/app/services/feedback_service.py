"""反馈服务模块（数据库实现）"""
from typing import List, Optional
import logging
from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models.feedback_orm import FeedbackORM
from app.models.feedback import FeedbackCreate, FeedbackResponse, FeedbackStats

logger = logging.getLogger(__name__)


class FeedbackService:
    """反馈服务类"""

    def create_feedback(self, feedback: FeedbackCreate) -> FeedbackResponse:
        """创建新反馈"""
        with SessionLocal() as db:
            obj = FeedbackORM(
                trip_id=feedback.trip_id,
                rating=feedback.rating,
                category=feedback.category,
                comment=feedback.comment,
                user_email=feedback.user_email,
                user_name=feedback.user_name,
            )
            db.add(obj)
            db.commit()
            db.refresh(obj)
            logger.info("Feedback created: %s", obj.id)
            return FeedbackResponse.model_validate(obj)
    
    def get_feedback(self, feedback_id: str) -> Optional[FeedbackResponse]:
        """根据ID获取反馈"""
        with SessionLocal() as db:
            obj = db.get(FeedbackORM, feedback_id)
            return FeedbackResponse.model_validate(obj) if obj else None
    
    def list_feedback(
        self, 
        category: Optional[str] = None,
        min_rating: Optional[int] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[FeedbackResponse]:
        """列出反馈"""
        with SessionLocal() as db:
            stmt = select(FeedbackORM).order_by(FeedbackORM.created_at.desc()).offset(offset).limit(limit)
            if category:
                stmt = stmt.where(FeedbackORM.category == category)
            if min_rating is not None:
                stmt = stmt.where(FeedbackORM.rating >= min_rating)
            rows = db.execute(stmt).scalars().all()
            return [FeedbackResponse.model_validate(row) for row in rows]
    
    def get_feedback_stats(self) -> FeedbackStats:
        """获取反馈统计"""
        with SessionLocal() as db:
            total = db.execute(select(func.count()).select_from(FeedbackORM)).scalar_one()
            avg = db.execute(select(func.avg(FeedbackORM.rating))).scalar_one()
            category_rows = db.execute(
                select(FeedbackORM.category, func.count()).group_by(FeedbackORM.category)
            ).all()
            recent_rows = db.execute(
                select(FeedbackORM).order_by(FeedbackORM.created_at.desc()).limit(5)
            ).scalars().all()

            return FeedbackStats(
                total_feedback=total or 0,
                average_rating=round(float(avg or 0.0), 2),
                category_distribution={row[0]: row[1] for row in category_rows},
                recent_feedback=[FeedbackResponse.model_validate(row) for row in recent_rows],
            )
    
    def delete_feedback(self, feedback_id: str) -> bool:
        """删除反馈"""
        with SessionLocal() as db:
            obj = db.get(FeedbackORM, feedback_id)
            if not obj:
                return False
            db.delete(obj)
            db.commit()
            logger.info("Feedback deleted: %s", feedback_id)
            return True


# 创建全局反馈服务实例
feedback_service = FeedbackService()
