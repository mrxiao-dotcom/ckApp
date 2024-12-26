// 在文件开头添加解析服务器信息的代码
let serverInfo = {};
try {
    const urlParams = new URLSearchParams(window.location.search);
    const serverInfoStr = urlParams.get('serverInfo');
    if (serverInfoStr) {
        serverInfo = JSON.parse(decodeURIComponent(serverInfoStr));
    }
} catch (error) {
    console.error('解析服务器信息失败:', error);
}

// 使用全局变量
let currentPage = 1;
const perPage = 30;

// 在文件开头添加标记变量
let isLoadingMonitorList = false;

// 初始化页面
document.addEventListener('DOMContentLoaded', () => {
    console.log('页面加载完成');
    initializeEventListeners();
    loadSymbolData();
});

// 初始化事件监听器
function initializeEventListeners() {
    // 标签页切换
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            switchTab(tab);
        });
    });

    // 全选/取消全选
    const selectAllCheckbox = document.getElementById('select-all');
    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', handleSelectAll);
    }

    // 保存按钮
    const saveButton = document.getElementById('save-selected');
    if (saveButton) {
        saveButton.addEventListener('click', saveSelectedSymbols);
    }

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
        // 如果切换到监控标签页，加载监控列表
        if (tabId === 'monitor' && !isLoadingMonitorList) {
            loadMonitorList();
        }
    }
}

// 处理全选/取消全选
function handleSelectAll(event) {
    console.log('全选状态改变:', event.target.checked);
    const checkboxes = document.querySelectorAll('#symbols-list input[type="checkbox"]');
    checkboxes.forEach(checkbox => {
        checkbox.checked = event.target.checked;
    });
}

// 处理筛选条件变化
function handleFilterChange() {
    console.log('筛选条件改变');
    loadSymbolData();
}

// 获取筛选条件值
function getFilterValues() {
    const filters = {};
    
    try {
        // 获取并打印每个输入框的值
        const inputs = {
            minAmplitude: document.getElementById('minAmplitude'),
            maxAmplitude: document.getElementById('maxAmplitude'),
            minPosition: document.getElementById('minPosition'),
            maxPosition: document.getElementById('maxPosition'),
            minVolume: document.getElementById('minVolume'),
            maxVolume: document.getElementById('maxVolume'),
            symbolSearch: document.getElementById('symbol-search')
        };
        
        // 打印所有输入框的值
        Object.entries(inputs).forEach(([key, element]) => {
            if (element) {
                console.log(`${key}: ${element.value}`);
            } else {
                console.warn(`${key} 元素未找到`);
            }
        });
        
        // 振幅范围（输入为百分比，转换为小数）
        if (inputs.minAmplitude?.value) {
            const value = parseFloat(inputs.minAmplitude.value);
            if (!isNaN(value)) filters.min_amplitude = value / 100;  // 转换为小数
        }
        if (inputs.maxAmplitude?.value) {
            const value = parseFloat(inputs.maxAmplitude.value);
            if (!isNaN(value)) filters.max_amplitude = value / 100;  // 转换为小数
        }
        
        // 位置比范围（输入为百分比，转换为小数）
        if (inputs.minPosition?.value) {
            const value = parseFloat(inputs.minPosition.value);
            if (!isNaN(value)) filters.min_position = value / 100;  // 转换为小数
        }
        if (inputs.maxPosition?.value) {
            const value = parseFloat(inputs.maxPosition.value);
            if (!isNaN(value)) filters.max_position = value / 100;  // 转换为小数
        }
        
        // 成交额范围（输入为百万，转换为USDT）
        if (inputs.minVolume?.value) {
            const value = parseFloat(inputs.minVolume.value);
            if (!isNaN(value)) filters.min_volume = value * 1000000;  // 百万转USDT
        }
        if (inputs.maxVolume?.value) {
            const value = parseFloat(inputs.maxVolume.value);
            if (!isNaN(value)) filters.max_volume = value * 1000000;  // 百万转USDT
        }
        
        // 搜索关键词
        if (inputs.symbolSearch?.value?.trim()) {
            filters.symbol = inputs.symbolSearch.value.trim();
        }
        
        console.log('构建的筛选条件:', filters);
        return filters;
        
    } catch (error) {
        console.error('获取筛选条件时出错:', error);
        return {};
    }
}

// 应用筛选
function applyFilter() {
    console.log('点击筛选按钮');
    currentPage = 1;  // 重置页码
    loadSymbolData();  // 加载数据
}

