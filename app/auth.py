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
        try:
            logger.info(f"验证用户: username={username}, server_id={server_id}")
            
            user = User.query.filter_by(username=username).first()
            if not user:
                logger.warning(f"用户不存在: {username}")
                return None
            
            if not user.check_password(password):
                logger.warning(f"密码错误: {username}")
                return None
            
            # 获取用户在指定服务器上的所有账户信息
            account_info_list = DatabaseManager.get_account_info(server_id, username)
            logger.info(f"获取到账户信息: {len(account_info_list) if account_info_list else 0} 个账户")
            
            # 即使没有账户信息也允许登录
            user.account_info_list = account_info_list or []
            user.current_server = server_id
            
            logger.info(f"用户验证成功: {username}")
            return user
            
        except Exception as e:
            logger.error(f"用户认证失败: {str(e)}")
            return None

    @staticmethod
    def create_session(user: User) -> str:
        """创建用户会话并返回 JWT token"""
        try:
            # 生成过期时间
            expires_at = datetime.utcnow() + timedelta(days=1)
            
            # 准备 JWT payload
            payload = {
                'user_id': user.id,
                'exp': expires_at,
                'iat': datetime.utcnow()
            }
            
            # 使用 PyJWT 生成 token
            token = jwt.encode(
                payload,
                current_app.config['JWT_SECRET_KEY'],
                algorithm='HS256'
            )
            
            # 创建会话记录
            session = UserSession(
                user_id=user.id,
                token=token,
                server_id=user.current_server or '',
                expires_at=expires_at
            )
            
            db.session.add(session)
            db.session.commit()
            
            return token
            
        except Exception as e:
            logger.error(f"创建会话失败: {str(e)}")
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
    def invalidate_session(token: str) -> bool:
        """使会话失效"""
        try:
            session = UserSession.query.filter_by(token=token).first()
            if session:
                session.is_active = False
                db.session.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"使会话失效失败: {str(e)}")
            db.session.rollback()
            return False 