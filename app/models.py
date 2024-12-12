from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager
from dataclasses import dataclass
from typing import List, ClassVar, Optional
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, ForeignKey, DateTime, Boolean, Integer

@dataclass
class ProductInfo:
    product_list: str
    name: str
    status: str
    comb_name: str
    money: float = 0.0      # 总资金
    discount: float = 0.0   # 仓位

@dataclass
class AccountInfo:
    acct_id: str
    acct_name: str
    apikey: str
    secretkey: str
    apipass: str
    email: str
    group_id: int
    state: int
    status: int
    stg_comb_product_gateio: List[ProductInfo]

@dataclass
class Position:
    symbol: str
    name: str
    is_selected: bool = False
    money: float = 0.0      # 总资金
    discount: float = 0.0   # 仓位

@dataclass
class FuturesContractInfo:
    symbol: str
    name: str

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    password_hash: Mapped[Optional[str]] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # 用户会话
    sessions: Mapped[List["UserSession"]] = db.relationship(backref='user', lazy='dynamic')
    
    # 非数据库字段 - 使用 ClassVar
    account_info_list: ClassVar[Optional[List[AccountInfo]]] = None
    current_server: ClassVar[Optional[str]] = None
    
    def __init__(self, username: str, email: str):
        self.username = username
        self.email = email
        self.account_info_list = []
        self.current_server = None

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def update_last_login(self) -> None:
        self.last_login = datetime.utcnow()
        db.session.commit()

    def refresh_account_info(self):
        """刷新用户的账户信息"""
        if self.current_server:
            self.account_info_list = DatabaseManager.get_account_info(
                self.current_server,
                self.username
            )

class UserSession(db.Model):
    __tablename__ = 'user_sessions'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'), nullable=False)
    token: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    server_id: Mapped[str] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

@login_manager.user_loader
def load_user(user_id: str) -> Optional[User]:
    return User.query.get(int(user_id)) 