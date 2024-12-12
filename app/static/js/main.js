let currentAccount = null;
const accounts = JSON.parse(localStorage.getItem('accounts') || '[]');
let availableContracts = [];
let selectedContracts = new Set();
let selectedSearchResult = null;

// 初始化账户标签页
function initAccountTabs() {
    const tabsContainer = document.getElementById('account-tabs');
    if (!accounts || accounts.length === 0) {
        tabsContainer.innerHTML = '<div class="no-data">暂无账户数据</div>';
        return;
    }

    accounts.forEach((account, index) => {
        const tab = document.createElement('button');
        tab.className = 'account-tab';
        tab.textContent = `${account.acct_name || ''} (${account.acct_id})`;
        tab.onclick = () => switchAccount(account);
        if (index === 0) {
            tab.classList.add('active');
            currentAccount = account;
        }
        tabsContainer.appendChild(tab);
    });
    
    if (accounts.length > 0) {
        updateAccountInfo(accounts[0]);
        loadPositions(accounts[0]);
    }
}

// 切换账户
function switchAccount(account) {
    currentAccount = account;
    document.querySelectorAll('.account-tab').forEach(tab => {
        tab.classList.remove('active');
        if (tab.textContent.includes(account.acct_id)) {
            tab.classList.add('active');
        }
    });
    updateAccountInfo(account);
    loadPositions(account);
}

// 更新账户信息显示
function updateAccountInfo(account) {
    const accountDetails = document.getElementById('account-details');
    accountDetails.innerHTML = `
        <div class="account-details">
            <div class="detail-item">
                <div class="label">账户ID</div>
                <div class="value">${account.acct_id}</div>
            </div>
            <div class="detail-item">
                <div class="label">账户名称</div>
                <div class="value">${account.acct_name}</div>
            </div>
            <div class="detail-item">
                <div class="label">邮箱</div>
                <div class="value">${account.email}</div>
            </div>
            <div class="detail-item">
                <div class="label">状态</div>
                <div class="value">
                    <span class="status-badge ${account.status === 1 ? 'status-active' : 'status-inactive'}">
                        ${account.status === 1 ? '正常' : '禁用'}
                    </span>
                </div>
            </div>
        </div>
        ${account.stg_comb_product_gateio && account.stg_comb_product_gateio.length > 0 ? 
            account.stg_comb_product_gateio.map(product => `
                <div class="product-item">
                    <div class="product-header">
                        <div class="product-name">${product.name || '未命名'}</div>
                        <div class="product-status">
                            <span class="status-badge ${product.status === '1' ? 'status-active' : 'status-inactive'}">
                                ${product.status === '1' ? '正常' : '禁用'}
                            </span>
                        </div>
                    </div>
                    <div class="product-info">
                        <div class="product-config">
                            <div class="config-row">
                                <span class="config-label">组合名称:</span>
                                <span class="config-value">${product.product_list || '无'}</span>
                            </div>
                            <div class="config-row">
                                <span class="config-label">总资金:</span>
                                <span class="config-value">${formatMoney(product.money)}</span>
                            </div>
                            <div class="config-row">
                                <span class="config-label">仓位:</span>
                                <span class="config-value">${formatPercentage(product.discount)}</span>
                            </div>
                        </div>
                        <div class="symbols-grid">
                            ${product.comb_name ? 
                                product.comb_name.split('#').map(symbol => `
                                    <div class="symbol-tag">${symbol}</div>
                                `).join('') : ''
                            }
                        </div>
                    </div>
                </div>
            `).join('') : ''
        }
    `;
    
    document.getElementById('current-account').textContent = 
        `当前账户: ${account.acct_name || account.acct_id}`;
}

// 添加格式化函数
function formatMoney(value) {
    if (value == null) return '0.00';
    return new Intl.NumberFormat('zh-CN', {
        style: 'currency',
        currency: 'CNY'
    }).format(value);
}

