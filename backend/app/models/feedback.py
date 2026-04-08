from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class FeedbackBase(BaseModel):
    """反馈基础模型"""
    trip_id: Optional[str] = Field(None, description="行程ID")
    rating: int = Field(..., ge=1, le=5, description="评分（1-5星）")
    category: str = Field(..., description="反馈类别：itinerary, budget, recommendations, ui, other")
    comment: str = Field(..., min_length=1, max_length=1000, description="详细反馈")
    user_email: Optional[str] = Field(None, description="用户邮箱（可选）")
    user_name: Optional[str] = Field(None, description="用户姓名（可选）")


class FeedbackCreate(FeedbackBase):
    """创建反馈请求模型"""
    pass


class FeedbackResponse(FeedbackBase):
    """反馈响应模型"""
    id: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class FeedbackStats(BaseModel):
    """反馈统计模型"""
    total_feedback: int
    average_rating: float
    category_distribution: dict
    recent_feedback: list[FeedbackResponse]