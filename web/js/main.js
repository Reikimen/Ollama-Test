// 主程序入口文件

// DOM加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    // Ollama模型管理
    document.getElementById('check-models').addEventListener('click', checkOllamaModels);
    document.getElementById('pull-model').addEventListener('click', pullOllamaModel);
    
    // 服务状态检查
    document.getElementById('check-coordinator').addEventListener('click', () => checkServiceStatus('coordinator'));
    document.getElementById('check-stt').addEventListener('click', () => checkServiceStatus('stt'));
    document.getElementById('check-tts').addEventListener('click', () => checkServiceStatus('tts'));
    document.getElementById('check-iot').addEventListener('click', () => checkServiceStatus('iot'));
    
    // AI交互
    document.getElementById('send-text').addEventListener('click', sendTextToAI);
    document.getElementById('clear-chat').addEventListener('click', clearChat);
    document.getElementById('user-input').addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendTextToAI();
        }
    });
    
    // IoT设备控制
    document.getElementById('send-command').addEventListener('click', sendIoTCommand);
    document.getElementById('get-devices').addEventListener('click', getAllDevices);
    
    // 设备类型切换时更新动作下拉菜单
    document.getElementById('device-type').addEventListener('change', updateActionDropdown);
    
    // 语音合成
    document.getElementById('synthesize-speech').addEventListener('click', synthesizeSpeech);
    document.getElementById('get-voices').addEventListener('click', getAvailableVoices);
    
    // WebSocket交互
    document.getElementById('ws-connect').addEventListener('click', connectWebSocket);
    document.getElementById('ws-disconnect').addEventListener('click', disconnectWebSocket);
    document.getElementById('ws-send').addEventListener('click', sendWebSocketMessage);
    document.getElementById('ws-message').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            sendWebSocketMessage();
        }
    });
    
    // 初始化
    updateActionDropdown();
    
    // 显示欢迎消息
    console.log('AI语音助手控制面板已加载完成');
});
