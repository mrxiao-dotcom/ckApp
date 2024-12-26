import sys
import os
import time
import schedule
from datetime import datetime, timedelta, date
import pymysql
from typing import Dict, List, Optional
import logging
from logging.handlers import RotatingFileHandler
from decimal import Decimal
from sqlalchemy import text  # 添加这行导入
import codecs
from app import setup_logging
from config import Config

# 添加项目根目录到 Python 路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(current_dir)
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

# 现在可以导入 app 模块了
from app.data_manager import DataManager
from app.database import DatabaseConnection, DatabaseManager
from flask import current_app
from app import create_app, db
from app.models import PriceRange20d

# 配置日志
logger = setup_logging(
    'price_updater',
    os.path.join('logs', 'price_updater.log')
)

class PriceUpdater:
    def __init__(self, app=None):
        self.app = app or create_app()
        self.db_connection = None
        self.data_manager = None
        self.price_range_days = Config.PRICE_RANGE_DAYS
        
    def init_connections(self):
        """初始化数据库连接和API管理器"""
        self.db_connection = DatabaseConnection('2')  # 使用服务器1的配置
        self.init_api_credentials()

    def get_db_connection(self):
        """获取数据库连接"""
        if not self.db_connection:
            raise RuntimeError("Database connection not initialized")
        return self.db_connection.get_connection()

    def init_api_credentials(self):
        """从数据库获取API凭证"""
        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT acct_id, acct_name, apikey, secretkey, apipass, 
                               email, group_id, state, status
                        FROM acct_info
                        WHERE acct_id = 55
                    """)
                    account_data = cursor.fetchone()
                    if not account_data:
                        raise ValueError("Account 55 not found")

                    # 创建 AccountInfo 对象，对敏感信息进行脱敏处理
                    from app.models import AccountInfo
                    account_info = AccountInfo(
                        acct_id=str(account_data['acct_id']),
                        acct_name=account_data['acct_name'],
                        apikey='*' * len(account_data['apikey']),  # 脱敏处理
                        secretkey='*' * len(account_data['secretkey']),  # 脱敏处理
                        apipass='*' * len(account_data['apipass']),  # 脱敏处理
                        email=account_data['email'],
                        group_id=account_data['group_id'],
                        state=account_data['state'],
                        status=account_data['status'],
                        stg_comb_product_gateio=[]
                    )

                    # 初始化 DataManager
                    self.data_manager = DataManager('2')
                    self.data_manager.account_info = account_info
                    logger.debug("API credentials initialized")
        except Exception as e:
            logger.error(f"Failed to get API credentials: {str(e)}")
            raise

    def get_all_contracts(self) -> List[str]:
        """获取所有可用的合约"""
        try:
            # 使用 DataManager 的方法获取合约列表
            contracts = self.data_manager.get_futures_contracts()
            # 返回合约名称列表
            return [contract.symbol for contract in contracts]
        except Exception as e:
            logger.error(f"获取合约列表失败: {str(e)}")
            return []

    def get_ohlcv_data(self, symbol: str) -> Optional[List]:
        """获取指定合约的K线数据"""
        try:
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            yesterday = today - timedelta(days=1)
            start_date = yesterday - timedelta(days=self.price_range_days-1)  # 减1是因为包含昨天
            
            end_timestamp = int(today.timestamp())
            start_timestamp = int(start_date.timestamp())
            
            logger.debug(f"获取 {symbol} K线数据: {start_date.date()} 到 {yesterday.date()}")
            
            candles = self.data_manager.get_futures_candlesticks(
                symbol=symbol,
                from_time=start_timestamp,
                to_time=end_timestamp,
                interval='1d'
            )
            
            if not candles:
                logger.warning(f"{symbol} 没有K线数据")
                return None
            
            # 提取收盘价，确保正好取N天的数据
            close_prices = [float(candle['close']) for candle in candles[-self.price_range_days:]]
            
            if len(close_prices) < self.price_range_days:
                logger.warning(f"{symbol} 的K线数据��足{self.price_range_days}天: {len(close_prices)}天")
                return None
            
            # 记录最高最低价格的日期
            prices_with_dates = [(float(candle['close']), 
                                datetime.fromtimestamp(candle['timestamp']).date()) 
                               for candle in candles[-self.price_range_days:]]
            max_price, max_date = max(prices_with_dates, key=lambda x: x[0])
            min_price, min_date = min(prices_with_dates, key=lambda x: x[0])
            logger.debug(f"{symbol} {self.price_range_days}日最高收盘价 {max_price} ({max_date})")
            logger.debug(f"{symbol} {self.price_range_days}日最低收盘价 {min_price} ({min_date})")
            
            return close_prices
            
        except Exception as e:
            logger.error(f"获取{symbol}的K线数据失败: {str(e)}")
            return None

    def calculate_price_range(self, close_prices: List[float]) -> Optional[Dict]:
        """计算20日价格范围"""
        if not close_prices or len(close_prices) < 20:
            return None

        high_price = max(close_prices)
        low_price = min(close_prices)
        last_price = close_prices[-1]

        # 计算振幅和位置比例
        amplitude = (high_price - low_price) / low_price if low_price > 0 else 0
        position_ratio = (last_price - low_price) / (high_price - low_price) if (high_price - low_price) > 0 else 0

        return {
            'high_price_20d': high_price,
            'low_price_20d': low_price,
            'last_price': last_price,
            'amplitude': amplitude,
            'position_ratio': position_ratio
        }

    def update_price_range(self, symbol: str, price_data: Dict):
        """更新数据库中的价格范围数据"""
        today = datetime.now().date()
        
        with self.get_db_connection() as conn:
            with conn.cursor() as cursor:
                # 检查天是否已经有数据
                cursor.execute("""
                    SELECT id FROM price_range_20d 
                    WHERE symbol = %s AND update_date = %s
                """, (symbol, today))
                
                if cursor.fetchone():
                    logger.info(f"{symbol} 今日数据已存在，跳过更新")
                    return False

                # 插入新数据
                cursor.execute("""
                    INSERT INTO price_range_20d (
                        symbol, high_price_20d, low_price_20d, last_price,
                        amplitude, position_ratio, update_date
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s
                    )
                """, (
                    symbol,
                    price_data['high_price_20d'],
                    price_data['low_price_20d'],
                    price_data['last_price'],
                    price_data['amplitude'],
                    price_data['position_ratio'],
                    today
                ))
                conn.commit()
                return True

    def run(self):
        """运行更新程序"""
        with self.app.app_context():
            try:
                self.init_connections()
                logger.info("开始价格范围更新")
                
                today = date.today()
                yesterday = today - timedelta(days=1)
                
                # 1. 获取所有现有记录
                existing_records = {}
                try:
                    records = PriceRange20d.query.all()
                    for record in records:
                        existing_records[record.symbol] = record
                    logger.info(f"从数据库获取到 {len(existing_records)} 个现有记录")
                except Exception as e:
                    logger.error(f"获取现有记录失败: {str(e)}")
                    raise
                
                # 2. 获取��有可用合约
                try:
                    futures_api = self.data_manager.get_futures_api()
                    available_contracts = futures_api.list_futures_contracts(settle='usdt')
                    valid_contracts = []
                    for contract in available_contracts:
                        symbol = contract.name.replace('_USDT', '')
                        valid_contracts.append({
                            'symbol': symbol,
                            'name': contract.name
                        })
                    logger.info(f"从交易所获取到 {len(valid_contracts)} 个有效合约")
                except Exception as e:
                    logger.error(f"获取合约列表失败: {str(e)}")
                    raise
                
                # 3. 处理每个合约
                update_count = 0
                new_count = 0
                for contract in valid_contracts:
                    try:
                        symbol = contract['symbol']
                        existing_record = existing_records.get(symbol)
                        
                        # 检查是否需要更新
                        need_update = False
                        if not existing_record:
                            logger.info(f"发现新合约: {symbol}")
                            need_update = True
                        elif existing_record.update_date < yesterday:
                            logger.info(f"合约 {symbol} 需要更新，最后更新日期: {existing_record.update_date}")
                            need_update = True
                        
                        if need_update:
                            # 获取K线数据
                            close_prices = self.get_ohlcv_data(symbol)
                            if not close_prices:
                                logger.warning(f"无法获取 {symbol} 的K线数据")
                                continue
                            
                            if len(close_prices) < 20:
                                logger.warning(f"{symbol} 的K线数据不足20天: {len(close_prices)}天")
                                continue
                            
                            # 计算价格范围
                            price_data = self.calculate_price_range(close_prices)
                            if not price_data:
                                logger.warning(f"无法计算 {symbol} 的价格范围")
                                continue
                            
                            try:
                                if existing_record:
                                    # 更新现有记录
                                    existing_record.high_price_20d = price_data['high_price_20d']
                                    existing_record.low_price_20d = price_data['low_price_20d']
                                    existing_record.last_price = price_data['last_price']
                                    existing_record.amplitude = price_data['amplitude']
                                    existing_record.position_ratio = price_data['position_ratio']
                                    existing_record.volume_24h = 0  # 初始化为0，等待tick更新
                                    existing_record.update_date = yesterday
                                    update_count += 1
                                    logger.info(f"更新合约 {symbol} 的价格范围数据")
                                else:
                                    # 创建新记录
                                    new_record = PriceRange20d(
                                        symbol=symbol,
                                        high_price_20d=price_data['high_price_20d'],
                                        low_price_20d=price_data['low_price_20d'],
                                        last_price=price_data['last_price'],
                                        amplitude=price_data['amplitude'],
                                        position_ratio=price_data['position_ratio'],
                                        volume_24h=0,  # 初始化为0，等待tick更新
                                        update_date=yesterday
                                    )
                                    db.session.add(new_record)
                                    new_count += 1
                                    logger.info(f"添加新合约 {symbol} 的价格范围数据")
                                
                                db.session.commit()
                                
                            except Exception as e:
                                logger.error(f"保存 {symbol} 数据失败: {str(e)}")
                                db.session.rollback()
                                continue
                            
                            time.sleep(0.5)  # 避免请求过于频繁
                            
                    except Exception as e:
                        logger.error(f"处理合约 {symbol} 时发生错误: {str(e)}")
                        continue
                
                logger.info(f"价格范围数据更新完成")
                logger.info(f"更新现有记录: {update_count} 个")
                logger.info(f"新增记录: {new_count} 个")
                
            except Exception as e:
                logger.error(f"更新过程发生错误: {str(e)}")
                raise

    def update_ticks(self):
        """更新实时行情数据"""
        with self.app.app_context():
            try:
                logger.info("开始更新实时行情数据")
                
                # 初始化连接（如果需要）
                if not self.data_manager:
                    self.init_connections()
                
                # 获取最新日期的所有品种
                latest_date = db.session.query(db.func.max(PriceRange20d.update_date)).scalar()
                logger.info(f"最新数据日期: {latest_date}")
                
                if not latest_date:
                    logger.warning("未找到任何价格范围数据")
                    return
                
                # 获取需要更新的品种列表
                symbols = PriceRange20d.query.filter_by(update_date=latest_date).all()
                if not symbols:
                    logger.warning("没有找到需要更新的品种")
                    return
                
                # 获取所有品种的符号列表
                symbol_list = [symbol.symbol for symbol in symbols]
                logger.info(f"需要更新的品种数量: {len(symbol_list)}")
                
                # 使用新的 get_ticks 方法获取行情数据
                ticker_dict = self.data_manager.get_ticks(symbol_list)
                logger.info(f"获取到的行情数据数量: {len(ticker_dict)}")
                
                # 获取当前时间
                current_time = datetime.now()
                
                # 更新每个品种的数据
                update_count = 0
                for symbol in symbols:
                    if symbol.symbol in ticker_dict:
                        ticker = ticker_dict[symbol.symbol]
                        last_price = Decimal(str(ticker.last))
                        old_price = symbol.last_price
                        
                        # 获取24小时成交量（USDT计价）
                        volume_24h = Decimal(str(ticker.volume_24h_settle or 0))
                        
                        # 计算新的振幅和位置比
                        high_price = Decimal(str(symbol.high_price_20d))
                        low_price = Decimal(str(symbol.low_price_20d))
                        new_amplitude = (high_price - low_price) / low_price if low_price > 0 else 0
                        new_position_ratio = (last_price - low_price) / (high_price - low_price) if (high_price - low_price) > 0 else 0
                        
                        # 更新数据
                        symbol.last_price = last_price
                        symbol.amplitude = float(new_amplitude)
                        symbol.position_ratio = float(new_position_ratio)
                        symbol.volume_24h = float(volume_24h)  # 更新24小时成交量
                        symbol.update_time = current_time
                        update_count += 1
                        
                        # 记录价格和成交量变化
                        if old_price != last_price:
                            logger.info(f"{symbol.symbol} 更新 - "
                                      f"价格: {old_price} -> {last_price}, "
                                      f"24h成交量: {volume_24h:,.0f} USDT")
                
                # 提交更改
                db.session.commit()
                logger.info(f"实时行情更新完成，成功更新了 {update_count} 个品种")
                
            except Exception as e:
                logger.error(f"实时行情更新失败: {str(e)}")
                db.session.rollback()
                raise

    def _update_price_ranges(self):
        """更新20日价格范围数据"""
        # 获取所有品种的20日高点
        price_ranges = self.data_manager.get_price_ranges()
        if not price_ranges:
            logger.warning("未获取到价格范围数据")
            return

        today = date.today()
        
        # 批量更新数据
        try:
            # 删除今日数据（如果存在）
            PriceRange20d.query.filter_by(update_date=today).delete()
            
            # 插入新数据
            for pr in price_ranges:
                price_range = PriceRange20d(
                    symbol=pr.symbol,
                    high_price_20d=pr.high_price,
                    low_price_20d=pr.low_price,
                    last_price=pr.last_price,
                    amplitude=pr.amplitude,
                    position_ratio=pr.position_ratio,
                    update_date=today
                )
                db.session.add(price_range)
            
            db.session.commit()
            logger.info(f"成功更新 {len(price_ranges)} 个品种的价格范围")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"保存价格范围数据失败: {str(e)}")
            raise

def run_scheduler():
    """行调度器"""
    logger.info("启动价格更新调度器")
    
    # 更新任务
    def price_range_job():
        try:
            logger.info(f"开始执行价格范围更新任务 - {datetime.now()}")
            updater = PriceUpdater()
            updater.run()
            logger.info("价格范围更新任务成功")
        except Exception as e:
            logger.error(f"价格范围更新任务失败: {str(e)}")

    def tick_update_job():
        try:
            logger.info(f"开始执行实时行情更新任务 - {datetime.now()}")
            updater = PriceUpdater()
            updater.update_ticks()
            logger.info("实时行情更新任务完成")
        except Exception as e:
            logger.error(f"实时行情更新任务失败: {str(e)}")

    # 设置每天 0:01 执行价格范围更新
    schedule.every().day.at("00:01").do(price_range_job)
    
    # 设置每分钟执行实时行情更新
    schedule.every(1).minutes.do(tick_update_job)
    
    # 启动时先执行一次价格范围更新

    price_range_job()
    
    # 持续运行调度器
    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except KeyboardInterrupt:
            logger.info("程序被手动停止")
            break
        except Exception as e:
            logger.error(f"调度器运行错误: {str(e)}")
            time.sleep(60)  # 发生错误时等待一分钟后继续

if __name__ == "__main__":
    try:
        # 根据命令行参数决定运行模式
        if len(sys.argv) > 1:
            if sys.argv[1] == '--once':
                # 单次运行价格范围更新
                updater = PriceUpdater()
                updater.run()
            elif sys.argv[1] == '--tick':
                # 单次运行实时行情更新
                updater = PriceUpdater()
                updater.update_ticks()
        else:
            # 调度器模式
            run_scheduler()
    except Exception as e:
        logger.error(f"程序运行失败: {str(e)}")
        sys.exit(1) 