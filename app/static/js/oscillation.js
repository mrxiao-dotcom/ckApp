// 检查并初始化全局变量
if (typeof window.serverInfo === 'undefined') {
    window.serverInfo = {};
    try {
        const urlParams = new URLSearchParams(window.location.search);
        const serverInfoStr = urlParams.get('serverInfo');
        if (serverInfoStr) {
            window.serverInfo = JSON.parse(decodeURIComponent(serverInfoStr));
        }
    } catch (error) {
        console.error('解析服务器信息失败:', error);
    }
}

if (typeof window.currentPage === 'undefined') {
    window.currentPage = 1;
}
if (typeof window.perPage === 'undefined') {
    window.perPage = 30;
}
if (typeof window.isLoadingMonitorList === 'undefined') {
    window.isLoadingMonitorList = false;
}

// 初始化页面
document.addEventListener('DOMContentLoaded', () => {
    console.log('页面加载完成');
    initializeEventListeners();
    
    // 如果默认显示监控列表，则加载一次数据
    if (document.querySelector('[data-tab="monitor"]').classList.contains('active')) {
        loadMonitorList();
    }
});

// 初始化事件监听器
function initializeEventListeners() {
    // 标签页切换
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            switchTab(tab);
        });
    });

    // 筛选按钮点击事件
    const filterButton = document.querySelector('.filter-button');
    if (filterButton) {
        // 移除 onclick 属性绑定的事件
        filterButton.removeAttribute('onclick');
        // 使用 addEventListener 绑定事件
        filterButton.addEventListener('click', applyFilter);
    }

    // 移除所有自动触发的事件监听
    ['minAmplitude', 'maxAmplitude', 'minPosition', 'maxPosition', 'minVolume', 'maxVolume', 'symbol-search'].forEach(id => {
        const input = document.getElementById(id);
        if (input) {
            // 清除所有已存在的事件监听器
            const newInput = input.cloneNode(true);
            input.parentNode.replaceChild(newInput, input);
        }
    });

    // 保存按钮点击事件
    const saveButton = document.getElementById('save-selected');
    if (saveButton) {
        saveButton.addEventListener('click', saveSelectedSymbols);
    }
}

// 加载监控列表
function loadMonitorList() {
    if (!accountId) {
        console.error('未找到账户ID');
        return;
    }

    if (!serverInfo.serverId) {
        console.error('未找到服务器ID');
        return;
    }

    // 如果正在加载，则不重复加载
    if (isLoadingMonitorList) {
        console.log('正在加载中，跳过重复请求');
        return;
    }

    isLoadingMonitorList = true;
    console.log('正在加载震荡交易监控列表', {
        accountId,
        serverId: serverInfo.serverId
    });

    fetch(`/api/oscillation_monitor_symbols/${accountId}`, {
        method: 'GET',
        headers: {
            'X-Server-ID': serverInfo.serverId,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => {
                throw new Error(err.message || '请求失败');
            });
        }
        return response.json();
    })
    .then(result => {
        if (result.status === 'success') {
            console.log('获取数据成功:', result.data.length, '条记录');
            updateMonitorTable(result.data);
        } else {
            throw new Error(result.message || '获取数据失败');
        }
    })
    .catch(error => {
        console.error('获取监控列表错误:', error);
        const tbody = document.getElementById('monitor-list');
        tbody.innerHTML = `<tr><td colspan="12" class="text-center text-danger">加载失败: ${error.message}</td></tr>`;
    })
    .finally(() => {
        isLoadingMonitorList = false;  // 重置加载状态
    });
}

// 保存监控中的品种
function saveSelectedSymbols() {
    const selectedCheckboxes = document.querySelectorAll('#symbols-list input[type="checkbox"]:checked');
    
    if (selectedCheckboxes.length === 0) {
        alert('请选择要保存的品种');
        return;
    }
    if (selectedCheckboxes.length > 1) {
        alert('每次只能选择一个品种添加到监控列表');
        return;
    }

    const symbol = selectedCheckboxes[0].value;
    showConfigDialog(symbol);
}

