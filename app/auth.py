from datetime import datetime, timedelta
import jwt
from flask import current_app
from app import db
from app.models import User, UserSession
from app.database import DatabaseManager
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class AuthService:
    @staticmethod
    def authenticate_user(username: str, password: str, server_id: str) -> Optional[User]:
        """验证用户并返回用户对象"""
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            # 获取用户在指定服务器上的所有账户信息
            account_info_list = DatabaseManager.get_account_info(server_id, username)
            if account_info_list:
                user.account_info_list = account_info_list
                user.current_server = server_id
                return user
        return None

    @staticmethod
    def create_session(user: User) -> str:
        try:
            # 创建JWT token
            expiration = datetime.utcnow() + timedelta(days=1)
            token = jwt.encode(
                {
                    'user_id': user.id,
                    'server_id': user.current_server,
                    'exp': expiration
                },
                current_app.config['SECRET_KEY'],
                algorithm='HS256'
            )

            # 删除旧的会话
            UserSession.query.filter_by(user_id=user.id, is_active=True).update({'is_active': False})

            # 创建新会话
            session = UserSession(
                user_id=user.id,
                token=token,
                server_id=user.current_server,
                expires_at=expiration,
                is_active=True
            )
            db.session.add(session)
            db.session.commit()

            return token
        except Exception as e:
            db.session.rollback()
            # 如果出错，尝试创建一个不包含server_id的会话
            try:
                session = UserSession(
                    user_id=user.id,
                    token=token,
                    expires_at=expiration,
                    is_active=True
                )
                db.session.add(session)
                db.session.commit()
                return token
            except Exception as e:
                db.session.rollback()
                raise

    @staticmethod
    def validate_token(token: str) -> Optional[User]:
        try:
            session = UserSession.query.filter_by(token=token, is_active=True).first()
            if not session or session.expires_at < datetime.utcnow():
                return None

            payload = jwt.decode(
                token,
                current_app.config['SECRET_KEY'],
                algorithms=['HS256']
            )
            user = User.query.get(payload['user_id'])
            if user:
                # 设置当前服务器
                user.current_server = session.server_id or payload.get('server_id')
                # 获取用户账户信息
                if user.current_server:
                    user.account_info_list = DatabaseManager.get_account_info(
                        user.current_server, 
                        user.username
                    )
            return user
        except Exception as e:
            logger.error(f"Error validating token: {str(e)}", exc_info=True)
            return None

    @staticmethod
    def invalidate_session(token: str) -> None:
        try:
            session = UserSession.query.filter_by(token=token).first()
            if session:
                session.is_active = False
                db.session.commit()
        except Exception as e:
            db.session.rollback() 