from app import create_app
from app.database import DatabaseConnection, DatabaseManager

def check_database():
    app = create_app()
    with app.app_context():
        print("\n=== 检查数据库表结构 ===")
        
        # 检查认证相关表
        print("\n认证相关表:")
        DatabaseManager.show_table_structure('1', 'users')
        DatabaseManager.show_table_structure('1', 'user_sessions')
        DatabaseManager.show_table_structure('1', 'user_accounts')
        
        # 检查业务相关表
        print("\n业务相关表:")
        DatabaseManager.show_table_structure('1', 'acct_info')
        DatabaseManager.show_table_structure('1', 'acct_stg_future_gateio')
        DatabaseManager.show_table_structure('1', 'stg_comb_product_gateio')
        
        # 检查表中的数据
        print("\n=== 检查表数据 ===")
        db = DatabaseConnection('1')
        with db.get_connection() as conn:
            with conn.cursor() as cursor:
                # 检查用户
                cursor.execute("SELECT id, username, email FROM users")
                users = cursor.fetchall()
                print("\n用户列表:")
                for user in users:
                    print(f"ID: {user['id']}, 用户名: {user['username']}, 邮箱: {user['email']}")
                
                # 检查用户会话
                cursor.execute("""
                    SELECT us.id, us.user_id, us.is_active, 
                           u.username
                    FROM user_sessions us
                    JOIN users u ON us.user_id = u.id
                    ORDER BY us.created_at DESC
                    LIMIT 5
                """)
                sessions = cursor.fetchall()
                print("\n最近的会话:")
                for session in sessions:
                    print(f"会话ID: {session['id']}, "
                          f"用户: {session['username']}, "
                          f"状态: {'活动' if session['is_active'] else '已结束'}")
                
                # 检查账户关联
                cursor.execute("""
                    SELECT ua.user_id, ua.acct_id, u.username, ai.acct_name
                    FROM user_accounts ua
                    JOIN users u ON ua.user_id = u.id
                    JOIN acct_info ai ON ua.acct_id = ai.acct_id
                """)
                accounts = cursor.fetchall()
                print("\n用户账户关联:")
                for account in accounts:
                    print(f"用户: {account['username']}, "
                          f"账户ID: {account['acct_id']}, "
                          f"账户名称: {account['acct_name']}")
                
                # 检查产品组合
                cursor.execute("""
                    SELECT asg.acct_id, asg.product_list, asg.name, asg.status,
                           asg.money, asg.discount,
                           scp.comb_name
                    FROM acct_stg_future_gateio asg
                    LEFT JOIN stg_comb_product_gateio scp 
                        ON asg.product_list = scp.product_comb
                    ORDER BY asg.acct_id
                """)
                products = cursor.fetchall()
                print("\n产品组合信息:")
                for product in products:
                    print(f"账户ID: {product['acct_id']}, "
                          f"名称: {product['name']}, "
                          f"组合: {product['comb_name'] or '无'}, "
                          f"资金: {product['money']}, "
                          f"仓位: {product['discount']}, "
                          f"状态: {product['status']}")

if __name__ == '__main__':
    check_database()
