from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager
from dataclasses import dataclass
from typing import List, ClassVar, Optional
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, ForeignKey, DateTime, Boolean, Integer
from enum import Enum

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
        self.is_active = True

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

class PriceRange20d(db.Model):
    """20日价格范围数据"""
    __tablename__ = 'price_range_20d'
    
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(20), nullable=False)
    high_price_20d = db.Column(db.DECIMAL(20, 8), nullable=False)
    low_price_20d = db.Column(db.DECIMAL(20, 8), nullable=False)
    last_price = db.Column(db.DECIMAL(20, 8), nullable=False)
    amplitude = db.Column(db.DECIMAL(20, 8), nullable=False)
    position_ratio = db.Column(db.DECIMAL(20, 8), nullable=False)
    volume_24h = db.Column(db.DECIMAL(20, 8), default=0)  # 添加新字段
    update_date = db.Column(db.Date, nullable=False)
    update_time = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f'<PriceRange20d {self.symbol}>'

class SyncStatus(str, Enum):
    """同步状态枚举"""
    WAITING = 'WAITING'      # 等待开仓
    OPENED = 'OPENED'        # 已开仓
    CLOSED = 'CLOSED'        # 已关闭

    @classmethod
    def from_string(cls, value: str) -> 'SyncStatus':
        """从字符串创建枚举值"""
        try:
            return cls(value.upper())
        except ValueError:
            return cls.WAITING  # 默认值

class MonitorList(db.Model):
    """账户监控列表"""
    __tablename__ = 'monitor_list'
    
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.String(50), nullable=False, index=True)  # 账户ID
    symbol = db.Column(db.String(20), nullable=False)  # 品种代码
    strategy_type = db.Column(db.String(20), nullable=False, default='break')  # 策略类型:break/oscillation
    
    # 交易配置
    allocated_money = db.Column(db.Numeric(20, 8), nullable=False)  # 分配资金
    leverage = db.Column(db.Integer, nullable=False)  # 杠杆倍数
    take_profit = db.Column(db.Numeric(20, 8), nullable=False)  # 止盈额
    
    # 状态控制
    position_side = db.Column(db.String(10))  # 当前持仓方向：long/short/none
    sync_status = db.Column(db.String(20), nullable=False, default='waiting')  # 同步状态
    is_active = db.Column(db.Boolean, default=True)  # 是否激活
    
    # 时间记录
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # 创建时间
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  # 更新时间
    last_sync_time = db.Column(db.DateTime)  # 最后同步时间
    
    __table_args__ = (
        db.UniqueConstraint('account_id', 'symbol', 'strategy_type', name='uix_account_symbol_strategy'),
    )
    
    def __repr__(self):
        return f'<MonitorList {self.account_id}:{self.symbol}:{self.strategy_type}>'

    def to_dict(self):
        """转换为字典格式"""
        return {
            'id': self.id,
            'account_id': self.account_id,
            'symbol': self.symbol,
            'strategy_type': self.strategy_type,
            'allocated_money': float(self.allocated_money),
            'leverage': self.leverage,
            'take_profit': float(self.take_profit),
            'position_side': self.position_side,
            'sync_status': self.sync_status,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_sync_time': self.last_sync_time.isoformat() if self.last_sync_time else None
        }

    def update_status(self, sync_status: SyncStatus):
        """更新同步状态"""
        self.sync_status = sync_status
        self.last_sync_time = datetime.utcnow()

class OscillationMonitor(db.Model):
    """震荡交易监控列表"""
    __tablename__ = 'oscillation_monitor'
    
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.String(50), nullable=False, index=True)  # 账户ID
    symbol = db.Column(db.String(20), nullable=False)  # 品种代码
    
    # 交易配置
    allocated_money = db.Column(db.Numeric(20, 8), nullable=False)  # 分配资金
    leverage = db.Column(db.Integer, nullable=False)  # 杠杆倍数
    take_profit = db.Column(db.Numeric(20, 8), nullable=False)  # 止盈额
    
    # 状态控制
    position_side = db.Column(db.String(10))  # 当前持仓方向：long/short/none
    sync_status = db.Column(db.String(20), nullable=False, default='waiting')  # 同步状态
    is_active = db.Column(db.Boolean, default=True)  # 是否激活
    
    # 时间记录
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # 创建时间
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  # 更新时间
    last_sync_time = db.Column(db.DateTime)  # 最后同步时间
    
    __table_args__ = (
        db.UniqueConstraint('account_id', 'symbol', name='uix_oscillation_account_symbol'),
    )
    
    def __repr__(self):
        return f'<OscillationMonitor {self.account_id}:{self.symbol}>'

    def to_dict(self):
        """转换为字典格式"""
        return {
            'id': self.id,
            'account_id': self.account_id,
            'symbol': self.symbol,
            'allocated_money': float(self.allocated_money),
            'leverage': self.leverage,
            'take_profit': float(self.take_profit),
            'position_side': self.position_side,
            'sync_status': self.sync_status,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_sync_time': self.last_sync_time.isoformat() if self.last_sync_time else None
        }