// 更新符号表格
function updateSymbolTable(data) {
    console.log('更新表格数据:', data);
    const tbody = document.getElementById('symbols-list');
    if (!tbody) {
        console.error('未找到表格体元素');
        return;
    }

    if (!data.length) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center">没有找到数据</td></tr>';
        return;
    }

    tbody.innerHTML = data.map(item => `
        <tr>
            <td class="checkbox-column">
                <input type="checkbox" value="${item.symbol}">
            </td>
            <td>${item.symbol}</td>
            <td>${item.high_price_20d.toFixed(4)}</td>
            <td>${item.low_price_20d.toFixed(4)}</td>
            <td>${(item.amplitude * 100).toFixed(2)}%</td>
            <td>${(item.position_ratio * 100).toFixed(2)}%</td>
        </tr>
    `).join('');
}

// 保存选中的符号
function saveSelectedSymbols() {
    console.log('保存选中的符号');
    const selectedCheckboxes = document.querySelectorAll('#symbols-list input[type="checkbox"]:checked');
    
    // 检查是否只选中了一个品种
    if (selectedCheckboxes.length === 0) {
        alert('请选择要保存的品种');
        return;
    }
    if (selectedCheckboxes.length > 1) {
        alert('每次只能选择一个品种添加到监控列表');
        return;
    }

    const symbol = selectedCheckboxes[0].value;
    
    // 检查否已在监控列表中
    checkSymbolExists(symbol).then(exists => {
        if (exists) {
            alert('该品种已在监控列表中');
            return;
        }
        showConfigDialog(symbol);
    });
}

// 检查品种是否存在于监控列表
async function checkSymbolExists(symbol) {
    try {
        const response = await fetch(`/api/check_monitor_symbol/${window.accountId}/${symbol}`);
        const data = await response.json();
        return data.exists;
    } catch (error) {
        console.error('检查品种是否存在失败:', error);
        return false;
    }
}

// 显示配置对话框
function showConfigDialog(symbol) {
    const dialog = document.getElementById('configDialog');
    const dialogContent = dialog.querySelector('.modal-content');
    const header = document.getElementById('dialogHeader');
    const closeBtn = dialog.querySelector('.close-button');
    const saveBtn = document.getElementById('saveConfig');
    const cancelBtn = document.getElementById('cancelConfig');
    
    // 重置表单
    document.getElementById('allocatedMoney').value = '';
    document.getElementById('leverage').value = '3';
    document.getElementById('takeProfit').value = '';
    
    // 显示对话框
    dialog.style.display = 'block';
    
    // 拖动功能
    let isDragging = false;
    let currentX;
    let currentY;
    let initialX;
    let initialY;
    let xOffset = 0;
    let yOffset = 0;

    function dragStart(e) {
        if (e.type === "mousedown") {
            initialX = e.clientX - xOffset;
            initialY = e.clientY - yOffset;
        }
        
        if (e.target === header || e.target.parentNode === header) {
            isDragging = true;
        }
    }

    function dragEnd(e) {
        initialX = currentX;
        initialY = currentY;
        isDragging = false;
    }

    function drag(e) {
        if (isDragging) {
            e.preventDefault();
            currentX = e.clientX - initialX;
            currentY = e.clientY - initialY;
            xOffset = currentX;
            yOffset = currentY;

            dialogContent.style.transform = `translate(${currentX}px, ${currentY}px)`;
        }
    }

    // 添加拖动事件监听器
    header.addEventListener('mousedown', dragStart);
    document.addEventListener('mousemove', drag);
    document.addEventListener('mouseup', dragEnd);
    
    // 保存配置
    saveBtn.onclick = () => {
        const allocatedMoney = parseFloat(document.getElementById('allocatedMoney').value);
        const leverage = parseInt(document.getElementById('leverage').value);
        const takeProfit = parseFloat(document.getElementById('takeProfit').value);
        
        // 验证输入
        if (!allocatedMoney || allocatedMoney <= 0) {
            alert('请输入有效的配置市值');
            return;
        }
        if (!leverage || leverage < 1 || !Number.isInteger(leverage)) {
            alert('请输入有效的杠杆倍数（必须为正整数）');
            return;
        }
        if (!takeProfit || takeProfit <= 0) {
            alert('请输入有效的止盈目标金额');
            return;
        }
        
        // 保存数据
        saveMonitorSymbol(symbol, {
            allocated_money: allocatedMoney,
            leverage: leverage,
            take_profit: takeProfit
        });
        
        // 关闭对话框
        closeDialog();
    };
    
    // 关闭对话框函数
    function closeDialog() {
        dialog.style.display = 'none';
        dialogContent.style.transform = 'translate(-50%, -50%)';
        xOffset = 0;
        yOffset = 0;
        
        // 移除事件监听器
        header.removeEventListener('mousedown', dragStart);
        document.removeEventListener('mousemove', drag);
        document.removeEventListener('mouseup', dragEnd);
    }
    
    // 取消按钮和关闭按钮
    cancelBtn.onclick = closeDialog;
    closeBtn.onclick = closeDialog;
    
    // 点击对话框外部不关闭
    dialog.onclick = (event) => {
        if (event.target === dialog) {
            event.stopPropagation();
        }
    };
}

