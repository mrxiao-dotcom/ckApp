from typing import List, Optional
from app.database import DatabaseConnection, DatabaseManager
from app.models import Position, FuturesContractInfo, AccountInfo
import logging
from gate_api import ApiClient, Configuration, FuturesApi, SpotApi
from gate_api.exceptions import ApiException, GateApiException
import os
from app import setup_logging
import math
import time

# 配置日志
logger = setup_logging(
    'data_manager',
    os.path.join('logs', 'data_manager.log')
)

class DataManager:
    def __init__(self, server_id: str):
        self.server_id = server_id
        self.db_connection = DatabaseConnection(server_id)
        self.account_info = None
        self.futures_api = None
        self.api_client = None
        self.logger = logger
        self._positions_cache = {}  # 添加持仓缓存
        self._positions_cache_time = 0  # 缓存时间戳
    
    def _init_api(self):
        """初始化API客户端"""
        if not self.account_info:
            raise ValueError("未设置账户信息，请先调用 init_api_credentials")
            
        try:
            # 创建API配置
            config = Configuration(
                key=self.account_info.apikey,
                secret=self.account_info.secretkey
            )
            
            # 创建API客户端
            self.api_client = ApiClient(config)
            
            # 创建期货API实例
            self.futures_api = FuturesApi(self.api_client)
            
            logger.debug(f"API客户端初始化成功")
            
        except Exception as e:
            logger.error(f"API客户端初始化失败: {str(e)}")
            raise
    
    def get_account_info(self, account_id: str) -> Optional[AccountInfo]:
        """获取账户API信息"""
        try:
            with self.db_connection.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT acct_id, acct_name, apikey, secretkey, apipass, 
                               email, group_id, state, status
                        FROM acct_info
                        WHERE acct_id = %s
                    """, (account_id,))
                    account_data = cursor.fetchone()
                    
                    if not account_data:
                        logger.warning(f"未找到账户 {account_id} 的信息")
                        return None
                    
                    # 创建 AccountInfo 对象
                    account_info = AccountInfo(
                        acct_id=str(account_data['acct_id']),
                        acct_name=account_data['acct_name'],
                        apikey=account_data['apikey'],
                        secretkey=account_data['secretkey'],
                        apipass=account_data['apipass'],
                        email=account_data['email'],
                        group_id=account_data['group_id'],
                        state=account_data['state'],
                        status=account_data['status'],
                        stg_comb_product_gateio=[]  # 空列表，因为这里不需要策略组合信息
                    )
                    
                    return account_info
                    
        except Exception as e:
            logger.error(f"获取账户 {account_id} 信息失败: {str(e)}")
            return None
    
    def _get_account_positions(self, account_info: AccountInfo, force_update=False):
        """获取账户持仓信息（带缓存）"""
        current_time = time.time()
        cache_key = account_info.acct_id
        
        # 如果缓存存在且未过期（3秒内）且不强制更新
        if not force_update and cache_key in self._positions_cache:
            if current_time - self._positions_cache_time < 3:
                return self._positions_cache[cache_key]
        
        try:
            # 确保API已初始化
            if not self.futures_api:
                self.init_api(account_info)
            
            # 获取所有持仓信息
            positions = self.futures_api.list_positions("usdt", holding="true")
            
            # 更新缓存
            self._positions_cache[cache_key] = positions
            self._positions_cache_time = current_time
            
            return positions
            
        except Exception as e:
            logger.error(f"获取账户持仓失败: {str(e)}")
            return None
    
    def init_api(self, account_info: AccountInfo):
        """使用账户信息初始化API"""
        self.account_info = account_info
        self._init_api()
    
    def get_futures_api(self):
        """获取期货API实例"""
        if not self.futures_api:
            self._init_api()
        return self.futures_api

    def get_futures_contracts(self) -> List[FuturesContractInfo]:
        """获取所有期货合约"""
        try:
            futures_api = self.get_futures_api()
            contracts = futures_api.list_futures_contracts(settle='usdt')
            
            # 移除 _USDT 后缀
            return [
                FuturesContractInfo(
                    symbol=contract.name.replace('_USDT', ''),
                    name=contract.name.replace('_USDT', '')
                )
                for contract in contracts
            ]
        except (ApiException, GateApiException) as e:
            logger.error(f"获取合约列表失败: {str(e)}")
            return []

    def merge_positions(self, existing_positions: List[Position], 
                       new_contracts: List[FuturesContractInfo]) -> List[Position]:
        existing_symbols = {p.symbol for p in existing_positions}
        
        for contract in new_contracts:
            if contract.symbol not in existing_symbols:
                existing_positions.append(Position(
                    symbol=contract.symbol,
                    name=contract.name,
                    is_selected=False,
                    money=0.0,
                    discount=0.0
                ))
                
        return sorted(existing_positions, key=lambda x: x.symbol) 

    def get_product_config(self, acct_id: str) -> dict:
        """获取产品组合配置"""
        try:
            db = DatabaseConnection(self.server_id)
            with db.get_connection() as conn:
                with conn.cursor() as cursor:
                    # 获取账户的产品组合配置
                    cursor.execute("""
                        SELECT asg.product_list, asg.money, asg.discount,
                               scp.comb_name
                        FROM acct_stg_future_gateio asg
                        LEFT JOIN stg_comb_product_gateio scp 
                            ON asg.product_list = scp.product_comb
                        WHERE asg.acct_id = %s
                    """, (acct_id,))
                    config = cursor.fetchone()
                    
                    if config:
                        # 如果找到配置，返回组合信息
                        return {
                            'money': float(config['money']) if config['money'] is not None else 0,
                            'discount': float(config['discount']) if config['discount'] is not None else 0,
                            'product_list': config['product_list'] or '',  # 组合名
                            'comb_name': config['comb_name'] or '',  # 组合内产品明细
                            'symbols': config['comb_name'].split('#') if config['comb_name'] else []
                        }
                    
                    # 如果没有找到配置，返回空结果
                    return {
                        'money': 0,
                        'discount': 0,
                        'product_list': '',
                        'comb_name': '',
                        'symbols': []
                    }
                
        except Exception as e:
            logger.exception(f"Error getting product config for account {acct_id}")
            raise

    def save_product_config(self, acct_id: str, money: float, discount: float, symbols: List[str], product_list: str):
        """保存产品组合配置
        
        Args:
            acct_id: 账户ID
            money: 资金金额
            discount: 仓位比例
            symbols: 选中的合约列表
            product_list: 组合名称
        """
        try:
            db = DatabaseConnection(self.server_id)
            with db.get_connection() as conn:
                with conn.cursor() as cursor:
                    # 首先检查是否已存在配置
                    cursor.execute("""
                        SELECT 1 FROM acct_stg_future_gateio
                        WHERE acct_id = %s
                    """, (acct_id,))
                    exists = cursor.fetchone()

                    if exists:
                        # 更新现有配置 - product_list 保存组合名称
                        cursor.execute("""
                            UPDATE acct_stg_future_gateio
                            SET product_list = %s,
                                money = %s,
                                discount = %s
                            WHERE acct_id = %s
                        """, (product_list, money, discount, acct_id))
                    else:
                        # 创建新配置 - product_list 保存组合名称
                        cursor.execute("""
                            INSERT INTO acct_stg_future_gateio
                            (acct_id, product_list, money, discount)
                            VALUES (%s, %s, %s, %s)
                        """, (acct_id, product_list, money, discount))

                    # 更新组合内容 - comb_name 保存品种列表
                    cursor.execute("""
                        UPDATE stg_comb_product_gateio
                        SET comb_name = %s
                        WHERE product_comb = %s
                    """, ('#'.join(symbols), product_list))

                    conn.commit()
        except Exception as e:
            logger.exception(f"Error saving product config for account {acct_id}")
            raise

    def get_strategies(self) -> List[dict]:
        """获取所有策略组合"""
        try:
            db = DatabaseConnection(self.server_id)
            with db.get_connection() as conn:
                with conn.cursor() as cursor:
                    # 获取所有可用的策略组合
                    cursor.execute("""
                        SELECT DISTINCT product_comb, comb_name
                        FROM stg_comb_product_gateio
                        ORDER BY product_comb
                    """)
                    strategies = cursor.fetchall()
                    return [
                        {
                            'product_comb': strategy['product_comb'],  # 组合标识
                            'comb_name': strategy['comb_name'] or '',  # 组合内容
                            'display_name': f"{strategy['product_comb']} - {strategy['comb_name'] or '无'}"  # 显示名称
                        }
                        for strategy in strategies
                    ] if strategies else []
        except Exception as e:
            logger.exception("Error getting strategies")
            raise

    def get_strategy(self, product_comb: str) -> dict:
        """获取指定策略组合的详细信息"""
        try:
            db = DatabaseConnection(self.server_id)
            with db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT product_comb, comb_name
                        FROM stg_comb_product_gateio
                        WHERE product_comb = %s
                    """, (product_comb,))
                    strategy = cursor.fetchone()
                    if strategy:
                        return {
                            'product_comb': strategy['product_comb'],  # 组合标识
                            'comb_name': strategy['comb_name'] or '',  # 组合内容
                            'symbols': strategy['comb_name'].split('#') if strategy['comb_name'] else []  # 拆分的产品列表
                        }
                    return {
                        'product_comb': '',
                        'comb_name': '',
                        'symbols': []
                    }
        except Exception as e:
            logger.exception("Error getting strategy")
            raise

    def create_strategy(self, product_comb: str, comb_name: str, symbols: List[str]):
        """创建新的策略组合"""
        try:
            db = DatabaseConnection(self.server_id)
            with db.get_connection() as conn:
                with conn.cursor() as cursor:
                    # 检查是否已存在
                    cursor.execute("""
                        SELECT 1 FROM stg_comb_product_gateio
                        WHERE product_comb = %s
                    """, (product_comb,))
                    if cursor.fetchone():
                        raise ValueError("策略组合已存在")
                    
                    # 创建新策略
                    cursor.execute("""
                        INSERT INTO stg_comb_product_gateio
                        (product_comb, comb_name)
                        VALUES (%s, %s)
                    """, (product_comb, '#'.join(symbols)))
                    conn.commit()
        except Exception as e:
            logger.exception("Error creating strategy")
            raise 

    def get_futures_candlesticks(self, symbol: str, from_time: int, to_time: int, interval: str = '1d'):
        """获取期货K线数据"""
        try:
            futures_api = self.get_futures_api()
            # 添加 _USDT 后缀
            contract = f"{symbol}_USDT"
            
            logger.debug(f"获取 {contract} K线数据")
            
            # 使用正确的参数名称调用API
            response = futures_api.list_futures_candlesticks(
                "usdt",  # settle 参数
                contract,  # 合约名称
                _from=from_time,  # 注意这里使用 _from
                to=to_time,
                interval=interval
            )
            
            if not response:
                logger.warning(f"{contract} 没有K线数据")
                return None
            
            # 转换响应数据
            candles = []
            for item in response:
                candle = {
                    'timestamp': item.t,  # 时间戳
                    'volume': float(item.v),  # 成交量
                    'close': float(item.c),  # 收盘价
                    'high': float(item.h),  # 最高价
                    'low': float(item.l),  # 最低价
                    'open': float(item.o)  # 开盘价
                }
                candles.append(candle)
            
            logger.debug(f"获取到 {len(candles)} 条K线数据")
            return candles
            
        except (ApiException, GateApiException) as e:
            logger.error(f"获取K线数据失败: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"获取K线数据时发生错误: {str(e)}")
            return None

    def get_ticks(self, symbols):
        """获取实时行情数据"""
        try:
            futures_api = self.get_futures_api()
            
            # 获取所有行情数据
            tickers = futures_api.list_futures_tickers(settle='usdt')
            
            # 创建映射，移除 Gate.io 返回数据中的 _USDT 后缀
            result = {}
            for ticker in tickers:
                original_symbol = ticker.contract
                processed_symbol = original_symbol.replace('_USDT', '')
                
                if processed_symbol in symbols:
                    result[processed_symbol] = ticker
                    logger.debug(f"匹配到合约: {processed_symbol}")
            
            # 记录匹配结果
            logger.debug(f"数据库中的合约总数: {len(symbols)}")
            logger.debug(f"Gate.io返回的合约总数: {len(tickers)}")
            logger.debug(f"成功匹配的合约数量: {len(result)}")
            
            return result
            
        except (ApiException, GateApiException) as e:
            logger.error(f"获取实时行情失败: {str(e)}")
            return {}

    def create_order(self, account_info: AccountInfo, symbol: str, direction: str, amount: float, leverage: int) -> bool:
        """创建订单"""
        try:
            # 确保API已初始化
            if not self.futures_api:
                self.init_api(account_info)
            
            # 构建合约名称
            contract = f"{symbol}_USDT"
            
            # 1. 获取合约信息
            try:
                contract_info = self.futures_api.get_futures_contract(
                    settle='usdt',
                    contract=contract
                )
                
                # 获取合约参数
                max_size = float(contract_info.order_size_max)  # 最大下单量
                min_size = float(contract_info.order_size_min)  # 最小下单量
                contract_size = float(contract_info.quanto_multiplier)  # 合约面值
                current_price = float(contract_info.last_price)  # 当前价格
                leverage_max = float(contract_info.leverage_max)  # 最大杠杆
                
                logger.info(f"合约信息: {symbol} "
                           f"最大下单量={max_size}, 最小下单量={min_size}, "
                           f"合约面值={contract_size}, 当前价格={current_price}, "
                           f"最大杠杆={leverage_max}")
                
            except Exception as e:
                logger.error(f"获取合约信息失败: {str(e)}")
                return False
            
            # 2. 设置杠杆
            try:
                # 设置杠杆倍数
                actual_leverage = min(leverage, int(leverage_max))
                self.futures_api.update_position_leverage(
                    settle='usdt',
                    contract=contract,
                    leverage=str(actual_leverage)
                )
                logger.info(f"设置杠杆成功: {symbol} {actual_leverage}x")
                
            except Exception as e:
                logger.error(f"设置杠杆失败: {str(e)}")
                return False
            
            # 3. 计算并执行分批下单
            try:
                # 计算合约张数
                contract_value = contract_size * current_price  # 每张合约价值
                total_size = (amount * actual_leverage) / contract_value  # 需要的合约张数
                
                # 对合约张数进行上取整，确保至少有1张
                total_size = max(1, math.ceil(total_size))
                
                # 如果小于最小下单量，则调整到最小下单量
                if total_size < min_size:
                    logger.warning(f"下单量 {total_size} 小于最小下单量 {min_size}，将使用最小下单量")
                    total_size = min_size
                
                logger.info(f"计算得到合约张数: {total_size} 张")
                
                # 分批下单
                while total_size > 0:
                    # 确定本次下单量
                    batch_size = min(total_size, max_size)
                    total_size -= batch_size
                    
                    # 根据方向设置正负
                    order_size = int(batch_size) if direction == 'long' else -int(batch_size)
                    
                    # 创建订单对象
                    from gate_api import FuturesOrder
                    futures_order = FuturesOrder(
                        contract=contract,
                        size=str(order_size),  # 合约张数（整数）
                        price='0',  # 市价单
                        tif='ioc'  # 立即成交或取消
                    )
                    
                    # 创建订单
                    order = self.futures_api.create_futures_order(
                        settle='usdt',
                        futures_order=futures_order
                    )
                    
                    if order.status == 'finished':
                        logger.info(f"下单成功: {symbol} {order_size} 张, "
                                  f"剩余数量: {total_size}, 订单状态: {order.status}")
                    else:
                        logger.error(f"下单失败: {symbol} {order_size} 张, 订单状态: {order.status}")
                        return False
                
                return True
                
            except Exception as e:
                logger.error(f"下单失败: {str(e)}")
                return False
                
        except Exception as e:
            logger.error(f"创建订单失败: {str(e)}")
            return False
    
    def close_position(self, account_info: AccountInfo, symbol: str) -> bool:
        """平仓指定品种"""
        try:
            # 获取所有持仓信息（强制更新缓存）
            positions = self._get_account_positions(account_info, force_update=True)
            if not positions:
                logger.warning(f"没有找到任何持仓")
                return False
            
            # 构建合约名称
            contract = f"{symbol}_USDT"
            
            # 查找指定合约的持仓
            position = None
            for pos in positions:
                if pos.contract == contract and float(pos.size) != 0:
                    position = pos
                    break
            
            if not position:
                logger.warning(f"没有找到 {symbol} 的持仓")
                return False
            
            # 创建平仓订单对象
            from gate_api import FuturesOrder
            futures_order = FuturesOrder(
                contract=contract,
                size=str(int(-float(position.size))),  # 持仓反向下单，确保是整数
                price='0',  # 市价单
                tif='ioc'  # 立即成交或取消
            )
            
            # 创建平仓订单
            order = self.futures_api.create_futures_order(
                settle='usdt',
                futures_order=futures_order
            )
            
            if order.status == 'finished':
                logger.info(f"平仓成功: {symbol}, 订单状态: {order.status}")
                return True
            else:
                logger.error(f"平仓失败: {symbol}, 订单状态: {order.status}")
                return False
            
        except Exception as e:
            logger.error(f"平仓失败: {str(e)}")
            return False

    def get_position_pnl(self, account_info: AccountInfo, symbol: str) -> Optional[float]:
        """获取持仓未实现盈亏"""
        try:
            # 获取所有持仓信息（使用缓存）
            positions = self._get_account_positions(account_info)
            if not positions:
                logger.warning(f"没有找到任何持仓")
                return None
            
            # 构建合约名称
            contract = f"{symbol}_USDT"
            
            # 查找指定合约的持仓
            position = None
            for pos in positions:
                if pos.contract == contract and float(pos.size) != 0:
                    position = pos
                    break
            
            if not position:
                logger.warning(f"没有找到 {symbol} 的持仓")
                return None
            
            # 获取未实现盈亏
            unrealised_pnl = float(position.unrealised_pnl)
            size = float(position.size)
            
            # 如果是空仓，需要反向计算盈��
            pnl = unrealised_pnl
            
            logger.debug(f"获取持仓盈亏: {symbol} 盈亏={pnl:+.2f}")
            return pnl
            
        except Exception as e:
            logger.error(f"获取持仓盈亏失败: {str(e)}")
            return None

    def get_account_positions(self, account_info: AccountInfo) -> List[Position]:
        """获取账户当前持仓"""
        try:
            # 使用缓存的持仓信息
            positions = self._get_account_positions(account_info)
            if not positions:
                return []
            
            # 转换为 Position 对象列表
            result = []
            for pos in positions:
                if float(pos.size) != 0:  # 只返回有持仓的品种
                    result.append(Position(
                        symbol=pos.contract.replace('_USDT', ''),
                        name=pos.contract,
                        is_selected=True,
                        money=float(pos.value),
                        discount=float(pos.leverage)
                    ))
            
            return result
            
        except Exception as e:
            logger.error(f"获取账户持仓失败: {str(e)}")
            return []

    def get_all_accounts(self) -> List[str]:
        """获取所有��户ID"""
        try:
            with self.db_connection.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT DISTINCT account_id 
                        FROM monitor_list 
                        WHERE is_active = 1
                    """)
                    accounts = [str(row['account_id']) for row in cursor.fetchall()]
                    logger.info(f"获取到 {len(accounts)} 个活跃账户")
                    return accounts
                    
        except Exception as e:
            logger.error(f"获取账户列表失败: {str(e)}")
            return []

    def get_kline_data(self, symbol: str, interval: str = '1d', limit: int = 21) -> List:
        """获取K线数据
        
        Args:
            symbol: 合约名称
            interval: K线间隔 (1d表示日线)
            limit: 获取数量
            
        Returns:
            List of [timestamp, open, high, low, close, volume]
        """
        try:
            if not self.futures_api:
                self._init_api()
            
            # 添加 _USDT 后缀
            contract = f"{symbol}_USDT"
            
            # 使用期货K线接口
            candlesticks = self.futures_api.list_futures_candlesticks(
                settle='usdt',  # 结算币种
                contract=contract,
                interval=interval,
                limit=limit
            )
            
            logger.info(f"获取到 {symbol} 的 {len(candlesticks) if candlesticks else 0} 条K线数据")
            return candlesticks
            
        except Exception as e:
            logger.error(f"获取K线数据失败: {str(e)}")
            return []