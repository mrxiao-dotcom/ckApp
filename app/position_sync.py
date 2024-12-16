import sys
import os
import time
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
import schedule
from logging.handlers import RotatingFileHandler

# 添加项目根目录到 Python 路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(current_dir)
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

from app import create_app, db
from app.models import MonitorList, PriceRange20d
from app.data_manager import DataManager
from app.database import DatabaseConnection

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # 输出到控制台
        logging.FileHandler('position_sync.log', encoding='utf-8')  # 同时写入文件
    ]
)
logger = logging.getLogger(__name__)

class PositionSyncer:
    def __init__(self, app=None):
        self.app = app or create_app()
        self.data_manager = None
        self.db_connection = None
        
    def init_connections(self):
        """初始化数据库连接和API管理器"""
        self.db_connection = DatabaseConnection('2')
        self.data_manager = DataManager('2')
    
    def check_waiting_positions(self):
        """检查等待开仓的仓位"""
        with self.app.app_context():
            try:
                # 获取等待开仓的监控记录
                monitors = MonitorList.query.filter_by(
                    sync_status='waiting',
                    is_active=True
                ).all()
                
                if not monitors:
                    logger.info("没有等待开仓的记录")
                    return
                
                logger.info(f"找到 {len(monitors)} 条等待开仓的记录")
                
                # 获取最新价格数据
                latest_date = db.session.query(db.func.max(PriceRange20d.update_date)).scalar()
                if not latest_date:
                    logger.warning("未找到价格数据")
                    return
                
                # 获取3分钟前的时间
                three_mins_ago = datetime.now() - timedelta(minutes=3)
                
                # 获取价格数据
                price_records = PriceRange20d.query.filter(
                    PriceRange20d.update_date == latest_date,
                    PriceRange20d.update_time >= three_mins_ago
                ).all()
                
                # 转换为字典以便快速查找
                price_data = {pr.symbol: pr for pr in price_records}
                
                # 处理每个等待开仓的记录
                for monitor in monitors:
                    self.process_waiting_position(monitor, price_data)
                    
            except Exception as e:
                logger.error(f"检查等待开仓失败: {str(e)}")
                logger.exception("详细错误信息：")
    
    def process_waiting_position(self, monitor: MonitorList, price_data: Dict):
        """处理单个等待开仓的记录"""
        try:
            price_info = price_data.get(monitor.symbol)
            if not price_info:
                logger.warning(f"未找到 {monitor.symbol} 的价格数据")
                return
            
            # 获取账户API信息
            account_info = self.data_manager.get_account_info(monitor.account_id)
            if not account_info:
                logger.error(f"未找到账户 {monitor.account_id} 的API信息")
                return
            
            # 初始化API
            self.data_manager.init_api(account_info)
            
            # 检查开仓条件
            last_price = Decimal(str(price_info.last_price))
            high_price = Decimal(str(price_info.high_price_20d))
            low_price = Decimal(str(price_info.low_price_20d))
            
            if last_price > high_price:
                # 开多
                logger.info(f"开多信号 - {monitor.symbol}")
                self.open_position(monitor, account_info, 'long')
            elif last_price < low_price:
                # 开空
                logger.info(f"开空信号 - {monitor.symbol}")
                self.open_position(monitor, account_info, 'short')
                
        except Exception as e:
            logger.error(f"处理 {monitor.symbol} 失败: {str(e)}")
    
    def check_opened_positions(self):
        """检查已开仓的仓位"""
        with self.app.app_context():
            try:
                # 获取已开仓的监控记录
                monitors = MonitorList.query.filter_by(
                    sync_status='opened',
                    is_active=True
                ).all()
                
                if not monitors:
                    logger.info("没有已开仓的记录")
                    return
                
                logger.info(f"找到 {len(monitors)} 条已开仓的记录")
                
                # 处理每个已开仓的记录
                for monitor in monitors:
                    self.check_take_profit(monitor)
                    
            except Exception as e:
                logger.error(f"检查已开仓失败: {str(e)}")
                logger.exception("详细错误信息：")
    
    def open_position(self, monitor: MonitorList, account_info: dict, direction: str):
        """开仓"""
        try:
            # 计算下单金额
            amount = float(monitor.allocated_money)
            
            # 调用交易所API下单
            order = self.data_manager.create_order(
                account_info=account_info,
                symbol=monitor.symbol,
                direction=direction,
                amount=amount,
                leverage=monitor.leverage  # 使用监控记录中的杠杆倍数
            )
            
            if order:
                # 更新状态
                monitor.sync_status = 'opened'
                monitor.last_sync_time = datetime.now()
                db.session.commit()
                logger.info(f"成功开仓 {monitor.symbol}")
            else:
                logger.error(f"开仓 {monitor.symbol} 失败")
                
        except Exception as e:
            logger.error(f"开仓 {monitor.symbol} 失败: {str(e)}")
            db.session.rollback()
    
    def check_take_profit(self, monitor: MonitorList):
        """检查止盈"""
        try:
            # 获取账户API信息
            account_info = self.data_manager.get_account_info(monitor.account_id)
            if not account_info:
                logger.error(f"未找到账户 {monitor.account_id} 的API信息")
                return
            
            # 获取未实现盈利
            unrealized_pnl = self.data_manager.get_position_pnl(
                account_info=account_info,
                symbol=monitor.symbol
            )
            
            if unrealized_pnl is None:
                logger.warning(f"获取 {monitor.symbol} 未实现盈利失败")
                return
            
            # 检查是否达到止盈条件
            if unrealized_pnl >= float(monitor.take_profit):
                logger.info(f"{monitor.symbol} 达到止盈条件")
                self.close_position(monitor, account_info)
                
        except Exception as e:
            logger.error(f"检查止盈 {monitor.symbol} 失败: {str(e)}")
    
    def close_position(self, monitor: MonitorList, account_info: dict):
        """平仓"""
        try:
            # 调用交易所API平仓
            success = self.data_manager.close_position(
                account_info=account_info,
                symbol=monitor.symbol
            )
            
            if success:
                # 更新状态
                monitor.sync_status = 'closed'
                monitor.last_sync_time = datetime.now()
                db.session.commit()
                logger.info(f"成功平仓 {monitor.symbol}")
            else:
                logger.error(f"平仓 {monitor.symbol} 失败")
                
        except Exception as e:
            logger.error(f"平仓 {monitor.symbol} 失败: {str(e)}")
            db.session.rollback()
    
    def check_unwanted_positions(self):
        """检查并平仓不在监控列表中的仓位"""
        with self.app.app_context():
            try:
                # 获取所有激活的监控记录
                monitors = MonitorList.query.filter_by(is_active=True).all()
                monitored_symbols = {(m.account_id, m.symbol) for m in monitors}
                
                # 获取所有账户ID
                account_ids = {m.account_id for m in monitors}
                
                for account_id in account_ids:
                    try:
                        # 获取账户API信息
                        account_info = self.data_manager.get_account_info(account_id)
                        if not account_info:
                            logger.error(f"未找到账户 {account_id} 的API信息")
                            continue
                        
                        # 获取账户当前持仓
                        positions = self.data_manager.get_account_positions(account_info)
                        if not positions:
                            continue
                        
                        # 检查每个持仓
                        for position in positions:
                            if (account_id, position.symbol) not in monitored_symbols:
                                logger.info(f"发现非监控品种持仓: {account_id} - {position.symbol}")
                                # 平仓
                                success = self.data_manager.close_position(
                                    account_info=account_info,
                                    symbol=position.symbol
                                )
                                if success:
                                    logger.info(f"成功平仓非监控品种: {position.symbol}")
                                else:
                                    logger.error(f"平仓非监控品种失败: {position.symbol}")
                    
                    except Exception as e:
                        logger.error(f"处理账户 {account_id} 的非监控品种失败: {str(e)}")
                        
            except Exception as e:
                logger.error("检查非监控品种失败")
                logger.exception("详细错误信息：")

