import click
from flask.cli import with_appcontext
from app import db
from app.models import User

def init_app(app):
    app.cli.add_command(create_user)
    app.cli.add_command(change_password)

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