// 显示配置对话框
function showConfigDialog(symbol) {
    const dialog = document.getElementById('configDialog');
    dialog.style.display = 'block';
    
    // 重置表单
    document.getElementById('allocatedMoney').value = '';
    document.getElementById('leverage').value = '3';
    document.getElementById('takeProfit').value = '';
    
    // 保存配置
    document.getElementById('saveConfig').onclick = () => {
        const config = {
            allocated_money: parseFloat(document.getElementById('allocatedMoney').value),
            leverage: parseInt(document.getElementById('leverage').value),
            take_profit: parseFloat(document.getElementById('takeProfit').value)
        };
        
        if (!config.allocated_money || config.allocated_money <= 0) {
            alert('请输入有效的配置市值');
            return;
        }
        if (!config.leverage || config.leverage < 1) {
            alert('请输入有效的杠杆倍数');
            return;
        }
        if (!config.take_profit || config.take_profit <= 0) {
            alert('请输入有效的止盈目标金额');
            return;
        }
        
        saveMonitorSymbol(symbol, config);
        dialog.style.display = 'none';
    };
    
    // 取消按钮
    document.getElementById('cancelConfig').onclick = () => {
        dialog.style.display = 'none';
    };
    
    // 关闭按钮
    dialog.querySelector('.close-button').onclick = () => {
        dialog.style.display = 'none';
    };
}

// 保存监控品种
async function saveMonitorSymbol(symbol, config) {
    try {
        const response = await fetch('/api/save_oscillation_monitor', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Server-ID': serverInfo.serverId
            },
            body: JSON.stringify({
                accountId: accountId,
                symbols: [{
                    symbol: symbol,
                    allocated_money: config.allocated_money,
                    leverage: config.leverage,
                    take_profit: config.take_profit
                }]
            })
        });
        
        const result = await response.json();
        if (result.status === 'success') {
            alert('保存成功');
            // 切换到监控列表并刷新
            const monitorTab = document.querySelector('[data-tab="monitor"]');
            if (monitorTab) {
                switchTab(monitorTab);
            }
        } else {
            alert('保存失败: ' + result.message);
        }
    } catch (error) {
        console.error('保存失败:', error);
        alert('保存失败，请重试');
    }
}

// 获取状态样式类
function getBadgeClass(status) {
    const upperStatus = (status || '').toUpperCase();
    switch (upperStatus) {
        case 'WAITING': return 'bg-warning';
        case 'OPENED': return 'bg-success';
        case 'CLOSED': return 'bg-secondary';
        default: return 'bg-secondary';
    }
}

function getStatusText(status) {
    const upperStatus = (status || '').toUpperCase();
    switch (upperStatus) {
        case 'WAITING': return '等待开仓';
        case 'OPENED': return '已开仓';
        case 'CLOSED': return '已关闭';
        default: return status || '-';
    }
}

// 获取方向文本
function getDirectionText(side) {
    if (!side) return '-';
    switch(side.toUpperCase()) {
        case 'LONG': return '多';
        case 'SHORT': return '空';
        default: return side;
    }
}

