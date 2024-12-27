from flask import Blueprint, render_template, request, jsonify, redirect, url_for, current_app
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime, timedelta
from app import db
from app.models import User, PriceRange20d, MonitorList, SyncStatus, OscillationMonitor
from app.auth import AuthService
from app.data_manager import DataManager
from app.database import DatabaseManager
import logging
from typing import Optional

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# 创建蓝图 - 重命名为更具描述性的名称
auth_bp = Blueprint('auth', __name__)
main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    return redirect(url_for('auth.login'))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            # 支持 JSON 格式的请求
            data = request.json
            username = data.get('username')
            password = data.get('password')
            server_id = data.get('server')
            
            logger.info(f"尝试登录: username={username}, server_id={server_id}")
            
            if not all([username, password, server_id]):
                return jsonify({'error': '请填写所有必填字段'}), 400
            
            user = AuthService.authenticate_user(username, password, server_id)
            if user:
                login_user(user)
                user.update_last_login()
                token = AuthService.create_session(user)
                
                # 如果用户没有账户，返回空列表
                accounts = []
                if user.account_info_list:
                    accounts = [
                        {
                            'acct_id': acc.acct_id,
                            'acct_name': acc.acct_name,
                            'email': acc.email,
                            'state': acc.state,
                            'status': acc.status
                        }
                        for acc in user.account_info_list
                    ]
                
                logger.info(f"用户 {username} 登录成功")
                return jsonify({
                    'token': token,
                    'accounts': accounts,
                    'hasAccounts': bool(accounts)
                })
                
            logger.warning(f"用户 {username} 登录失败: 用户名或密码错误")
            return jsonify({'error': '用户名或密码错误'}), 401
            
        except Exception as e:
            logger.error(f"登录过程发生错误: {str(e)}")
            return jsonify({'error': '登录失败，请重试'}), 500
            
    return render_template('login.html', config=current_app.config)

@auth_bp.route('/logout')
@login_required
def logout():
    token = request.headers.get('Authorization')
    if token:
        AuthService.invalidate_session(token)
    logout_user()
    return redirect(url_for('auth.login'))

@main_bp.route('/main')
@login_required
def main():
    return render_template('main.html')

@main_bp.route('/api/positions')
@login_required
def get_positions():
    if not current_user.current_server:
        server_id = request.headers.get('X-Server-ID')
        if not server_id:
            return jsonify({'error': '未选择服务器'}), 400
        current_user.current_server = server_id
    
    acct_id = request.args.get('acct_id')
    if not acct_id:
        return jsonify({'error': '未指定账户ID'}), 400
    
    try:
        logger.debug(f"Getting positions for account {acct_id} on server {current_user.current_server}")
        
        # 如果 account_info_list 为空，重新获取
        if not current_user.account_info_list:
            current_user.account_info_list = DatabaseManager.get_account_info(
                current_user.current_server,
                current_user.username
            )
            if not current_user.account_info_list:
                return jsonify({'error': '无法获取账户信息'}), 500
        
        # 查找账户信息
        account_info = next(
            (acc for acc in current_user.account_info_list if acc.acct_id == acct_id),
            None
        )
        
        if not account_info:
            logger.error(f"Invalid account ID: {acct_id}")
            return jsonify({'error': '无效的账户ID'}), 400
            
        logger.debug(f"Found account info: {account_info}")
        
        # 获取持仓信息
        data_manager = DataManager(current_user.current_server)
        positions = data_manager.get_account_positions(account_info)
        logger.debug(f"Got positions: {positions}")
        
        return jsonify([{
            'symbol': p.symbol,
            'name': p.name,
            'is_selected': p.is_selected,
            'money': p.money,
            'discount': p.discount
        } for p in positions])
        
    except Exception as e:
        logger.exception("Error getting positions")
        return jsonify({'error': str(e)}), 500