function formatPercentage(value) {
    if (value == null) return '0%';
    return new Intl.NumberFormat('zh-CN', {
        style: 'percent',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(value);
}

// 加载持仓列表
async function loadPositions(account) {
    try {
        console.log('Loading positions for account:', account.acct_id);
        const headers = {
            'Authorization': `Bearer ${localStorage.getItem('token')}`,
            'X-Server-ID': localStorage.getItem('server_id')
        };
        const response = await fetch(`/api/positions?acct_id=${account.acct_id}`, {
            headers: headers
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || '服务器错误');
        }
        
        const positions = await response.json();
        console.log('Loaded positions:', positions);
        
        const positionsList = document.getElementById('positions-list');
        if (!positions || positions.length === 0) {
            positionsList.innerHTML = '<div class="no-data">暂无持仓数据</div>';
            return;
        }

        // 获取第一个持仓的资金和仓位信息（因为所有持仓共享相同的资金和仓位）
        const money = positions[0].money;
        const discount = positions[0].discount;
        
        // 显示持仓信息
        positionsList.innerHTML = `
            <div class="position-config">
                <div class="config-row">
                    <span class="config-label">总资金:</span>
                    <span class="config-value">${formatMoney(money)}</span>
                </div>
                <div class="config-row">
                    <span class="config-label">仓位:</span>
                    <span class="config-value">${formatPercentage(discount)}</span>
                </div>
            </div>
            <div class="positions-grid">
                ${positions.map(position => `
                    <div class="position-item">
                        <span class="position-symbol">${position.symbol}</span>
                    </div>
                `).join('')}
            </div>
        `;
    } catch (error) {
        console.error('Error loading positions:', error);
        document.getElementById('positions-list').innerHTML = `
            <div class="error-message">
                加载持仓数据失败: ${error.message}
            </div>
        `;
    }
}

// 显示配置模态框
async function showConfigModal() {
    if (!currentAccount) return;
    
    try {
        // 加载组合列表
        const response = await fetch('/api/strategies', {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('token')}`,
                'X-Server-ID': localStorage.getItem('server_id')
            }
        });
        
        const strategies = await response.json();
        
        // 填充组合选择下拉框
        const select = document.getElementById('strategy-select');
        select.innerHTML = '<option value="">请选择组合</option>' +
            strategies.map(s => `
                <option value="${s.product_comb}">${s.display_name}</option>
            `).join('');
            
        // 加载当前账户的组合配置
        const configResponse = await fetch(`/api/product_config?acct_id=${currentAccount.acct_id}`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('token')}`,
                'X-Server-ID': localStorage.getItem('server_id')
            }
        });
        
        const config = await configResponse.json();
        
        // 设置当前值
        if (config.product_list) {
            select.value = config.product_list;
            document.getElementById('config-money').value = config.money;
            document.getElementById('config-discount').value = config.discount;
            selectedContracts = new Set(config.symbols);
            updateSelectedContracts();
        }
        
        document.getElementById('config-modal').style.display = 'block';
        // 初始化拖动功能
        makeDraggable('config-modal');
    } catch (error) {
        console.error('Error loading config:', error);
        alert('加载配置失败: ' + error.message);
    }
}

// 处理组合选择变化
document.getElementById('strategy-select').addEventListener('change', async function() {
    const productComb = this.value;
    if (!productComb) {
        document.getElementById('comb-name').value = '';
        return;
    }
    
    try {
        const response = await fetch(`/api/strategy/${productComb}`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('token')}`,
                'X-Server-ID': localStorage.getItem('server_id')
            }
        });
        
        const strategy = await response.json();
        document.getElementById('comb-name').value = strategy.comb_name;
        selectedContracts = new Set(strategy.symbols);
        updateSelectedContracts();
    } catch (error) {
        console.error('Error loading strategy:', error);
        alert('加载策略失败: ' + error.message);
    }
});

// 处理合约搜索
document.getElementById('contract-search').addEventListener('input', async function() {
    const searchText = this.value.trim();
    selectedSearchResult = null;  // 清除选中状态
    
    if (!searchText) {
        document.getElementById('search-results').style.display = 'none';
        return;
    }
    
    try {
        // 每次搜索时重新获取可用合约列表
        if (!availableContracts.length) {
            const serverId = localStorage.getItem('server_id');
            if (!serverId) {
                throw new Error('未选择服务器');
            }
            
            const response = await fetch('/api/available_contracts', {
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('token')}`,
                    'X-Server-ID': serverId
                }
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || '加载合约列表失败');
            }
            
            availableContracts = await response.json();
        }
        
        // 搜索匹配的合约
        const matches = availableContracts.filter(c => 
            c.symbol.toLowerCase().includes(searchText.toLowerCase()) ||
            (c.name && c.name.toLowerCase().includes(searchText.toLowerCase()))
        );
        
        const resultsDiv = document.getElementById('search-results');
        if (matches.length === 0) {
            resultsDiv.style.display = 'none';
            return;
        }
        
        resultsDiv.innerHTML = matches.map(c => `
            <div class="search-result-item" onclick="selectSearchResult('${c.symbol}')">
                <span>${c.symbol}${c.name ? ` - ${c.name}` : ''}</span>
            </div>
        `).join('');
        resultsDiv.style.display = 'block';
    } catch (error) {
        console.error('Error searching contracts:', error);
        document.getElementById('search-results').innerHTML = `
            <div class="search-result-item error">
                ${error.message}
            </div>
        `;
        document.getElementById('search-results').style.display = 'block';
    }
});