// 更新监控表格
function updateMonitorTable(data) {
    const tbody = document.getElementById('monitor-list');
    tbody.innerHTML = '';
    
    if (!data.length) {
        tbody.innerHTML = '<tr><td colspan="12" class="text-center">暂无监控数据</td></tr>';
        return;
    }
    
    // 过滤掉已关闭的记录
    const activeData = data;  // 移除过滤,显示所有记录包括closed状态
    
    activeData.forEach(item => {
        const tr = document.createElement('tr');
        tr.className = item.is_active ? '' : 'table-secondary';
        
        // 添加调试日志
        console.log('行数据:', {
            symbol: item.symbol,
            status: item.status,
            is_active: item.is_active
        });

        tr.innerHTML = `
            <td>${item.symbol}</td>
            <td class="text-right">${Number(item.last_price).toFixed(4)}</td>
            <td class="text-center">${formatDateTime(item.update_time)}</td>
            <td class="text-right">${(Number(item.amplitude) * 100).toFixed(2)}%</td>
            <td class="text-right">${(Number(item.position_ratio) * 100).toFixed(2)}%</td>
            <td class="text-center">${getDirectionText(item.position_side)}</td>
            <td class="text-right">${Number(item.allocated_money).toFixed(2)}</td>
            <td class="text-right">${item.leverage}x</td>
            <td class="text-right">${Number(item.take_profit).toFixed(2)}</td>
            <td>
                <span class="badge ${getBadgeClass(item.status)}">
                    ${getStatusText(item.status)}
                </span>
            </td>
            <td class="text-center">
                <button onclick="deleteMonitor(${item.id})" class="delete-btn">
                    删除
                </button>
            </td>
            <td class="text-center">${formatDateTime(item.sync_time)}</td>
            <td class="action-column">
                <button onclick="editMonitorItem(${item.id})" class="edit-btn">
                    编辑
                </button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

// 切换标签页
function switchTab(tab) {
    // 移除所有活动状态
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    
    // 添加新的活动状态
    tab.classList.add('active');
    const tabId = tab.getAttribute('data-tab');
    const tabPanel = document.getElementById(`${tabId}-content`);
    
    if (tabPanel) {
        tabPanel.classList.add('active');
        // 如果切换到监控标签页，加载一次数据
        if (tabId === 'monitor') {
            loadMonitorList();
        }
    }
}

// 应用筛选
function applyFilter() {
    console.log('点击筛选按钮');
    currentPage = 1;  // 重置页码
    loadSymbolData();  // 加载数据
}

// 获取筛选条件
function getFilterValues() {
    const inputs = {
        minAmplitude: document.getElementById('minAmplitude'),
        maxAmplitude: document.getElementById('maxAmplitude'),
        minPosition: document.getElementById('minPosition'),
        maxPosition: document.getElementById('maxPosition'),
        minVolume: document.getElementById('minVolume'),
        maxVolume: document.getElementById('maxVolume'),
        symbol: document.getElementById('symbol-search')
    };

    const filters = {};

    // 处理振幅条件 - 直接使用百分比值
    if (inputs.minAmplitude?.value) {
        const value = parseFloat(inputs.minAmplitude.value);
        if (!isNaN(value)) {
            filters.min_amplitude = value;  // 直接使用百分比值
        }
    }
    if (inputs.maxAmplitude?.value) {
        const value = parseFloat(inputs.maxAmplitude.value);
        if (!isNaN(value)) {
            filters.max_amplitude = value;  // 直接使用百分比值
        }
    }

    // 处理位置条件 - 转换为小数
    if (inputs.minPosition?.value) {
        const value = parseFloat(inputs.minPosition.value);
        if (!isNaN(value)) {
            filters.min_position = value / 100;  // 将百分比转换为小数
        }
    }
    if (inputs.maxPosition?.value) {
        const value = parseFloat(inputs.maxPosition.value);
        if (!isNaN(value)) {
            filters.max_position = value / 100;  // 将百分比转换为小数
        }
    }

    // 处理成交量条件 - 直接使用百万为单位的值
    if (inputs.minVolume?.value) {
        const value = parseFloat(inputs.minVolume.value);
        if (!isNaN(value)) {
            filters.min_volume = value;  // 直接使用百万为单位的值
        }
    }
    if (inputs.maxVolume?.value) {
        const value = parseFloat(inputs.maxVolume.value);
        if (!isNaN(value)) {
            filters.max_volume = value;  // 直接使用百万为单位的值
        }
    }

    // 处理品种搜索
    if (inputs.symbol?.value) {
        filters.symbol = inputs.symbol.value.trim().toUpperCase();
    }

    // 添加调试日志
    console.log('筛选条件:', {
        '原始输入': {
            '振幅': {
                '最小': inputs.minAmplitude?.value,
                '最大': inputs.maxAmplitude?.value
            },
            '位置': {
                '最小': inputs.minPosition?.value,
                '最大': inputs.maxPosition?.value
            },
            '成交量': {
                '最小': inputs.minVolume?.value,
                '最大': inputs.maxVolume?.value
            }
        },
        '发送参数': filters
    });

    return filters;
}

// 加载品种数据
function loadSymbolData() {
    const filters = getFilterValues();
    console.log('加载数据用的筛选条件:', filters);
    
    const params = new URLSearchParams();
    
    // 添加基础参数
    params.append('account_id', accountId);
    params.append('strategy_type', 'oscillation');
    params.append('page', currentPage);
    params.append('per_page', perPage);
    
    // 添加筛选参数
    Object.entries(filters).forEach(([key, value]) => {
        if (value !== null && value !== undefined && value !== '') {
            params.append(key, value);
        }
    });
    
    console.log('请求数:', Object.fromEntries(params));

    // 发送请求
    fetch(`/api/price_ranges?${params.toString()}`, {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
            'X-Server-ID': serverInfo.serverId
        }
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .then(data => {
        if (data.status === 'success') {
            displayPriceRanges(data);
            if (data.total) {
                updatePagination(data.total);
            }
        } else {
            throw new Error(data.message || '加载失败');
        }
    })
    .catch(error => {
        console.error('请求失败:', error);
        const tableBody = document.querySelector('#priceRangeTable tbody');
        if (tableBody) {
            tableBody.innerHTML = `<tr><td colspan="10" class="text-center">加载失败: ${error.message}</td></tr>`;
        }
    });
}

// 其他辅助函数
function formatDateTime(dateTimeStr) {
    if (!dateTimeStr) return '-';
    
    try {
        const date = new Date(dateTimeStr);
        const month = (date.getMonth() + 1).toString().padStart(2, '0');
        const day = date.getDate().toString().padStart(2, '0');
        const hours = date.getHours().toString().padStart(2, '0');
        const minutes = date.getMinutes().toString().padStart(2, '0');
        const seconds = date.getSeconds().toString().padStart(2, '0');
        
        return `${month}-${day} ${hours}:${minutes}:${seconds}`;
    } catch (e) {
        console.error('日期格式化错误:', e);
        return dateTimeStr;
    }
}

// 显示价格范围数据
function displayPriceRanges(result) {
    // 更新记录数显示
    const statsDiv = document.getElementById('filter-stats');
    if (statsDiv) {
        statsDiv.innerHTML = `
            <span class="text-muted">
                符合条件的记录：<strong>${result.data.length}</strong> 条
                ${result.total ? `（共 ${result.total} 条）` : ''}
            </span>
        `;
    }

    // 更新表格内容
    const tableBody = document.querySelector('#priceRangeTable tbody');
    tableBody.innerHTML = '';

    if (!result.data.length) {
        tableBody.innerHTML = '<tr><td colspan="10" class="text-center">没有找到数据</td></tr>';
        return;
    }

    result.data.forEach(item => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td class="checkbox-column">
                <input type="checkbox" value="${item.symbol}">
            </td>
            <td><a href="#" onclick="showKlineModal('${item.symbol}'); return false;">${item.symbol}</a></td>
            <td class="text-right">${Number(item.high_price_20d).toFixed(4)}</td>
            <td class="text-right">${Number(item.low_price_20d).toFixed(4)}</td>
            <td class="text-right">${Number(item.last_price).toFixed(4)}</td>
            <td class="text-right">${(Number(item.amplitude)).toFixed(2)}%</td>
            <td class="text-right">${(Number(item.position_ratio)).toFixed(2)}%</td>
            <td class="text-right">${formatVolume(Number(item.volume_24h))}</td>
            <td class="text-center">${formatDateTime(item.update_time)}</td>
            <td class="action-column">
                <button onclick="addToMonitor('${item.symbol}')" class="monitor-btn">监控</button>
            </td>
        `;
        tableBody.appendChild(row);
    });
}

