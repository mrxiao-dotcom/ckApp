// 全局变量声明或获取
window.accountId = window.accountId || new URLSearchParams(window.location.search).get('accountId');
window.serverInfo = window.serverInfo || JSON.parse(decodeURIComponent(new URLSearchParams(window.location.search).get('serverInfo')));

// K线图实例
let klineChart = null;
let volumeChart = null;

// 显示K线图模态框
function showKlineModal(symbol) {
    // 初始化模态框
    document.getElementById('klineModal').style.display = 'block';
    document.getElementById('klineSymbol').textContent = symbol;
    
    // 初始化图表
    if (!klineChart) {
        klineChart = echarts.init(document.getElementById('klineChart'));
    }
    if (!volumeChart) {
        volumeChart = echarts.init(document.getElementById('volumeChart'));
    }
    
    // 加载数据
    loadKlineData(symbol);
}

// 关闭K线图模态框
function closeKlineModal() {
    document.getElementById('klineModal').style.display = 'none';
}

// 加载K线数据
async function loadKlineData(symbol) {
    try {
        const response = await fetch(`/api/kline/${symbol}?accountId=${window.accountId}`, {
            headers: {
                'X-Server-ID': window.serverInfo.serverId
            }
        });
        
        const result = await response.json();
        if (result.status === 'success') {
            renderCharts(result.data);
        } else {
            alert('获取K线数据失败：' + result.message);
        }
    } catch (error) {
        console.error('加载K线数据失败:', error);
        alert('加载K线数据失败，请重试');
    }
}

// 渲染图表
function renderCharts(data) {
    // K线图配置
    const klineOption = {
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'cross'
            }
        },
        legend: {
            data: ['K线', 'MA5', 'MA10', 'MA20']
        },
        grid: {
            left: '10%',
            right: '10%',
            bottom: '15%'
        },
        xAxis: {
            type: 'category',
            data: data.dates,
            scale: true,
            boundaryGap: false,
            axisLine: { onZero: false },
            splitLine: { show: false },
            splitNumber: 20
        },
        yAxis: {
            scale: true,
            splitLine: { show: true }
        },
        dataZoom: [
            {
                type: 'inside',
                start: 0,
                end: 100
            },
            {
                show: true,
                type: 'slider',
                bottom: '5%',
                start: 0,
                end: 100
            }
        ],
        series: [
            {
                name: 'K线',
                type: 'candlestick',
                data: data.klineData,
                itemStyle: {
                    color: '#ef232a',
                    color0: '#14b143',
                    borderColor: '#ef232a',
                    borderColor0: '#14b143'
                }
            },
            {
                name: 'MA5',
                type: 'line',
                data: data.ma5,
                smooth: true,
                lineStyle: { opacity: 0.5 }
            },
            {
                name: 'MA10',
                type: 'line',
                data: data.ma10,
                smooth: true,
                lineStyle: { opacity: 0.5 }
            },
            {
                name: 'MA20',
                type: 'line',
                data: data.ma20,
                smooth: true,
                lineStyle: { opacity: 0.5 }
            }
        ]
    };

    // 成交量图配置
    const volumeOption = {
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'cross'
            }
        },
        grid: {
            left: '10%',
            right: '10%',
            height: '70%'
        },
        xAxis: {
            type: 'category',
            data: data.dates,
            axisLabel: { show: false }
        },
        yAxis: {
            type: 'value',
            scale: true
        },
        series: [
            {
                name: '成交量',
                type: 'bar',
                data: data.volumes,
                itemStyle: {
                    color: function(params) {
                        const i = params.dataIndex;
                        const closePrice = data.klineData[i][1];  // 收盘价
                        const openPrice = data.klineData[i][0];   // 开盘价
                        return closePrice > openPrice ? '#ef232a' : '#14b143';
                    }
                }
            }
        ]
    };

    // 设置图表联动
    klineChart.group = 'group1';
    volumeChart.group = 'group1';

    // 渲染图表
    klineChart.setOption(klineOption);
    volumeChart.setOption(volumeOption);
}

// 监听窗口大小变化，调整图表大小
window.addEventListener('resize', function() {
    if (klineChart) {
        klineChart.resize();
    }
    if (volumeChart) {
        volumeChart.resize();
    }
});

// 监听ESC键关闭模态框
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        closeKlineModal();
    }
}); 