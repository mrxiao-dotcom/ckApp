import os
from datetime import timedelta
from urllib.parse import quote_plus

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here'
    
    # 数据库配置
    DATABASES = {
        'server1': {
            'HOST': '45.153.131.230',
            'USER': 'root',
            'PASSWORD': 'Xj774913@',
            'NAME': 'autotrader',
            'PORT': 3306
        },
        'server2': {
            'HOST': '45.153.131.217',
            'USER': 'root',
            'PASSWORD': 'Xj774913@',
            'NAME': 'localdb',
            'PORT': 3306
        }
    }
    
    # 默认数据库配置（用于用户认证等）
    DB_CONFIG = DATABASES['server1']
    # 对特殊字符进行URL编码
    ENCODED_PASSWORD = quote_plus(DB_CONFIG['PASSWORD'])
    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{DB_CONFIG['USER']}:{ENCODED_PASSWORD}"
        f"@{DB_CONFIG['HOST']}:{DB_CONFIG['PORT']}/{DB_CONFIG['NAME']}"
    )
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_timeout': 30,
        'max_overflow': 2,
        'connect_args': {
            'connect_timeout': 10
        }
    }
    
    # JWT配置
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-key'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=1)
    
    # 服务器配置
    SERVERS = [
        {"id": "1", "name": "服务器1", "url": "http://45.153.131.230:3306"},
        {"id": "2", "name": "服务器2", "url": "http://45.153.131.217:3306"}
    ] 