// 格式化成交量显示
function formatVolume(volume) {
    if (!volume) return '-';
    if (volume >= 1000000000) {
        return (volume / 1000000000).toFixed(2) + 'B';
    }
    if (volume >= 1000000) {
        return (volume / 1000000).toFixed(2) + 'M';
    }
    if (volume >= 1000) {
        return (volume / 1000).toFixed(2) + 'K';
    }
    return volume.toFixed(2);
}

// 切换激活状态
async function toggleMonitorActive(id) {
    if (confirm('确定要删除这条监控记录吗？')) {
        try {
            const response = await fetch(`/api/monitor/${id}`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Server-ID': serverInfo.serverId
                }
            });
            
            const data = await response.json();
            if (data.success) {
                loadMonitorList();  // 重新加载列表
            } else {
                alert('删除失败：' + data.message);
            }
        } catch (error) {
            alert('删除失败：' + error);
        }
    }
}

// 编辑监控项
function editMonitorItem(id) {
    fetch(`/api/oscillation/${id}`, {
        headers: {
            'X-Server-ID': serverInfo.serverId
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            showEditDialog(data.monitor);
        } else {
            alert('获取监控数据失败：' + data.message);
        }
    })
    .catch(error => {
        console.error('获取监控数据失败:', error);
        alert('获取监控数据失败，请重试');
    });
}

// 显示编辑对话框
function showEditDialog(monitorId) {
    const dialog = document.getElementById('editDialog');
    const closeBtn = dialog.querySelector('.close-button');
    const saveBtn = document.getElementById('saveEdit');
    const cancelBtn = document.getElementById('cancelEdit');
    
    // 保存原始数据
    let originalData = null;
    
    // 获取当前记录的数据
    fetch(`/api/monitor/${monitorId}`, {
        headers: {
            'X-Server-ID': serverInfo.serverId
        }
    })
    .then(response => response.json())
    .then(result => {
        if (result.status === 'success') {
            originalData = result.monitor;
            // 显示止盈金额的输入框
            document.getElementById('editTakeProfit').value = originalData.take_profit;
            
            // 显示对话框
            dialog.style.display = 'block';
            
            // 保存编辑
            saveBtn.onclick = () => {
                const takeProfit = parseFloat(document.getElementById('editTakeProfit').value);
                
                // 验证输入
                if (!takeProfit || takeProfit <= 0) {
                    alert('请输入有效的止盈金额');
                    return;
                }
                
                // 保存更新 - 发送所有必需字段
                fetch(`/api/monitor/${monitorId}`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Server-ID': serverInfo.serverId
                    },
                    body: JSON.stringify({
                        allocated_money: originalData.allocated_money,
                        leverage: originalData.leverage,
                        take_profit: takeProfit
                    })
                })
                .then(response => response.json())
                .then(result => {
                    if (result.status === 'success') {
                        alert('更新成功');
                        dialog.style.display = 'none';
                        loadMonitorList();  // 重新加载列表
                    } else {
                        alert('更新失败：' + result.message);
                    }
                })
                .catch(error => {
                    alert('更新失败：' + error);
                });
            };
        } else {
            alert('获取数据失败：' + result.message);
        }
    })
    .catch(error => {
        alert('获取数据失败：' + error);
    });
    
    // 关闭对话框
    const closeDialog = () => {
        dialog.style.display = 'none';
    };
    
    closeBtn.onclick = closeDialog;
    cancelBtn.onclick = closeDialog;
    
    // 点击对话框外部不关闭
    dialog.onclick = (event) => {
        if (event.target === dialog) {
            event.stopPropagation();
        }
    };
}

