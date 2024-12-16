import click
from flask.cli import with_appcontext
from app import db
from app.models import User, PriceRange20d
from datetime import date

def init_app(app):
    app.cli.add_command(create_user)
    app.cli.add_command(change_password)
    app.cli.add_command(add_test_data)

@click.command('create-user')
@click.argument('username')
@click.argument('email')
@click.password_option()
@with_appcontext
def create_user(username, email, password):
    """创建新用户"""
    user = User(username=username, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    click.echo(f'已创建用户 {username}')

@click.command('change-password')
@click.argument('username')
@click.password_option()
@with_appcontext
def change_password(username, password):
    """修改用户密码"""
    user = User.query.filter_by(username=username).first()
    if user:
        user.set_password(password)
        db.session.commit()
        click.echo(f'已更新用户 {username} 的密码')
    else:
        click.echo(f'用户 {username} 不存在')

@click.command('add-test-data')
@with_appcontext
def add_test_data():
    """添加测试数据"""
    # 清除旧数据
    PriceRange20d.query.delete()
    
    # 添加测试数据
    test_data = [
        {
            'symbol': 'BTC/USDT',
            'high_price_20d': 45000.0,
            'low_price_20d': 40000.0,
            'last_price': 42500.0,
            'amplitude': 0.125,  # (45000-40000)/40000
            'position_ratio': 0.5,  # (42500-40000)/(45000-40000)
            'update_date': date.today()
        },
        {
            'symbol': 'ETH/USDT',
            'high_price_20d': 2500.0,
            'low_price_20d': 2000.0,
            'last_price': 2300.0,
            'amplitude': 0.25,
            'position_ratio': 0.6,
            'update_date': date.today()
        },
        # 可以添加更多测试数据
    ]
    
    for data in test_data:
        price_range = PriceRange20d(**data)
        db.session.add(price_range)
    
    db.session.commit()
    click.echo('Added test data successfully.') 