// 保存监控品种
async function saveMonitorSymbol(symbol, config) {
    try {
        const response = await fetch('/api/save_monitor_symbols', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Server-ID': serverInfo.serverId
            },
            body: JSON.stringify({
                accountId: accountId,
                strategy_type: 'break',  // 添加策略类型
                symbols: [{
                    symbol: symbol,
                    allocated_money: config.allocated_money,
                    leverage: config.leverage,
                    take_profit: config.take_profit
                }]
            })
        });

        // 检查响应状态
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
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

// 加载币种数据
function loadSymbolData() {
    // 筛选条件
    const filters = getFilterValues();
    const params = new URLSearchParams();
    
    // 添加账户ID和策略类型参数
    params.append('account_id', accountId);
    params.append('strategy_type', 'breakthrough');
    
    // 添加筛选参数（确保所有参数都被添加）
    const paramKeys = [
        'min_amplitude', 'max_amplitude',
        'min_position', 'max_position',
        'min_volume', 'max_volume',
        'symbol'
    ];
    
    paramKeys.forEach(key => {
        if (filters[key] !== undefined && filters[key] !== null && filters[key] !== '') {
            params.append(key, filters[key]);
        }
    });
    
    // 添加分页参数
    params.append('page', currentPage);
    params.append('per_page', perPage);
    
    console.log('筛选条件:', filters);  // 调试日志
    console.log('请求参数:', Object.fromEntries(params));  // 调试日志

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
        console.log('接收到的数据:', data);  // 调试日志
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

// 显示价格范围数据
function displayPriceRanges(result) {
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

// 格式化日期时间显示
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

// 格式化成量显示
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

// 添加滑动指示器���
document.addEventListener('DOMContentLoaded', function() {
    const tableContainer = document.querySelector('.data-table-container');
    const scrollIndicator = document.querySelector('.scroll-indicator');
    
    if (tableContainer && scrollIndicator) {
        tableContainer.addEventListener('scroll', function() {
            const maxScroll = tableContainer.scrollWidth - tableContainer.clientWidth;
            const scrollPercentage = (tableContainer.scrollLeft / maxScroll) * 100;
            scrollIndicator.style.background = 
                `linear-gradient(90deg, #1890ff ${scrollPercentage}%, transparent 100%)`;
        });
    }
});

// 其他函数实现...
// (根据需要加其他功能函数) 

function updateMonitorTable(data) {
    const tbody = document.getElementById('monitor-list');
    tbody.innerHTML = '';
    
    data.forEach(item => {
        const tr = document.createElement('tr');
        tr.className = item.is_active ? '' : 'table-secondary';
        
        // 获取方向文本
        const getDirectionText = (side) => {
            if (!side) return '-';
            switch(side.toUpperCase()) {
                case 'LONG': return '多';
                case 'SHORT': return '空';
                default: return side;
            }
        };

        // 检查状态是否为"已开仓"（不区分大小写）
        const isOpened = (status) => {
            if (!status) return false;
            return status.toUpperCase() === 'OPENED' || status.toLowerCase() === 'opened';
        };

        // 添加调试日志
        console.log('行数据:', {
            symbol: item.symbol,
            status: item.status,  // 检查原始状态字段
            sync_status: item.sync_status,  // 检查 sync_status 字段
            position_side: item.position_side
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
            <td class="text-center"><span class="badge ${getBadgeClass(item.status)}">${getStatusText(item.status)}</span></td>
            <td class="text-center">${item.is_active ? '是' : '否'}</td>
            <td class="text-center">${formatDateTime(item.sync_time)}</td>
            <td class="text-center">
                <div class="btn-group">
                    ${isOpened(item.status) ? 
                        `<button onclick="showEditDialog(${item.id})" class="edit-btn">编辑</button>` : 
                        ''
                    }
                    <button onclick="toggleMonitorActive(${item.id}, ${item.is_active})" class="monitor-btn">
                        ${item.is_active ? '禁用' : '激活'}
                    </button>
                </div>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

// 获取状态显示文本
function getStatusText(status) {
    const upperStatus = (status || '').toUpperCase();
    switch (upperStatus) {
        case 'WAITING':
            return '等待开仓';
        case 'OPENED':
            return '已开仓';
        case 'CLOSED':
            return '已关闭';
        default:
            return status || '-';
    }
}

// 获取状态标签样式
function getBadgeClass(status) {
    const upperStatus = (status || '').toUpperCase();
    switch (upperStatus) {
        case 'WAITING':
            return 'bg-warning';
        case 'OPENED':
            return 'bg-success';
        case 'CLOSED':
            return 'bg-secondary';
        default:
            return 'bg-secondary';
    }
}

// 添加分页更新函数
function updatePagination(total, totalPages, currentPage) {
    const paginationContainer = document.createElement('div');
    paginationContainer.className = 'pagination';
    
    // 计算显示的页码范围
    let startPage = Math.max(1, currentPage - 2);
    let endPage = Math.min(totalPages, startPage + 4);
    
    // 调始页，确保始终显示5个页码（如果有）
    if (endPage - startPage < 4) {
        startPage = Math.max(1, endPage - 4);
    }
    
    // 创建分页HTML
    let paginationHtml = `
        <div class="pagination-info">
            共 ${total} 记录，${totalPages} 页
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

// 添加页码切换函数
function changePage(page) {
    currentPage = page;
    loadSymbolData();
}

// 编辑监控项
function editMonitorItem(id) {
    fetch(`/api/monitor/${id}`, {
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
    
    // 获取当前记录的数据
    fetch(`/api/monitor/${monitorId}`, {
        headers: {
            'X-Server-ID': serverInfo.serverId
        }
    })
    .then(response => response.json())
    .then(result => {
        if (result.status === 'success') {
            const data = result.monitor;
            document.getElementById('editAllocatedMoney').value = data.allocated_money;
            document.getElementById('editLeverage').value = data.leverage;
            document.getElementById('editTakeProfit').value = data.take_profit;
            
            // 显示对话框
            dialog.style.display = 'block';
            
            // 保存编辑
            saveBtn.onclick = () => {
                const allocatedMoney = parseFloat(document.getElementById('editAllocatedMoney').value);
                const leverage = parseInt(document.getElementById('editLeverage').value);
                const takeProfit = parseFloat(document.getElementById('editTakeProfit').value);
                
                // 验证输入
                if (!allocatedMoney || allocatedMoney <= 0) {
                    alert('请输入有效的资金');
                    return;
                }
                if (!leverage || leverage < 1 || !Number.isInteger(leverage)) {
                    alert('请输入有效的杠杆倍数（必须为正整数）');
                    return;
                }
                if (!takeProfit || takeProfit <= 0) {
                    alert('请输入有效的止盈金额');
                    return;
                }
                
                // 保存更新
                fetch(`/api/monitor/${monitorId}`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Server-ID': serverInfo.serverId
                    },
                    body: JSON.stringify({
                        allocated_money: allocatedMoney,
                        leverage: leverage,
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
    console.log('正在加载监控列表', {
        accountId,
        serverId: serverInfo.serverId
    });

    fetch(`/api/monitor_symbols/${accountId}`, {
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

// 更新分页 - 只在筛选页面使用
function updatePagination(total) {
    // 只在筛选页面显示分页
    const filterPanel = document.getElementById('filter-content');
    if (!filterPanel || !filterPanel.classList.contains('active')) {
        return;  // 如果不是筛选页面不显示分页
    }

    const totalPages = Math.ceil(total / perPage);
    // ... 其余分页代码保持不变 ...
}

// 添加到监控列表
function addToMonitor(symbol) {
    showConfigDialog(symbol);
}

// 修改页面加载事件监听
document.addEventListener('DOMContentLoaded', function() {
    // 初始化事件监听器
    initializeEventListeners();
    
    // 如果默认显示监控列表，则加载数据（只加载一次）
    if (document.querySelector('[data-tab="monitor"]').classList.contains('active')) {
        loadMonitorList();
    }
});