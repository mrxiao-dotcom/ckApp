from app import scheduler
from app.price_updater import PriceUpdater
import logging
from datetime import datetime
from flask import current_app

logger = logging.getLogger(__name__)

def update_price_range():
    """执行价格范围更新任务"""
    try:
        logger.info(f"开始执行价格范围更新任务 - {datetime.now()}")
        updater = PriceUpdater(current_app._get_current_object())
        updater.run()
        logger.info("价格范围更新任务完成")
    except Exception as e:
        logger.error(f"价格范围更新任务失败: {str(e)}")

def update_ticks():
    """执行实时行情更新任务"""
    try:
        logger.info(f"开始执行实时行情更新任务 - {datetime.now()}")
        updater = PriceUpdater(current_app._get_current_object())
        updater.update_ticks()
        logger.info("实时行情更新任务完成")
    except Exception as e:
        logger.error(f"实时行情更新任务失败: {str(e)}")

def init_scheduler():
    """初始化调度任务"""
    try:
        # 移除已存在的任务（如果有）
        scheduler.remove_job('update_price_range')
        scheduler.remove_job('update_ticks')
    except:
        pass

    # 添加每日更新任务
    scheduler.add_job(
        id='update_price_range',
        func=update_price_range,
        trigger='cron',
        hour=0,
        minute=1,
        misfire_grace_time=3600  # 允许的任务延迟执行时间（秒）
    )
    
    # 添加实时行情更新任务（每分钟执行）
    scheduler.add_job(
        id='update_ticks',
        func=update_ticks,
        trigger='interval',
        minutes=1,
        misfire_grace_time=30  # 允许30秒的延迟
    )
    
    logger.info("所有定时任务已调度")