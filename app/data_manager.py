from typing import List
from app.database import DatabaseConnection, DatabaseManager
from app.models import Position, FuturesContractInfo, AccountInfo
import logging

logger = logging.getLogger(__name__)

class DataManager:
    def __init__(self, server_id: str = None):
        if server_id is None:
            raise ValueError("服务器ID不能为空")
        self.server_id = server_id
        self.db_manager = DatabaseManager()

    def get_account_positions(self, account_info: AccountInfo) -> List[Position]:
        if not account_info:
            logger.warning("No account info provided")
            return []
            
        try:
            logger.debug(f"Getting positions for account {account_info.acct_id}")
            positions = []
            
            # 从产品组合中获取持仓信息
            for product in account_info.stg_comb_product_gateio:
                logger.debug(f"Processing product: {product}")
                
                # 使用 comb_name 获取产品列表
                if not product.comb_name:
                    logger.warning(f"Empty comb_name for product {product}")
                    continue
                
                # 将组合名称分割成单个产品
                product_symbols = [
                    symbol.strip() 
                    for symbol in product.comb_name.split('#')
                    if symbol.strip()  # 忽略空字符串
                ]
                
                logger.debug(f"Split products from comb_name: {product_symbols}")
                
                # 为每个产品创建持仓信息
                for symbol in product_symbols:
                    positions.append(Position(
                        symbol=symbol,
                        name=symbol,  # 使用symbol作为名称
                        is_selected=True,  # 已在组合中的产品标记为已选择
                        money=product.money,  # 使用组合的资金
                        discount=product.discount  # 使用组合的仓位
                    ))
            
            sorted_positions = sorted(positions, key=lambda x: x.symbol)
            logger.debug(f"Returning {len(sorted_positions)} positions")
            return sorted_positions
            
        except Exception as e:
            logger.exception("Error getting account positions")
            raise

    def get_futures_contracts(self) -> List[FuturesContractInfo]:
        try:
            db = DatabaseConnection(self.server_id)
            with db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT DISTINCT symbol, symbol as name
                        FROM futures_contract_info
                        ORDER BY symbol
                    """)
                    contracts = cursor.fetchall()
                    return [
                        FuturesContractInfo(
                            symbol=contract['symbol'],
                            name=contract['name']
                        )
                        for contract in contracts
                    ]
        except Exception as e:
            logger.exception("Error getting futures contracts")
            raise

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