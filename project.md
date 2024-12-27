# 交易监控系统项目说明文档

## 1. 系统概述

本系统是一个交易监控管理平台，主要用于管理和监控加密货币的交易策略。系统支持两种主要的交易策略：突破交易和震荡交易。

### 1.1 核心功能
- 用户认证和授权
  - 基于 Flask-Login 的用户认证
  - 服务器选择和切换
  - 会话管理和权限控制
- 交易策略管理
  - 突破交易策略
  - 震荡交易策略
  - 参数配置和实时监控
- 实时监控和数据展示
  - K线图展示
  - 价格和成交量数据
  - 监控状态实时更新
- 交易品种筛选
  - 多维度筛选条件
  - 分页展示
  - 实时搜索
- 参数配置和管理
  - 资金配置
  - 杠杆设置
  - 止盈目标管理

### 1.2 技术栈
- 后端：
  - Python 3.7+
  - Flask Web框架
  - SQLAlchemy ORM
  - MySQL数据库
- 前端：
  - HTML5 + CSS3
  - 原生JavaScript (ES6+)
  - ECharts图表库
  - Font Awesome图标
- 开发工具：
  - Git版本控制
  - PyCharm IDE
  - MySQL Workbench

## 2. 项目结构

```
├── app/                            # 应用主目录
│   ├── __init__.py                # 应用初始化、Flask配置
│   ├── routes.py                  # 路由控制器
│   ├── models.py                  # 数据模型定义
│   ├── auth.py                    # 认证相关功能
│   ├── data_manager.py            # 数据管理类
│   ├── database.py                # 数据库配置
│   ├── static/                    # 静态资源目录
│   │   ├── css/                   # 样式文件
│   │   │   ├── style.css         # 全局样式
│   │   │   ├── breakthrough.css   # 突破交易样式
│   │   │   └── oscillation.css    # 震荡交易样式
│   │   ├── js/                    # JavaScript文件
│   │   │   ├── main.js           # 主要脚本
│   │   │   ├── breakthrough.js    # 突破交易脚本
│   │   │   ├── oscillation.js     # 震荡交易脚本
│   │   │   └── kline.js          # K线图相关脚本
│   │   └── img/                   # 图片资源
│   └── templates/                 # 页面模板
│       ├── login.html             # 登录页面
│       ├── main.html              # 主页面
│       ├── breakthrough.html      # 突破交易页面
│       └── oscillation.html       # 震荡交易页面
├── config.py                      # 配置文件
├── requirements.txt               # 依赖管理
└── project.md                     # 项目说明文档
```

## 3. 核心模块详解

### 3.1 认证模块 (auth.py)
```python
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True)
    password_hash = db.Column(db.String(128))
    current_server = db.Column(db.String(50))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
```

功能说明：
- 用户认证和会话管理
- 密码加密存储
- 服务器选择和切换
- 登录状态维护

### 3.2 数据管理模块 (data_manager.py)
```python
class DataManager:
    def __init__(self, server_id):
        self.server_id = server_id
        self.db_connection = DatabaseConnection(server_id)
    
    def get_price_ranges(self, account_id, strategy_type, filters):
        """获取价格范围数据"""
        # 构建查询条件
        conditions = []
        params = []
        
        if filters.get('min_amplitude'):
            conditions.append('amplitude >= %s')
            params.append(filters['min_amplitude'])
        
        if filters.get('max_amplitude'):
            conditions.append('amplitude <= %s')
            params.append(filters['max_amplitude'])
            
        # ... 其他筛选条件处理 ...
    
    def get_kline_data(self, symbol):
        """获取K线数据"""
        sql = """
            SELECT 
                timestamp,
                open_price,
                high_price,
                low_price,
                close_price,
                volume
            FROM kline_data
            WHERE symbol = %s
            ORDER BY timestamp DESC
            LIMIT 500
        """
        # ... 数据查询和处理 ...
```

功能说明：
- 数据库连接管理
- 价格数据查询和过滤
- K线数据获取
- 监控数据管理
- SQL查询优化

### 3.3 数据模型 (models.py)
```python
class MonitorList(db.Model):
    """监控列表模型"""
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.String(50))
    symbol = db.Column(db.String(20))
    allocated_money = db.Column(db.Numeric(20, 8))
    leverage = db.Column(db.Integer)
    take_profit = db.Column(db.Numeric(20, 8))
    strategy_type = db.Column(db.String(20))
    sync_status = db.Column(db.Enum('waiting', 'opened', 'closed'))
    is_active = db.Column(db.Boolean, default=True)
    position_side = db.Column(db.String(10))
    last_sync_time = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

class PriceRange20d(db.Model):
    """20日价格范围模型"""
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(20))
    high_price_20d = db.Column(db.Numeric(20, 8))
    low_price_20d = db.Column(db.Numeric(20, 8))
    last_price = db.Column(db.Numeric(20, 8))
    amplitude = db.Column(db.Numeric(10, 4))
    position_ratio = db.Column(db.Numeric(10, 4))
    volume_24h = db.Column(db.Numeric(30, 8))
    update_time = db.Column(db.DateTime)
    update_date = db.Column(db.Date)
```

