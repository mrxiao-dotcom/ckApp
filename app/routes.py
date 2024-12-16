from flask import Blueprint, render_template, request, jsonify, redirect, url_for, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User, PriceRange20d, MonitorList, SyncStatus
from app.auth import AuthService
from app.data_manager import DataManager
from app.database import DatabaseManager
import logging
from typing import Optional
from datetime import date

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
        username = request.form.get('username')
        password = request.form.get('password')
        server_id = request.form.get('server')
        
        user = AuthService.authenticate_user(username, password, server_id)
        if user:
            if not user.account_info_list:
                return jsonify({'error': '该用户没有可用的账户'}), 401
                
            login_user(user)
            user.update_last_login()
            token = AuthService.create_session(user)
            
            return jsonify({
                'token': token,
                'accounts': [
                    {
                        'acct_id': acc.acct_id,
                        'acct_name': acc.acct_name,
                        'email': acc.email,
                        'state': acc.state,
                        'status': acc.status
                    }
                    for acc in user.account_info_list
                ]
            })
            
        return jsonify({'error': '用户名或密码错误'}), 401
            
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

@main_bp.route('/api/save_monitor_symbols', methods=['POST'])
@login_required
def save_monitor_symbols():
    """保存账户的监控品种列表"""
    try:
        data = request.json
        account_id = data.get('accountId')
        symbols_data = data.get('symbols', [])
        
        if not account_id:
            return jsonify({'error': '未指定账户ID'}), 400
            
        try:
            # 先检查是否存在
            for symbol_data in symbols_data:
                existing = MonitorList.query.filter_by(
                    account_id=account_id,
                    symbol=symbol_data['symbol']
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
                    monitor_item = MonitorList(
                        account_id=account_id,
                        symbol=symbol_data['symbol'],
                        allocated_money=symbol_data['allocated_money'],
                        leverage=symbol_data['leverage'],
                        take_profit=symbol_data['take_profit'],
                        sync_status='waiting',
                        is_active=True
                    )
                    db.session.add(monitor_item)
            
            db.session.commit()
            return jsonify({
                'status': 'success',
                'message': '保存成功',
                'count': len(symbols_data)
            })
            
        except Exception as e:
            db.session.rollback()
            raise
            
    except Exception as e:
        logger.error(f"保存监控列表失败: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@main_bp.route('/get_price_ranges', methods=['GET'])
@login_required
def get_price_ranges():
    """获取价格范围数据"""
    try:
        # 获取筛选参数
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        min_amplitude = request.args.get('min_amplitude', type=float)
        max_amplitude = request.args.get('max_amplitude', type=float)
        min_position = request.args.get('min_position', type=float)
        max_position = request.args.get('max_position', type=float)
        min_volume = request.args.get('min_volume', type=float)
        max_volume = request.args.get('max_volume', type=float)
        search = request.args.get('search', '').strip()

        # 构建查询
        query = PriceRange20d.query

        # 获取最新日期的数据
        latest_date = db.session.query(db.func.max(PriceRange20d.update_date)).scalar()
        if latest_date:
            query = query.filter(PriceRange20d.update_date == latest_date)
        
        # 应用筛选条件
        if min_amplitude is not None:
            query = query.filter(PriceRange20d.amplitude >= min_amplitude)
        if max_amplitude is not None:
            query = query.filter(PriceRange20d.amplitude <= max_amplitude)
        if min_position is not None:
            query = query.filter(PriceRange20d.position_ratio >= min_position)
        if max_position is not None:
            query = query.filter(PriceRange20d.position_ratio <= max_position)
        if min_volume is not None:
            query = query.filter(PriceRange20d.volume_24h >= min_volume)
        if max_volume is not None:
            query = query.filter(PriceRange20d.volume_24h <= max_volume)
        if search:
            query = query.filter(PriceRange20d.symbol.ilike(f'%{search}%'))

        # 获取分页数据
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        price_ranges = pagination.items

        # 转换为JSON格式
        data = [{
            'symbol': pr.symbol,
            'high_price_20d': float(pr.high_price_20d),
            'low_price_20d': float(pr.low_price_20d),
            'last_price': float(pr.last_price),
            'amplitude': float(pr.amplitude),
            'position_ratio': float(pr.position_ratio),
            'volume_24h': float(pr.volume_24h),
            'update_time': pr.update_time.strftime('%Y-%m-%d %H:%M:%S') if pr.update_time else None
        } for pr in price_ranges]

        return jsonify({
            'status': 'success',
            'data': data,
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page
        })

    except Exception as e:
        logger.error(f"获取价格范围数据失败: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@main_bp.route('/api/monitor_symbols/<account_id>', methods=['GET'])
@login_required
def get_monitor_symbols(account_id):
    """获取账户的监控品种列表"""
    try:
        current_app.logger.info(f"获取账户 {account_id} 的监控列表")
        
        # 查询该账户的所有监控品种
        monitor_items = MonitorList.query.filter_by(
            account_id=account_id,
            is_active=True
        ).all()
        
        # 确保同步状态值正确
        for item in monitor_items:
            if isinstance(item.sync_status, str):
                item.sync_status = SyncStatus.from_string(item.sync_status)
        
        # 获取这些品种的最新价格范围数据
        latest_date = db.session.query(db.func.max(PriceRange20d.update_date)).scalar()
        
        if latest_date:
            symbols = [item.symbol for item in monitor_items]
            price_ranges = PriceRange20d.query.filter(
                PriceRange20d.update_date == latest_date,
                PriceRange20d.symbol.in_(symbols)
            ).all()
            
            # 转换为字典以便快速查找
            price_data = {pr.symbol: pr for pr in price_ranges}
            
            # 组合数据
            data = [{
                **item.to_dict(),  # 包含监控列表的所有字段
                'high_price_20d': float(price_data[item.symbol].high_price_20d) if item.symbol in price_data else None,
                'low_price_20d': float(price_data[item.symbol].low_price_20d) if item.symbol in price_data else None,
                'last_price': float(price_data[item.symbol].last_price) if item.symbol in price_data else None,
                'amplitude': float(price_data[item.symbol].amplitude) if item.symbol in price_data else None,
                'position_ratio': float(price_data[item.symbol].position_ratio) if item.symbol in price_data else None
            } for item in monitor_items]
        else:
            data = [item.to_dict() for item in monitor_items]

        current_app.logger.info(f"成功获取监控列表，共 {len(monitor_items)} 个品种")
        return jsonify({
            'status': 'success',
            'data': data
        })
        
    except Exception as e:
        current_app.logger.error(f"获取监控列表失败: {str(e)}")
        current_app.logger.exception("详细错误信息：")
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
        
        # 组织数据
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