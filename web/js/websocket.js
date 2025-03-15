// WebSocket通信模块

// WebSocket连接
let wsConnection = null;

// WebSocket连接
function connectWebSocket() {
    if (wsConnection) {
        // 已经连接
        return;
    }
    
    const wsUrl = `ws://${window.location.hostname}:8080/ws`;
    wsConnection = new WebSocket(wsUrl);
    
    const statusElement = document.getElementById('ws-status');
    statusElement.textContent = '正在连接...';
    statusElement.className = 'ms-3 badge bg-warning';
    
    const outputArea = document.getElementById('ws-output');
    
    // 连接建立时
    wsConnection.onopen = function() {
        statusElement.textContent = '已连接';
        statusElement.className = 'ms-3 badge bg-success';
        
        document.getElementById('ws-connect').disabled = true;
        document.getElementById('ws-disconnect').disabled = false;
        document.getElementById('ws-send').disabled = false;
        
        outputArea.innerHTML += '<div class="console-output success">WebSocket连接已建立</div>';
    };
    
    // 收到消息时
    wsConnection.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            outputArea.innerHTML += `<div class="console-output">收到消息:<br><pre>${JSON.stringify(data, null, 2)}</pre></div>`;
            
            // 如果有音频路径，显示音频播放器
            if (data.audio_path) {
                const audioServer = API_URLS.tts;
                const audioFilename = data.audio_path.split('/').pop();
                const audioUrl = `${audioServer}/audio/${audioFilename}`;
                
                const audioElement = document.createElement('audio');
                audioElement.controls = true;
                audioElement.src = audioUrl;
                audioElement.style.width = '100%';
                audioElement.style.marginTop = '10px';
                
                const audioContainer = document.createElement('div');
                audioContainer.className = 'console-output';
                audioContainer.innerHTML = '<strong>收到音频响应:</strong><br>';
                audioContainer.appendChild(audioElement);
                
                outputArea.appendChild(audioContainer);
                
                // 自动播放
                audioElement.play().catch(() => {});
            }
        } catch (e) {
            outputArea.innerHTML += `<div class="console-output">收到消息: ${event.data}</div>`;
        }
        
        // 滚动到底部
        outputArea.scrollTop = outputArea.scrollHeight;
    };
    
    // 连接关闭时
    wsConnection.onclose = function() {
        statusElement.textContent = '已断开';
        statusElement.className = 'ms-3 badge bg-secondary';
        
        document.getElementById('ws-connect').disabled = false;
        document.getElementById('ws-disconnect').disabled = true;
        document.getElementById('ws-send').disabled = true;
        
        outputArea.innerHTML += '<div class="console-output">WebSocket连接已关闭</div>';
        wsConnection = null;
    };
    
    // 连接错误时
    wsConnection.onerror = function(error) {
        statusElement.textContent = '连接错误';
        statusElement.className = 'ms-3 badge bg-danger';
        
        outputArea.innerHTML += `<div class="console-output error">WebSocket错误: ${error.message || '未知错误'}</div>`;
    };
}

// 断开WebSocket连接
function disconnectWebSocket() {
    if (wsConnection) {
        wsConnection.close();
        // onclose事件会处理UI更新
    }
}

// 发送WebSocket消息
function sendWebSocketMessage() {
    if (!wsConnection || wsConnection.readyState !== WebSocket.OPEN) {
        document.getElementById('ws-output').innerHTML += '<div class="console-output error">WebSocket未连接</div>';
        return;
    }
    
    const message = document.getElementById('ws-message').value.trim();
    
    if (!message) {
        return;
    }
    
    // 创建消息对象
    const messageObj = {
        type: 'text',
        text: message
    };
    
    // 发送消息
    wsConnection.send(JSON.stringify(messageObj));
    
    // 显示已发送的消息
    document.getElementById('ws-output').innerHTML += `<div class="console-output">发送消息: ${message}</div>`;
    
    // 清空输入框
    document.getElementById('ws-message').value = '';
}