@main_bp.route('/api/futures_contracts')
@login_required
def get_futures_contracts():
    if not current_user.current_server:
        return jsonify({'error': '未选择服务器'}), 400
        
    try:
        data_manager = DataManager(current_user.current_server)
        contracts = data_manager.get_futures_contracts()
        return jsonify([c.__dict__ for c in contracts])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main_bp.route('/api/import_contracts', methods=['POST'])
@login_required
def import_contracts():
    if not current_user.current_server:
        return jsonify({'error': '未选择服务器'}), 400
        
    data = request.json
    acct_id = data.get('acct_id')
    selected_contracts = data.get('contracts', [])
    
    if not acct_id:
        return jsonify({'error': '未指定账户ID'}), 400
        
    try:
        data_manager = DataManager(current_user.current_server)
        account_info = next(
            (acc for acc in current_user.account_info_list if acc.acct_id == acct_id),
            None
        )
        
        if not account_info:
            return jsonify({'error': '无效的账户ID'}), 400
        
        current_positions = data_manager.get_account_positions(account_info)
        new_contracts = [c for c in data_manager.get_futures_contracts() 
                        if c.symbol in selected_contracts]
        
        updated_positions = data_manager.merge_positions(current_positions, new_contracts)
        return jsonify([p.__dict__ for p in updated_positions])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main_bp.route('/api/product_config')
@login_required
def get_product_config():
    if not current_user.current_server:
        server_id = request.headers.get('X-Server-ID')
        if not server_id:
            return jsonify({'error': '未选择服务器'}), 400
        current_user.current_server = server_id
    
    acct_id = request.args.get('acct_id')
    if not acct_id:
        return jsonify({'error': '未指定账户ID'}), 400
        
    try:
        data_manager = DataManager(current_user.current_server)
        config = data_manager.get_product_config(acct_id)
        return jsonify(config)
    except Exception as e:
        logger.exception("Error getting product config")
        return jsonify({'error': str(e)}), 500

@main_bp.route('/api/save_config', methods=['POST'])
@login_required
def save_product_config():
    # 检查并设置服务器ID
    if not current_user.current_server:
        server_id = request.headers.get('X-Server-ID')
        if not server_id:
            return jsonify({'error': '未选择服务器'}), 400
        current_user.current_server = server_id
    
    data = request.json
    acct_id = data.get('acct_id')
    if not acct_id:
        return jsonify({'error': '未指定账户ID'}), 400
        
    try:
        data_manager = DataManager(current_user.current_server)
        data_manager.save_product_config(
            acct_id=acct_id,
            money=data.get('money', 0),
            discount=data.get('discount', 0),
            symbols=data.get('symbols', []),
            product_list=data.get('product_list')
        )
        return jsonify({'success': True})
    except Exception as e:
        logger.exception("Error saving product config")
        return jsonify({'error': str(e)}), 500

@main_bp.route('/api/strategies')
@login_required
def get_strategies():
    if not current_user.current_server:
        server_id = request.headers.get('X-Server-ID')
        if not server_id:
            return jsonify({'error': '未选择服务器'}), 400
        current_user.current_server = server_id
    
    try:
        data_manager = DataManager(current_user.current_server)
        strategies = data_manager.get_strategies()
        return jsonify(strategies)
    except Exception as e:
        logger.exception("Error getting strategies")
        return jsonify({'error': str(e)}), 500

@main_bp.route('/api/strategy/<product_comb>')
@login_required
def get_strategy(product_comb):
    if not current_user.current_server:
        server_id = request.headers.get('X-Server-ID')
        if not server_id:
            return jsonify({'error': '未选择服务器'}), 400
        current_user.current_server = server_id
    
    try:
        data_manager = DataManager(current_user.current_server)
        strategy = data_manager.get_strategy(product_comb)
        return jsonify(strategy)
    except Exception as e:
        logger.exception("Error getting strategy")
        return jsonify({'error': str(e)}), 500

