from typing import List, Optional, Dict
import pymysql
from flask import current_app
from contextlib import contextmanager
from app.models import AccountInfo, ProductInfo
import time
import logging

logger = logging.getLogger(__name__)

class DatabaseConnection:
    def __init__(self, server_id: str):
        self.server_id = f'server{server_id}'
        self.max_retries = 3
        self.retry_delay = 1  # 重试延迟（秒）
        
    def get_db_config(self):
        """获取数据库配置"""
        if not current_app:
            raise RuntimeError("No Flask application context")
        return current_app.config['DATABASES'][self.server_id]
        
    @contextmanager
    def get_connection(self):
        """获取数据库连接"""
        connection = None
        try:
            # 获取数据库配置
            db_config = self.get_db_config()
            
            # 创建数据库连接
            connection = pymysql.connect(
                host=db_config['HOST'],
                user=db_config['USER'],
                password=db_config['PASSWORD'],
                database=db_config['NAME'],
                port=db_config['PORT'],
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor,
                connect_timeout=5,
                read_timeout=30,
                write_timeout=30
            )
            
            yield connection
            connection.commit()  # 如果没有异常，提交事务
            
        except Exception as e:
            if connection:
                connection.rollback()  # 发生异常时回滚
            logger.error(f"Database connection error: {str(e)}")
            raise
            
        finally:
            if connection:
                connection.close()  # 确保连接被关闭

class DatabaseManager:
    @staticmethod
    def get_user_accounts(server_id: str, username: str) -> List[str]:
        """获取用户关联的所有账户ID"""
        db = DatabaseConnection(server_id)
        
        with db.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT ua.acct_id
                    FROM users u
                    JOIN user_accounts ua ON u.id = ua.user_id
                    JOIN acct_info ai ON ua.acct_id = ai.acct_id
                    WHERE u.username = %s AND ai.group_id = 3
                """, (username,))
                return [row['acct_id'] for row in cursor.fetchall()]

    @staticmethod
    def get_account_info(server_id: str, username: str) -> List[AccountInfo]:
        """获取用户的所有账户信息"""
        db = DatabaseConnection(server_id)
        account_info_list = []
        
        # 首先获取用户关联的所有账户ID
        acct_ids = DatabaseManager.get_user_accounts(server_id, username)
        if not acct_ids:
            return []
            
        with db.get_connection() as conn:
            with conn.cursor() as cursor:
                # 获取所有关联账户的基本信息
                cursor.execute("""
                    SELECT acct_id, acct_name, apikey, secretkey, apipass, 
                           email, group_id, state, status
                    FROM acct_info
                    WHERE acct_id IN (%s)
                """ % ','.join(['%s'] * len(acct_ids)), tuple(acct_ids))
                accounts_data = cursor.fetchall()
                
                # 获取所有关联账户的产品组合信息
                for account in accounts_data:
                    cursor.execute("""
                        SELECT asg.product_list, asg.name, asg.status,
                               asg.money, asg.discount,
                               scp.comb_name
                        FROM acct_stg_future_gateio asg
                        LEFT JOIN stg_comb_product_gateio scp 
                            ON asg.product_list = scp.product_comb
                        WHERE asg.acct_id = %s
                    """, (account['acct_id'],))
                    product_data = cursor.fetchall()
                    
                    products = [
                        ProductInfo(
                            product_list=row['product_list'],
                            name=row['name'],
                            status=row['status'],
                            comb_name=row['comb_name'] if row['comb_name'] else '',
                            money=float(row['money']) if row['money'] is not None else 0.0,
                            discount=float(row['discount']) if row['discount'] is not None else 0.0
                        )
                        for row in product_data
                    ]
                    
                    account_info_list.append(AccountInfo(
                        acct_id=str(account['acct_id']),
                        acct_name=account['acct_name'],
                        apikey=account['apikey'],
                        secretkey=account['secretkey'],
                        apipass=account['apipass'],
                        email=account['email'],
                        group_id=account['group_id'],
                        state=account['state'],
                        status=account['status'],
                        stg_comb_product_gateio=products
                    ))
                
        return account_info_list

    @staticmethod
    def create_user(server_id: str, username: str, email: str, password_hash: str) -> Optional[int]:
        """创建新用户"""
        db = DatabaseConnection(server_id)
        
        with db.get_connection() as conn:
            with conn.cursor() as cursor:
                try:
                    cursor.execute("""
                        INSERT INTO users (username, email, password_hash)
                        VALUES (%s, %s, %s)
                    """, (username, email, password_hash))
                    conn.commit()
                    return cursor.lastrowid
                except pymysql.IntegrityError:
                    return None

    @staticmethod
    def link_user_account(server_id: str, user_id: int, acct_id: str) -> bool:
        """关联用户和账户"""
        db = DatabaseConnection(server_id)
        
        with db.get_connection() as conn:
            with conn.cursor() as cursor:
                try:
                    cursor.execute("""
                        INSERT INTO user_accounts (user_id, acct_id)
                        VALUES (%s, %s)
                    """, (user_id, acct_id))
                    conn.commit()
                    return True
                except pymysql.IntegrityError:
                    return False

    @staticmethod
    def get_futures_contracts(server_id: str) -> List[Dict]:
        """从指定服务器获取期货合约信息"""
        db = DatabaseConnection(server_id)
        
        with db.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT symbol, name
                    FROM futures_contract_info
                    ORDER BY symbol
                """)
                return cursor.fetchall()

    @staticmethod
    def save_position(server_id: str, acct_id: str, symbol: str, name: str):
        """保存持信息到指定服务器"""
        db = DatabaseConnection(server_id)
        
        with db.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO positions (acct_id, symbol, name)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                    name = VALUES(name)
                """, (acct_id, symbol, name))
                conn.commit()

    @staticmethod
    def test_connection(server_id: str):
        """测试数据库连接和表结构"""
        db = DatabaseConnection(server_id)
        
        with db.get_connection() as conn:
            with conn.cursor() as cursor:
                # 获取所有表名
                cursor.execute("""
                    SHOW TABLES
                """)
                tables = [row.values()[0] for row in cursor.fetchall()]
                print(f"数据库中的表: {tables}")
                
                # 检查 acct_info 表结构
                cursor.execute("""
                    DESCRIBE acct_info
                """)
                columns = cursor.fetchall()
                print("\nacct_info 表结构:")
                for col in columns:
                    print(f"{col['Field']}: {col['Type']}") 

    @staticmethod
    def show_table_structure(server_id: str, table_name: str):
        """显示指定表的结构"""
        db = DatabaseConnection(server_id)
        
        with db.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"""
                    DESCRIBE {table_name}
                """)
                columns = cursor.fetchall()
                print(f"\n{table_name} 表结构:")
                for col in columns:
                    print(f"{col['Field']}: {col['Type']}")