// 选择搜索结果
function selectSearchResult(symbol) {
    selectedSearchResult = symbol;
    // 高亮显示选中项
    document.querySelectorAll('.search-result-item').forEach(item => {
        if (item.textContent.includes(symbol)) {
            item.classList.add('selected');
        } else {
            item.classList.remove('selected');
        }
    });
    // 可选：将选中的合约显示在搜索框中
    document.getElementById('contract-search').value = symbol;
}

// 添加搜索到的合约
function addSearchedContract() {
    if (!selectedSearchResult) {
        alert('请先选择要添加的合约');
        return;
    }
    
    selectedContracts.add(selectedSearchResult);
    updateSelectedContracts();
    
    // 清空搜索
    document.getElementById('contract-search').value = '';
    document.getElementById('search-results').style.display = 'none';
    selectedSearchResult = null;
}

// 移除合约
function removeContract(symbol) {
    selectedContracts.delete(symbol);
    updateSelectedContracts();
}

// 更新已选合约显示
function updateSelectedContracts() {
    const container = document.getElementById('selected-contracts');
    container.innerHTML = Array.from(selectedContracts).map(symbol => `
        <div class="contract-tag">
            ${symbol}
            <span class="remove-contract" onclick="removeContract('${symbol}')">&times;</span>
        </div>
    `).join('');
}

// 保存配置
async function saveConfig() {
    if (!currentAccount) return;
    
    const productComb = document.getElementById('strategy-select').value;
    if (!productComb) {
        alert('请选择组合');
        return;
    }
    
    const money = parseFloat(document.getElementById('config-money').value);
    const discount = parseFloat(document.getElementById('config-discount').value);
    
    if (isNaN(money) || money <= 0) {
        alert('请输入有效的资金金额');
        return;
    }
    
    if (isNaN(discount) || discount < 0 || discount > 1) {
        alert('请输入有效的仓位比例（0-1之间）');
        return;
    }
    
    try {
        const serverId = localStorage.getItem('server_id');
        if (!serverId) {
            throw new Error('未选择服务器');
        }
        
        const response = await fetch('/api/save_config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`,
                'X-Server-ID': serverId
            },
            body: JSON.stringify({
                acct_id: currentAccount.acct_id,
                product_list: productComb,
                money: money,
                discount: discount,
                symbols: Array.from(selectedContracts)
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || '保存失败');
        }
        
        // 保存成功后刷新页面数据
        closeConfigModal();
        await loadPositions(currentAccount);
        // 刷新账户信息
        await updateAccountInfo(currentAccount);
    } catch (error) {
        console.error('Error saving config:', error);
        alert(error.message);
    }
}

// 关闭配置模态框
function closeConfigModal() {
    const modal = document.getElementById('config-modal');
    const content = modal.querySelector('.modal-content');
    content.style.transform = 'translate(-50%, -50%)';  // 重置位置
    modal.style.display = 'none';
}

// 退出登录
function logout() {
    localStorage.removeItem('token');
    localStorage.removeItem('accounts');
    window.location.href = '/auth/logout';
}

// 页面加载完成后执行
document.addEventListener('DOMContentLoaded', () => {
    initAccountTabs();
});

