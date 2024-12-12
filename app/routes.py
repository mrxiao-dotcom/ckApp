from flask import Blueprint, render_template, request, jsonify, redirect, url_for, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User
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