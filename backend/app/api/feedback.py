"""
反馈API端点
处理用户反馈的提交、查询和统计
"""
from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional
import logging
from app.models.feedback import FeedbackCreate, FeedbackResponse, FeedbackStats
from app.services.feedback_service import feedback_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def submit_feedback(feedback: FeedbackCreate):
    """
    提交用户反馈
    
    Args:
        feedback: 反馈数据
        
    Returns:
        创建的反馈记录
    """
    logger.info(f"Submitting feedback: category={feedback.category}, rating={feedback.rating}")
    
    try:
        # 创建反馈
        created_feedback = feedback_service.create_feedback(feedback)
        
        logger.info(f"Feedback submitted successfully: {created_feedback.id}")
        return created_feedback
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error submitting feedback: {e}")
        raise HTTPException(status_code=500, detail="提交反馈失败，请稍后重试")


@router.get("/", response_model=List[FeedbackResponse])
async def list_feedback(
    category: Optional[str] = None,
    min_rating: Optional[int] = None,
    limit: int = 50,
    offset: int = 0
):
    """
    列出反馈
    
    Args:
        category: 过滤类别
        min_rating: 最低评分
        limit: 返回数量限制
        offset: 偏移量
        
    Returns:
        反馈列表
    """
    logger.info(f"Listing feedback: category={category}, min_rating={min_rating}")
    
    try:
        feedbacks = feedback_service.list_feedback(
            category=category,
            min_rating=min_rating,
            limit=limit,
            offset=offset
        )
        
        return feedbacks
        
    except Exception as e:
        logger.error(f"Error listing feedback: {e}")
        raise HTTPException(status_code=500, detail="获取反馈列表失败")


@router.get("/stats", response_model=FeedbackStats)
async def get_feedback_stats():
    """
    获取反馈统计
    
    Returns:
        反馈统计数据
    """
    logger.info("Getting feedback statistics")
    
    try:
        stats = feedback_service.get_feedback_stats()
        return stats
        
    except Exception as e:
        logger.error(f"Error getting feedback stats: {e}")
        raise HTTPException(status_code=500, detail="获取反馈统计失败")


@router.get("/health", status_code=status.HTTP_200_OK)
async def feedback_health_check():
    """反馈服务健康检查"""
    stats = feedback_service.get_feedback_stats()
    return {
        "status": "healthy",
        "service": "feedback",
        "total_feedback": stats.total_feedback
    }


@router.get("/{feedback_id}", response_model=FeedbackResponse)
async def get_feedback(feedback_id: str):
    """
    根据ID获取反馈详情
    
    Args:
        feedback_id: 反馈ID
        
    Returns:
        反馈详情
    """
    logger.info(f"Getting feedback: {feedback_id}")
    
    try:
        feedback = feedback_service.get_feedback(feedback_id)
        
        if not feedback:
            raise HTTPException(status_code=404, detail="反馈不存在")
        
        return feedback
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting feedback {feedback_id}: {e}")
        raise HTTPException(status_code=500, detail="获取反馈详情失败")


@router.delete("/{feedback_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_feedback(feedback_id: str):
    """
    删除反馈
    
    Args:
        feedback_id: 反馈ID
    """
    logger.info(f"Deleting feedback: {feedback_id}")
    
    try:
        deleted = feedback_service.delete_feedback(feedback_id)
        
        if not deleted:
            raise HTTPException(status_code=404, detail="反馈不存在")
        
        logger.info(f"Feedback deleted successfully: {feedback_id}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting feedback {feedback_id}: {e}")
        raise HTTPException(status_code=500, detail="删除反馈失败")