功能说明：
- 监控列表数据结构
- 价格范围数据结构
- 数据关系映射
- 字段类型定义
- 默认值和更新规则

### 3.4 数据库配置 (database.py)
```python
class DatabaseConnection:
    def __init__(self, server_id):
        self.server_id = server_id
        self.config = self._get_db_config()
        self.pool = self._create_connection_pool()
    
    def _get_db_config(self):
        """获取数据库配置"""
        # 根据server_id获取对应的数据库配置
        
    def _create_connection_pool(self):
        """创建数据库连接池"""
        # 配置和创建连接池
        
    def get_connection(self):
        """获取数据库连接"""
        # 从连接池获取连接
```

功能说明：
- 数据库连接池管理
- 多服务器配置支持
- 连接复用和释放
- 错误处理和重试机制 

## 4. 前端功能详解

### 4.1 突破交易页面 (breakthrough.html, breakthrough.js)
```javascript
// 监控列表功能
function loadMonitorList() {
    fetch(`/api/monitor_symbols/${accountId}`, {
        headers: {
            'X-Server-ID': serverInfo.serverId
        }
    })
    .then(response => response.json())
    .then(result => {
        if (result.status === 'success') {
            updateMonitorTable(result.data);
        }
    });
}

// K线图展示
function showKlineChart(symbol) {
    const klineChart = echarts.init(document.getElementById('klineChart'));
    const volumeChart = echarts.init(document.getElementById('volumeChart'));
    // 配置和渲染图表...
}
```

功能说明：
- 监控列表管理
  - 显示所有监控品种
  - 实时状态更新
  - 参数编辑功能
  - 删除监控记录
- K线图展示
  - 价格走势图
  - 成交量图表
  - 技术指标叠加
- 筛选功能
  - 振幅范围筛选
  - 位置比筛选
  - ���交额筛选
  - 品种搜索

### 4.2 震荡交易页面 (oscillation.html, oscillation.js)
```javascript
// 品种筛选功能
function getFilterValues() {
    const filters = {};
    // 获取并处理各个筛选条件
    if (inputs.minAmplitude?.value) {
        filters.min_amplitude = parseFloat(inputs.minAmplitude.value);
    }
    if (inputs.minPosition?.value) {
        filters.min_position = parseFloat(inputs.minPosition.value) / 100;
    }
    // ... 其他筛选条件处理
    return filters;
}

// 监控配置功能
function showConfigDialog(symbol) {
    const dialog = document.getElementById('configDialog');
    dialog.style.display = 'block';
    
    document.getElementById('saveConfig').onclick = () => {
        const config = {
            allocated_money: parseFloat(document.getElementById('allocatedMoney').value),
            leverage: parseInt(document.getElementById('leverage').value),
            take_profit: parseFloat(document.getElementById('takeProfit').value)
        };
        // 保存配置...
    };
}
```

功能说明：
- 监控列表展示
  - 实时价格更新
  - 状态标识显示
  - 删除功能
  - 参数编辑
- 筛选功能
  - 多维度筛选
  - 分页展示
  - 结果统计
- 配置功能
  - 资金配置
  - 杠杆设置
  - 止盈设置

### 4.3 样式��计
```css
/* 表格样式 (style.css) */
.data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
}

.data-table th,
.data-table td {
    padding: 8px;
    border: 1px solid #ddd;
}

/* 按钮样式 (oscillation.css) */
.edit-btn {
    padding: 2px 8px;
    background-color: #1890ff;
    color: white;
    border: none;
    border-radius: 3px;
}

.delete-btn {
    padding: 2px 8px;
    background-color: #ff4d4f;
    color: white;
    border: none;
    border-radius: 3px;
}
```

## 5. API接口文档

### 5.1 监控管理接口

#### 获取监控列表
```
GET /api/monitor_symbols/<account_id>

请求头:
- X-Server-ID: 服务器ID

响应:
{
    "status": "success",
    "data": [
        {
            "id": 1,
            "symbol": "BTCUSDT",
            "allocated_money": 1000.00,
            "leverage": 3,
            "take_profit": 100.00,
            "status": "waiting",
            "is_active": true,
            "sync_time": "2024-01-01 12:00:00"
        },
        // ...
    ]
}
```

