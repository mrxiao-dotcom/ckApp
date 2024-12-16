import os
from datetime import timedelta
from urllib.parse import quote_plus
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key'
    
    # 数据库配置
    DATABASES = {
        'server1': {
            'HOST': os.environ.get('DB1_HOST', 'localhost'),
            'USER': os.environ.get('DB1_USER', 'root'),
            'PASSWORD': os.environ.get('DB1_PASSWORD', ''),
            'NAME': os.environ.get('DB1_NAME', 'autotrader'),
            'PORT': int(os.environ.get('DB1_PORT', 3306))
        },
        'server2': {
            'HOST': os.environ.get('DB2_HOST', 'localhost'),
            'USER': os.environ.get('DB2_USER', 'root'),
            'PASSWORD': os.environ.get('DB2_PASSWORD', ''),
            'NAME': os.environ.get('DB2_NAME', 'localdb'),
            'PORT': int(os.environ.get('DB2_PORT', 3306))
        }
    }
    
    # 默认数据库配置
    DB_CONFIG = DATABASES['server2']
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
        {"id": "1", "name": "服务器1", "url": f"http://{os.environ.get('DB1_HOST')}:{os.environ.get('DB1_PORT')}"},
        {"id": "2", "name": "服务器2", "url": f"http://{os.environ.get('DB2_HOST')}:{os.environ.get('DB2_PORT')}"}
    ] 
    
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    
    # 价格范围配置
    PRICE_RANGE_DAYS = 20  # 价格范围的天数
    PRICE_UPDATE_INTERVAL = 60  # 实时价格更新间隔（秒）