def run_sync_once():
    """执行一次同步检查"""
    try:
        logger.info("开始同步检查")
        syncer = PositionSyncer()
        syncer.init_connections()
        
        with syncer.app.app_context():
            # 获取所有激活的监控记录，按账户分组
            monitors = MonitorList.query.filter_by(is_active=True).all()
            if not monitors:
                logger.info("没有监控记录")
                return
            
            # 按账户ID分组
            accounts_monitors = {}
            for monitor in monitors:
                if monitor.account_id not in accounts_monitors:
                    accounts_monitors[monitor.account_id] = []
                accounts_monitors[monitor.account_id].append(monitor)
            
            # 获取最新价格数据
            latest_date = db.session.query(db.func.max(PriceRange20d.update_date)).scalar()
            if not latest_date:
                logger.warning("未找到价格数据")
                return
            
            # 获取3分钟内的价格数据
            three_mins_ago = datetime.now() - timedelta(minutes=3)
            price_records = PriceRange20d.query.filter(
                PriceRange20d.update_date == latest_date,
                PriceRange20d.update_time >= three_mins_ago
            ).all()
            
            # 转换为字典以便快速查找
            price_data = {pr.symbol: pr for pr in price_records}
            
            # 处理每个账户
            for account_id, account_monitors in accounts_monitors.items():
                try:
                    logger.info(f"处理账户 {account_id}")
                    
                    # 获取账户API信息
                    account_info = syncer.data_manager.get_account_info(account_id)
                    if not account_info:
                        logger.error(f"未找到账户 {account_id} 的API信息")
                        continue
                    
                    # 初始化API
                    syncer.data_manager.init_api(account_info)
                    
                    # 获取当前持仓
                    current_positions = syncer.data_manager.get_account_positions(account_info)
                    current_position_symbols = {pos.symbol for pos in current_positions}
                    
                    # 处理每个监控品种
                    for monitor in account_monitors:
                        try:
                            # 获取价格数据
                            price_info = price_data.get(monitor.symbol)
                            if not price_info:
                                logger.warning(f"未找到 {monitor.symbol} 的价格数据")
                                continue
                            
                            # 检查是否已有持仓
                            has_position = monitor.symbol in current_position_symbols
                            
                            if monitor.sync_status == 'waiting' and not has_position:
                                # 检查开仓条件
                                last_price = Decimal(str(price_info.last_price))
                                high_price = Decimal(str(price_info.high_price_20d))
                                low_price = Decimal(str(price_info.low_price_20d))
                                
                                if last_price > high_price:
                                    # 开多
                                    logger.info(f"开多信号 - {monitor.symbol}")
                                    syncer.open_position(monitor, account_info, 'long')
                                elif last_price < low_price:
                                    # 开空
                                    logger.info(f"开空信号 - {monitor.symbol}")
                                    syncer.open_position(monitor, account_info, 'short')
                                    
                            elif monitor.sync_status == 'opened' and has_position:
                                # 检查止盈条件
                                syncer.check_take_profit(monitor)
                            
                            elif monitor.sync_status == 'opened' and not has_position:
                                # 状态不一致，更新为已关闭
                                logger.warning(f"{monitor.symbol} 状态为opened但无持仓，更新为closed")
                                monitor.sync_status = 'closed'
                                monitor.last_sync_time = datetime.now()
                                db.session.commit()
                                
                        except Exception as e:
                            logger.error(f"处理品种 {monitor.symbol} 失败: {str(e)}")
                            continue
                    
                    # 检查并平仓非监控品种
                    monitored_symbols = {m.symbol for m in account_monitors}
                    for position in current_positions:
                        if position.symbol not in monitored_symbols:
                            logger.info(f"发现非监控品种持仓: {position.symbol}")
                            success = syncer.data_manager.close_position(
                                account_info=account_info,
                                symbol=position.symbol
                            )
                            if success:
                                logger.info(f"成功平仓非监控品种: {position.symbol}")
                            else:
                                logger.error(f"平仓非监控品种失败: {position.symbol}")
                    
                except Exception as e:
                    logger.error(f"处理账户 {account_id} 失败: {str(e)}")
                    continue
            
        logger.info("同步检查完成")
        
    except Exception as e:
        logger.error(f"同步任务失败: {str(e)}")
        logger.exception("详细错误信息：")

def run_sync_loop(interval: int = 60):
    """持续运行同步检查"""
    logger.info(f"启动持续同步，间隔 {interval} 秒")
    
    schedule.every(interval).seconds.do(run_sync_once)
    
    # 启动时先执行一次
    run_sync_once()
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("程序被手动停止")

if __name__ == "__main__":
    try:
        # 检查命令行参数
        if len(sys.argv) > 1:
            if sys.argv[1] == '--once':
                # 单次运行模式
                run_sync_once()
            else:
                # 尝试将参数解析为间隔时间
                try:
                    interval = int(sys.argv[1])
                    run_sync_loop(interval)
                except ValueError:
                    print("用法：")
                    print("  python position_sync.py          # 持续运行，默认60秒间隔")
                    print("  python position_sync.py 30       # 持续运行，30秒间隔")
                    print("  python position_sync.py --once   # 执行一次后退出")
                    sys.exit(1)
        else:
            # 默认持续运行，60秒间隔
            run_sync_loop()
            
    except Exception as e:
        logger.error(f"程序运行失败: {str(e)}")
        logger.exception("详细错误信息：")
        sys.exit(1) 