#### 保存监控记录
```
POST /api/save_monitor_symbols

请求头:
- Content-Type: application/json
- X-Server-ID: 服务器ID

请求体:
{
    "accountId": "34",
    "symbols": [
        {
            "symbol": "BTCUSDT",
            "allocated_money": 1000.00,
            "leverage": 3,
            "take_profit": 100.00
        }
    ]
}

响应:
{
    "status": "success",
    "message": "保存成功"
}
```

#### 删除监控记录
```
DELETE /api/monitor/<id>

请求头:
- X-Server-ID: 服务器ID

响应:
{
    "success": true,
    "message": "删除成功"
}
```

### 5.2 数据查询接口

#### 获取价格范围数据
```
GET /api/price_ranges

参数:
- account_id: 账户ID
- strategy_type: 策略类型(break/oscillation)
- min_amplitude: 最小振幅
- max_amplitude: 最大振幅
- min_position: 最小位置比
- max_position: 最大位置比
- min_volume: 最小成交额
- max_volume: 最大成交额
- symbol: 搜索关键词
- page: 页码
- per_page: 每页记录数

响应:
{
    "status": "success",
    "data": [...],
    "total": 100
}
```

#### 获取K线数据
```
GET /api/kline_data/<symbol>

响应:
{
    "status": "success",
    "data": {
        "times": [...],
        "prices": [...],
        "volumes": [...]
    }
}
```

## 6. 开发规范

### 6.1 Python代码规范
- 遵循PEP8规范
- 使用类型注解
- 编写详细的文档字符串
```python
def get_price_ranges(
    self,
    account_id: str,
    strategy_type: str,
    filters: Dict[str, Any]
) -> Dict[str, Any]:
    """获取价格范围数据
    
    Args:
        account_id: 账户ID
        strategy_type: 策略类型(break/oscillation)
        filters: 筛选条件字典
        
    Returns:
        包含数据和总数的字典
    """
```

### 6.2 JavaScript代码规范
- 使用ES6+语法
- 统一的错误处理
- 避免全局变量
```javascript
// 推荐写法
const handleError = (error) => {
    console.error('操作失败:', error);
    alert(error.message || '未知错误');
};

try {
    await saveConfig(data);
} catch (error) {
    handleError(error);
}
```

### 6.3 CSS规范
- 使用BEM命名规范
- 模块化组织样式
- 避免内联样式
```css
/* 推荐写法 */
.monitor-list__item {
    /* 监控列表项样式 */
}

.monitor-list__item--active {
    /* 激活状态样式 */
}

.monitor-list__button {
    /* 按钮样式 */
}
```

### 6.4 Git提交规范
- feat: 新功能
- fix: 修复bug
- docs: 文档更新
- style: 代码格式调整
- refactor: 代码重构

```bash
# 示例
git commit -m "feat: 添加震荡交易监控功能"
git commit -m "fix: 修复价格数据更新异常"
git commit -m "docs: 更新API文档"
```

## 7. 部署说明

### 7.1 环境要求
```
# Python依赖
Python >= 3.7
Flask >= 2.0.0
SQLAlchemy >= 1.4.0
PyMySQL >= 1.0.0

# 数据库
MySQL >= 5.7

# 系统要求
CPU: 2核+
内存: 4GB+
磁盘: 50GB+
```

### 7.2 安装步骤
```bash
# 1. 克隆代码
git clone https://github.com/your-repo/trading-monitor.git
cd trading-monitor

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置数据库
# 修改 config.py 中的数据库配置
SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://user:password@localhost/dbname'

# 5. 初始化数据库
flask db upgrade

# 6. 启动应用
flask run
```

### 7.3 生产环境配置
```nginx
# Nginx配置示例
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```ini
# Supervisor配置示例
[program:trading-monitor]
directory=/path/to/trading-monitor
command=/path/to/venv/bin/gunicorn -w 4 -b 127.0.0.1:5000 wsgi:app
user=www-data
autostart=true
autorestart=true
```

## 8. 常见问题

### 8.1 数据库连接问题
```python
# 问题：连接池耗尽
# 解决方案：调整连接池配置
class DatabaseConnection:
    def _create_connection_pool(self):
        return pymysql.connect(
            **self.config,
            cursorclass=pymysql.cursors.DictCursor,
            pool_size=20,  # 增加连接池大小
            max_overflow=10,  # 允许的最大溢出连接数
            pool_timeout=30,  # 连接超时时间
            pool_recycle=1800  # 连接回收时间
        )
```

### 8.2 性能优化
- 数据库索引优化
- 查询缓存
- 分页加载
- 定时任务优化

## 9. 后续规划

### 9.1 功能增强
- [ ] WebSocket实时数据推送
- [ ] 多策略组合支持
- [ ] 回测系统集成
- [ ] 风控模块完善

### 9.2 技术改进
- [ ] 前端框架重构(Vue.js)
- [ ] 微服务架构演进
- [ ] 容器化部署支持
- [ ] 监控告警系统 