@main_bp.route('/api/create_strategy', methods=['POST'])
@login_required
def create_strategy():
    if not current_user.current_server:
        server_id = request.headers.get('X-Server-ID')
        if not server_id:
            return jsonify({'error': '未选择服务器'}), 400
        current_user.current_server = server_id
    
    data = request.json
    try:
        data_manager = DataManager(current_user.current_server)
        data_manager.create_strategy(
            product_comb=data['product_comb'],
            comb_name=data['comb_name'],
            symbols=data['symbols']
        )
        return jsonify({'success': True})
    except Exception as e:
        logger.exception("Error creating strategy")
        return jsonify({'error': str(e)}), 500

@main_bp.route('/api/available_contracts')
@login_required
def get_available_contracts():
    # 检查并设置服务器ID
    if not current_user.current_server:
        server_id = request.headers.get('X-Server-ID')
        if not server_id:
            return jsonify({'error': '未选择服务器'}), 400
        current_user.current_server = server_id
    
    try:
        data_manager = DataManager(current_user.current_server)
        contracts = data_manager.get_futures_contracts()
        return jsonify(contracts)
    except Exception as e:
        logger.exception("Error getting contracts")
        return jsonify({'error': str(e)}), 500

@main_bp.route('/breakthrough-trading')
@login_required
def breakthrough_trading():
    """突破交易页面"""
    current_app.logger.info("====== 进入突破交易页面 ======")
    account_id = request.args.get('accountId')
    server_info = request.args.get('serverInfo')
    current_app.logger.info(f"账户ID: {account_id}, 服务器信息: {server_info}")
    return render_template('breakthrough.html', account_id=account_id, server_info=server_info)

@main_bp.route('/api/symbol_data')
@login_required
def get_symbol_data():
    account_id = request.args.get('accountId')
    if not account_id:
        return jsonify({'error': '未指定账户ID'}), 400
        
    try:
        data_manager = DataManager(current_user.current_server)
        symbol_data = data_manager.get_symbol_data(account_id)
        return jsonify(symbol_data)
    except Exception as e:
        logger.exception("Error getting symbol data")
        return jsonify({'error': str(e)}), 500

def get_data_manager():
    """获取数据管理器实例"""
    server_id = request.headers.get('X-Server-ID')
    if not server_id:
        raise ValueError('未指定服务器ID')
    return DataManager(server_id)

