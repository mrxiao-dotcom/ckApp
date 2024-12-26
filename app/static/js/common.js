// 全局服务器信息
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