// 关闭配置对话框
function closeConfigDialog() {
    const dialog = document.getElementById('configDialog');
    dialog.style.display = 'none';
}

// 添加到监控列表
function addToMonitor(symbol) {
    showConfigDialog(symbol);
}

// 更新页
function updatePagination(total) {
    // 只在筛选页面显示分页
    const filterPanel = document.getElementById('filter-content');
    if (!filterPanel || !filterPanel.classList.contains('active')) {
        return;  // 如果不是筛选页面不显示分页
    }

    const totalPages = Math.ceil(total / perPage);
    const paginationContainer = document.createElement('div');
    paginationContainer.className = 'pagination';
    
    // 计算显示的页码范围
    let startPage = Math.max(1, currentPage - 2);
    let endPage = Math.min(totalPages, startPage + 4);
    
    // 调整始页，确保终显示5个页码（如果有）
    if (endPage - startPage < 4) {
        startPage = Math.max(1, endPage - 4);
    }
    
    // 创建分页HTML
    let paginationHtml = `
        <div class="pagination-info">
            共 ${total} 条记录，${totalPages} 页
        </div>
        <div class="pagination-buttons">
    `;
    
    // 上一页按钮
    paginationHtml += `
        <button class="page-button" 
                onclick="changePage(${currentPage - 1})"
                ${currentPage === 1 ? 'disabled' : ''}>
            上一页
        </button>
    `;
    
    // 第一页
    if (startPage > 1) {
        paginationHtml += `
            <button class="page-button" onclick="changePage(1)">1</button>
            ${startPage > 2 ? '<span class="page-ellipsis">...</span>' : ''}
        `;
    }
    
    // 页码按钮
    for (let i = startPage; i <= endPage; i++) {
        paginationHtml += `
            <button class="page-button ${i === currentPage ? 'active' : ''}" 
                    onclick="changePage(${i})">
                ${i}
            </button>
        `;
    }
    
    // 最后一页
    if (endPage < totalPages) {
        paginationHtml += `
            ${endPage < totalPages - 1 ? '<span class="page-ellipsis">...</span>' : ''}
            <button class="page-button" onclick="changePage(${totalPages})">
                ${totalPages}
            </button>
        `;
    }
    
    // 下一页按钮
    paginationHtml += `
        <button class="page-button" 
                onclick="changePage(${currentPage + 1})"
                ${currentPage === totalPages ? 'disabled' : ''}>
            下一页
        </button>
    </div>`;
    
    paginationContainer.innerHTML = paginationHtml;
    
    // 替换现有的分页区域
    const existingPagination = document.querySelector('.pagination');
    if (existingPagination) {
        existingPagination.replaceWith(paginationContainer);
    } else {
        // 添加到表格后面
        const tableContainer = document.querySelector('.data-table-container');
        if (tableContainer) {
            tableContainer.appendChild(paginationContainer);
        }
    }
}

// 切换页码
function changePage(page) {
    if (page < 1) return;
    currentPage = page;
    loadSymbolData();
}

// 添加删除监控记录的函数
function deleteMonitor(id) {
    if (confirm('确定要删除这条监控记录吗？')) {
        fetch(`/api/monitor/${id}/delete`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Server-ID': serverInfo.serverId
            }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(result => {
            if (result.status === 'success') {
                alert('删除成功');
                loadMonitorList();  // 重新加载列表
            } else {
                throw new Error(result.message || '删除失败');
            }
        })
        .catch(error => {
            console.error('删除失败:', error);
            alert('删除失败：' + error.message);
        });
    }
}