@main_bp.route('/api/monitor_symbols/<account_id>')
def get_monitor_symbols(account_id):
    """获取监控列表数据"""
    try:
        # 获取服务器ID
        server_id = request.headers.get('X-Server-ID')
        if not server_id:
            return jsonify({
                'status': 'error',
                'message': '未指定服务器ID'
            }), 400

        # 创建数据管理器
        data_manager = DataManager(server_id)
        
        # 获取监控列表数据
        sql = """
            SELECT 
                m.id,
                m.symbol,
                m.allocated_money,
                m.leverage,
                m.take_profit,
                m.sync_status as status,
                m.is_active,
                m.last_sync_time as sync_time,
                m.position_side,  # 直接使用原始的 position_side
                p.last_price,
                p.amplitude,
                p.position_ratio,
                p.update_time
            FROM monitor_list m
            LEFT JOIN price_range_20d p ON m.symbol = p.symbol
            WHERE m.account_id = %s AND m.strategy_type = 'break'
            ORDER BY m.id DESC
        """
        
        with data_manager.db_connection.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, (account_id,))
                data = cursor.fetchall()
                logger.info(f"查询到 {len(data)} 条记录")
                if data:
                    logger.debug(f"数据示例: {data[0]}")
                return jsonify({
                    'status': 'success',
                    'data': data
                })
                
    except Exception as e:
        logger.error(f"获取监控列表失败: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@main_bp.route('/api/check_monitor_symbol/<account_id>/<symbol>', methods=['GET'])
@login_required
def check_monitor_symbol(account_id, symbol):
    """检查品种是否存在于监控列表"""
    try:
        exists = MonitorList.query.filter_by(
            account_id=account_id,
            symbol=symbol,
            is_active=True
        ).first() is not None
        
        return jsonify({
            'status': 'success',
            'exists': exists
        })
    except Exception as e:
        current_app.logger.error(f"检查监控品种失败: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@main_bp.route('/monitor_list')
@login_required
def monitor_list():
    """监控列表页面"""
    try:
        # 获取所有监控记录
        monitors = MonitorList.query.all()
        logger.info(f"获取到 {len(monitors)} 条监控记录")
        
        if not monitors:
            logger.warning("没有找到任何监控记录")
            return render_template('monitor_list.html', monitors=[])
        
        # 获取最新的价格数据
        latest_date = db.session.query(db.func.max(PriceRange20d.update_date)).scalar()
        logger.info(f"最新价格数据日期: {latest_date}")
        
        if not latest_date:
            logger.warning("没有找到任何价格数据")
            return render_template('monitor_list.html', monitors=[])
        
        # 获取价格数据
        price_records = PriceRange20d.query.filter_by(update_date=latest_date).all()
        logger.info(f"获取到 {len(price_records)} 条价格数据")
        
        # 创建价格数据字典
        prices = {record.symbol: record for record in price_records}
        logger.info(f"价格数据包含的品种: {list(prices.keys())}")
        
        # 织数据
        monitor_data = []
        for monitor in monitors:
            logger.info(f"处理监控记录: {monitor.symbol}")
            price_info = prices.get(monitor.symbol)
            if price_info:
                logger.info(f"找到价格数据: {monitor.symbol}")
            else:
                logger.warning(f"未找到价格数据: {monitor.symbol}")
                
            data = {
                'id': monitor.id,
                'account_id': monitor.account_id,
                'symbol': monitor.symbol,
                'allocated_money': float(monitor.allocated_money),
                'leverage': monitor.leverage,
                'take_profit': float(monitor.take_profit),
                'sync_status': monitor.sync_status.value,
                'is_active': monitor.is_active,
                'last_sync_time': monitor.last_sync_time,
                'current_price': float(price_info.last_price) if price_info else None,
                'amplitude': float(price_info.amplitude) if price_info else None,
                'position_ratio': float(price_info.position_ratio) if price_info else None,
                'update_time': price_info.update_time if price_info else None
            }
            monitor_data.append(data)
            logger.info(f"添加数据: {data}")
        
        logger.info(f"成功组织监控列表数据，共 {len(monitor_data)} 条记录")
        return render_template('monitor_list.html', monitors=monitor_data)
        
    except Exception as e:
        logger.error(f"获取监控列表失败: {str(e)}")
        logger.exception("详细错误信息：")
        return render_template('error.html', message="获取监控列表失败")

@main_bp.route('/api/monitor/<int:id>/toggle_active', methods=['POST'])
@login_required
def toggle_monitor_active(id):
    """切换监控记录的激活状态"""
    try:
        monitor = MonitorList.query.get_or_404(id)
        monitor.is_active = not monitor.is_active
        db.session.commit()
        logger.info(f"成功切换监控记录 {monitor.symbol} 的激活状态为: {monitor.is_active}")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"切换监控记录激活状态失败: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@main_bp.route('/oscillation-trading')
@login_required
def oscillation_trading():
    """震荡交易页面"""
    account_id = request.args.get('accountId')
    server_info = request.args.get('serverInfo')
    return render_template('oscillation.html', account_id=account_id, server_info=server_info)

@main_bp.route('/api/save_oscillation_monitor', methods=['POST'])
@login_required
def save_oscillation_monitor():
    """保存震荡交易监控品种"""
    try:
        data = request.json
        if not data:
            return jsonify({
                'status': 'error',
                'message': '无效的请求数据'
            }), 400

        account_id = data.get('accountId')
        symbols_data = data.get('symbols', [])
        
        if not account_id:
            return jsonify({
                'status': 'error',
                'message': '未指定账户ID'
            }), 400
            
        try:
            for symbol_data in symbols_data:
                # 检查是否已存在
                existing = MonitorList.query.filter_by(
                    account_id=account_id,
                    symbol=symbol_data['symbol'],
                    strategy_type='oscillation'
                ).first()
                
                if existing:
                    # 如果记录已存在，返回友好的错误信息
                    return jsonify({
                        'status': 'error',
                        'message': f'合约 {symbol_data["symbol"]} 已在监控列表中，请先删除原记录后再添加'
                    }), 400
                else:
                    # 创建新记录
                    monitor = MonitorList(
                        account_id=account_id,
                        symbol=symbol_data['symbol'],
                        allocated_money=symbol_data['allocated_money'],
                        leverage=symbol_data['leverage'],
                        take_profit=symbol_data['take_profit'],
                        strategy_type='oscillation',
                        sync_status='waiting',
                        is_active=True
                    )
                    db.session.add(monitor)
            
            db.session.commit()
            return jsonify({
                'status': 'success',
                'message': '保存成功'
            })
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"保存震荡交易监控品种失败: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': '保存失败，请稍后重试'
            }), 500
            
    except Exception as e:
        logger.error(f"保存震荡交易监控品种失败: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': '保存失败，请稍后重试'
        }), 500