// 显示新建策略模态框
async function showNewStrategyModal() {
    try {
        // 加载可用合约列表
        const response = await fetch('/api/available_contracts', {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('token')}`,
                'X-Server-ID': localStorage.getItem('server_id')
            }
        });
        
        if (!response.ok) {
            throw new Error('加载合约列表失败');
        }
        
        availableContracts = await response.json();
        selectedContracts.clear();  // 清空已选合约
        updateNewSelectedContracts();  // 更新显示
        
        document.getElementById('new-strategy-modal').style.display = 'block';
        // 初始化拖动功能
        makeDraggable('new-strategy-modal');
    } catch (error) {
        console.error('Error:', error);
        alert(error.message);
    }
}

// 处理合约搜索
document.getElementById('new-contract-search').addEventListener('input', function() {
    const searchText = this.value.trim();
    if (!searchText) {
        document.getElementById('new-search-results').style.display = 'none';
        return;
    }
    
    // 处理直接输入的合约代码
    if (searchText.includes(',')) {
        const symbols = searchText.split(',')
            .map(s => s.trim().toUpperCase())
            .filter(s => s);
        symbols.forEach(addNewContract);
        this.value = '';
        return;
    }
    
    // 搜索匹配的合约
    const matches = availableContracts.filter(c => 
        c.symbol.toLowerCase().includes(searchText.toLowerCase()) ||
        c.name.toLowerCase().includes(searchText.toLowerCase())
    );
    
    const resultsDiv = document.getElementById('new-search-results');
    if (matches.length === 0) {
        resultsDiv.style.display = 'none';
        return;
    }
    
    resultsDiv.innerHTML = matches.map(c => `
        <div class="search-result-item" onclick="addNewContract('${c.symbol}')">
            ${c.symbol} - ${c.name}
        </div>
    `).join('');
    resultsDiv.style.display = 'block';
});

// 添加合约到新策略
function addNewContract(symbol) {
    selectedContracts.add(symbol.toUpperCase());
    updateNewSelectedContracts();
    document.getElementById('new-contract-search').value = '';
    document.getElementById('new-search-results').style.display = 'none';
}

// 从新策略中移除合约
function removeNewContract(symbol) {
    selectedContracts.delete(symbol);
    updateNewSelectedContracts();
}

// 更新新策略的已选合约显示
function updateNewSelectedContracts() {
    const container = document.getElementById('new-selected-contracts');
    container.innerHTML = Array.from(selectedContracts).map(symbol => `
        <div class="contract-tag">
            ${symbol}
            <span class="remove-contract" onclick="removeNewContract('${symbol}')">&times;</span>
        </div>
    `).join('');
}

// 创建新策略
async function createNewStrategy() {
    const productComb = document.getElementById('new-product-comb').value.trim();
    const combName = document.getElementById('new-comb-name').value.trim();
    
    if (!productComb || !combName) {
        alert('请填写组合标识和名称');
        return;
    }
    
    if (selectedContracts.size === 0) {
        alert('请至少添加一个合约');
        return;
    }
    
    try {
        const response = await fetch('/api/create_strategy', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('token')}`,
                'X-Server-ID': localStorage.getItem('server_id')
            },
            body: JSON.stringify({
                product_comb: productComb,
                comb_name: combName,
                symbols: Array.from(selectedContracts)
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || '创建失败');
        }
        
        closeNewStrategyModal();
        showConfigModal();  // 刷新配置模态框
    } catch (error) {
        console.error('Error creating strategy:', error);
        alert(error.message);
    }
}

// 关闭新建策略模态框
function closeNewStrategyModal() {
    const modal = document.getElementById('new-strategy-modal');
    const content = modal.querySelector('.modal-content');
    content.style.transform = 'translate(-50%, -50%)';  // 重置位置
    modal.style.display = 'none';
    // 清空表单
    document.getElementById('new-product-comb').value = '';
    document.getElementById('new-comb-name').value = '';
    document.getElementById('new-contract-search').value = '';
    selectedContracts.clear();
    updateNewSelectedContracts();
}

// 添加拖动功能
function makeDraggable(modalId) {
    const modal = document.getElementById(modalId);
    const content = modal.querySelector('.modal-content');
    const header = content.querySelector('.modal-header');
    
    let isDragging = false;
    let currentX;
    let currentY;
    let initialX;
    let initialY;
    let xOffset = 0;
    let yOffset = 0;

    header.addEventListener('mousedown', dragStart);
    document.addEventListener('mousemove', drag);
    document.addEventListener('mouseup', dragEnd);

    function dragStart(e) {
        initialX = e.clientX - xOffset;
        initialY = e.clientY - yOffset;

        if (e.target === header) {
            isDragging = true;
        }
    }

    function drag(e) {
        if (isDragging) {
            e.preventDefault();
            
            currentX = e.clientX - initialX;
            currentY = e.clientY - initialY;

            xOffset = currentX;
            yOffset = currentY;

            setTranslate(currentX, currentY, content);
        }
    }

    function dragEnd(e) {
        initialX = currentX;
        initialY = currentY;
        isDragging = false;
    }

    function setTranslate(xPos, yPos, el) {
        // 获取模态框的尺寸和视口尺寸
        const modalRect = el.getBoundingClientRect();
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;
        
        // 确保模态框不会移出视口
        xPos = Math.min(Math.max(xPos, -modalRect.width/2), viewportWidth - modalRect.width/2);
        yPos = Math.min(Math.max(yPos, -modalRect.height/2), viewportHeight - modalRect.height/2);
        
        el.style.transform = `translate(${xPos}px, ${yPos}px)`;
    }
} 