@main_bp.route('/api/oscillation/<int:id>', methods=['GET'])
@login_required
def get_oscillation_monitor(id):
    """获取震荡监控记录详情"""
    try:
        monitor = MonitorList.query.filter_by(
            id=id,
            strategy_type='oscillation'
        ).first_or_404()
        
        return jsonify({
            'status': 'success',
            'monitor': monitor.to_dict()
        })
    except Exception as e:
        logger.error(f"获取震荡监控记录失败: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@main_bp.route('/api/oscillation/<int:id>', methods=['PUT'])
@login_required
def update_oscillation_monitor(id):
    """更新震荡监控记录"""
    try:
        monitor = MonitorList.query.filter_by(
            id=id,
            strategy_type='oscillation'
        ).first_or_404()
        
        data = request.json
        
        monitor.allocated_money = data['allocated_money']
        monitor.leverage = data['leverage']
        monitor.take_profit = data['take_profit']
        monitor.updated_at = datetime.now()
        
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': '更新成功'
        })
    except Exception as e:
        logger.error(f"更新震荡监控记录失败: {str(e)}")
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@auth_bp.route('/register', methods=['POST'])
def register():
    """注册新用户"""
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'error': '用户名和密码不能为空'}), 400
            
        # 检查用户名是否已存在
        if User.query.filter_by(username=username).first():
            return jsonify({'error': '用户名已存在'}), 400
            
        # 创建新用户
        user = User(username=username, email=f"{username}@example.com")  # 临时使用用户名作为邮箱
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': '注册成功'
        })
        
    except Exception as e:
        logger.error(f"用户注册失败: {str(e)}")
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@main_bp.route('/api/kline/<symbol>')
@login_required
def get_kline_data(symbol):
    """获取K线数据"""
    try:
        server_id = request.headers.get('X-Server-ID')
        if not server_id:
            return jsonify({'status': 'error', 'message': '缺少服务器信息'}), 400
            
        # 获取账户信息
        account_id = request.args.get('accountId')
        if not account_id:
            return jsonify({'status': 'error', 'message': '缺少账户信息'}), 400
            
        # 创建数据管理器并初始化API凭证
        data_manager = DataManager(server_id)
        account_info = data_manager.get_account_info(account_id)
        if not account_info:
            return jsonify({'status': 'error', 'message': '获取账户信息失败'}), 400
            
        # 设置账户信息
        data_manager.account_info = account_info
        
        # 获取K线数据
        candlesticks = data_manager.get_kline_data(symbol, '1d', 21)
        if not candlesticks:
            return jsonify({'status': 'error', 'message': '获取K线数据失败'}), 400
            
        # 处理数据
        dates = []
        k_data = []
        volumes = []
        closes = []
        
        for k in candlesticks:
            # 使用对象属性而不是下标访问
            timestamp = datetime.fromtimestamp(k.t).strftime('%Y-%m-%d')
            dates.append(timestamp)
            k_data.append([
                float(k.o),  # 开盘价
                float(k.c),  # 收盘价
                float(k.h),  # 最高价
                float(k.l)   # 最低价
            ])
            volumes.append(float(k.v))  # 成交量
            closes.append(float(k.c))   # 收盘价
            
        # 计算均线
        ma5 = calculate_ma(closes, 5)
        ma10 = calculate_ma(closes, 10)
        ma20 = calculate_ma(closes, 20)
        
        return jsonify({
            'status': 'success',
            'data': {
                'dates': dates,
                'klineData': k_data,
                'volumes': volumes,
                'ma5': ma5,
                'ma10': ma10,
                'ma20': ma20
            }
        })
        
    except Exception as e:
        logger.error(f"获取K线数据失败: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

def calculate_ma(data, period):
    """计算移动平均线"""
    result = []
    for i in range(len(data)):
        if i < period - 1:
            result.append(None)
        else:
            val = sum(data[i - period + 1:i + 1]) / period
            result.append(val)
    return result

@main_bp.route('/api/monitor/<int:id>', methods=['GET'])
@login_required
def get_monitor(id):
    """获取监控记录详情"""
    try:
        monitor = MonitorList.query.get_or_404(id)
        return jsonify({
            'status': 'success',
            'monitor': monitor.to_dict()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@main_bp.route('/api/monitor/<int:id>', methods=['PUT'])
@login_required
def update_monitor(id):
    """更新监控记录"""
    try:
        monitor = MonitorList.query.get_or_404(id)
        data = request.json
        
        monitor.allocated_money = data['allocated_money']
        monitor.leverage = data['leverage']
        monitor.take_profit = data['take_profit']
        monitor.updated_at = datetime.now()
        
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': '更新成功'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@main_bp.route('/api/oscillation_monitor/<int:id>/toggle_active', methods=['POST'])
@login_required
def toggle_oscillation_monitor_active(id):
    """切换震荡交易监控记录的激活状态"""
    try:
        monitor = OscillationMonitor.query.get_or_404(id)
        monitor.is_active = not monitor.is_active
        db.session.commit()
        logger.info(f"成功切换震荡交易监控记录 {monitor.symbol} 的激活状态为: {monitor.is_active}")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"切换震荡交易监控记录激活状态失败: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@main_bp.route('/api/price_ranges')
@login_required
def get_price_ranges():
    """获取价格范围数据"""
    try:
        # 获取���求参数
        account_id = request.args.get('account_id')
        strategy_type = request.args.get('strategy_type')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 30))
        
        # 获取筛选条件
        filters = {
            'min_amplitude': float(request.args.get('min_amplitude')) if request.args.get('min_amplitude') else None,
            'max_amplitude': float(request.args.get('max_amplitude')) if request.args.get('max_amplitude') else None,
            'min_position': float(request.args.get('min_position')) if request.args.get('min_position') else None,
            'max_position': float(request.args.get('max_position')) if request.args.get('max_position') else None,
            'min_volume': float(request.args.get('min_volume')) if request.args.get('min_volume') else None,
            'max_volume': float(request.args.get('max_volume')) if request.args.get('max_volume') else None,
            'symbol': request.args.get('symbol'),
            'page': page,
            'per_page': per_page,
            'exclude_status': ['CLOSED']  # 添加状态过滤，排除已关闭的记录
        }

        # 获取服务器ID
        server_id = request.headers.get('X-Server-ID')
        if not server_id:
            return jsonify({
                'status': 'error',
                'message': '未指定服务器ID'
            }), 400

        # 创建数据管理器
        data_manager = DataManager(server_id)
        
        # 获取价格范围数据
        result = data_manager.get_price_ranges(account_id, strategy_type, filters)
        
        logger.debug(f"获取价格范围数据成功: {len(result.get('data', []))} 条记录")
        
        return jsonify({
            'status': 'success',
            'data': result.get('data', []),
            'total': result.get('total', 0)
        })
        
    except ValueError as e:
        logger.error(f"参数错误: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'参数错误: {str(e)}'
        }), 400
        
    except Exception as e:
        logger.error(f"获取价格范围数据失败: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'服务器错误: {str(e)}'
        }), 500

@main_bp.route('/api/save_monitor_symbols', methods=['POST'])
@login_required
def save_monitor_symbols():
    """保存监控品种"""
    try:
        data = request.json
        if not data:
            return jsonify({
                'status': 'error',
                'message': '无效的请求数据'
            }), 400

        account_id = data.get('accountId')
        strategy_type = data.get('strategy_type', 'break')  # 默认为突破策略
        symbols_data = data.get('symbols', [])
        
        if not account_id:
            return jsonify({
                'status': 'error',
                'message': '未指定账户ID'
            }), 400
            
        try:
            for symbol_data in symbols_data:
                # 检查是否已存在
                existing = MonitorList.query.filter_by(
                    account_id=account_id,
                    symbol=symbol_data['symbol'],
                    strategy_type=strategy_type
                ).first()
                
                if existing:
                    # 更新现有记录
                    existing.allocated_money = symbol_data['allocated_money']
                    existing.leverage = symbol_data['leverage']
                    existing.take_profit = symbol_data['take_profit']
                    existing.sync_status = 'waiting'
                    existing.is_active = True
                else:
                    # 创建新记录
                    monitor = MonitorList(
                        account_id=account_id,
                        symbol=symbol_data['symbol'],
                        allocated_money=symbol_data['allocated_money'],
                        leverage=symbol_data['leverage'],
                        take_profit=symbol_data['take_profit'],
                        strategy_type=strategy_type,
                        sync_status='waiting',
                        is_active=True
                    )
                    db.session.add(monitor)
            
            db.session.commit()
            return jsonify({
                'status': 'success',
                'message': '保存成功'
            })
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"保存监控品种失败: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500
            
    except Exception as e:
        logger.error(f"保存监控品种失败: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@main_bp.route('/api/oscillation_monitor_symbols/<account_id>')
def get_oscillation_monitor_symbols(account_id):
    """获取震荡交易监控列表数据"""
    try:
        # 获取服务器ID
        server_id = request.headers.get('X-Server-ID')
        if not server_id:
            return jsonify({
                'status': 'error',
                'message': '未指定服务器ID'
            }), 400

        # 创建数据管理器
        data_manager = DataManager(server_id)
        
        # 获取监控列表数据
        sql = """
            SELECT 
                m.id,
                m.symbol,
                m.allocated_money,
                m.leverage,
                m.take_profit,
                m.sync_status as status,
                m.is_active,
                m.last_sync_time as sync_time,
                m.position_side,
                p.last_price,
                p.amplitude,
                p.position_ratio,
                p.update_time
            FROM monitor_list m
            LEFT JOIN price_range_20d p ON m.symbol = p.symbol
            WHERE m.account_id = %s AND m.strategy_type = 'oscillation'
            ORDER BY m.id DESC
        """
        
        with data_manager.db_connection.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, (account_id,))
                data = cursor.fetchall()
                logger.info(f"查询到 {len(data)} 条震荡交易记录")
                if data:
                    logger.debug(f"数据示例: {data[0]}")
                return jsonify({
                    'status': 'success',
                    'data': data
                })
                
    except Exception as e:
        logger.error(f"获取震荡交易监控列表失败: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@main_bp.route('/api/monitor/<int:id>/delete', methods=['POST'])
@login_required
def delete_monitor(id):
    """删除监控记录"""
    try:
        # 查找监控记录
        monitor = MonitorList.query.get_or_404(id)
        
        # 记录日志
        logger.info(f"正在删除监控记录: ID={id}, Symbol={monitor.symbol}")
        
        # 删除记录
        db.session.delete(monitor)
        db.session.commit()
        
        logger.info(f"成功删除监控记录: {monitor.symbol}")
        return jsonify({
            'status': 'success',
            'message': '删除成功'
        })
        
    except Exception as e:
        logger.error(f"删除监控记录失败: {str(e)}")
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': f'删除失败: {str(e)}'
        }), 500