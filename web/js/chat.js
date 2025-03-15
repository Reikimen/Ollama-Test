// AI聊天交互模块

// 发送文本到AI
async function sendTextToAI() {
    const userInput = document.getElementById('user-input').value.trim();
    const chatHistory = document.getElementById('chat-history');
    
    if (!userInput) return;
    
    // 添加用户消息到聊天历史
    addMessageToChat('user', userInput);
    
    // 清空输入框
    document.getElementById('user-input').value = '';
    
    // 添加AI思考中消息
    const thinkingId = addMessageToChat('ai', '思考中...');
    
    try {
        const response = await fetch(`${API_URLS.coordinator}/process_text`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ text: userInput })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // 替换思考中的消息
            updateChatMessage(thinkingId, data.ai_response);
            
            // 显示IoT命令信息（如果有）
            if (data.iot_commands && data.iot_commands.length > 0) {
                let iotInfo = '已发送以下IoT命令:<br>';
                data.iot_commands.forEach(cmd => {
                    iotInfo += `- ${cmd.device} (${cmd.location}): ${cmd.action}<br>`;
                });
                addMessageToChat('system', iotInfo);
            }
            
            // 显示表情信息
            if (data.expression) {
                addMessageToChat('system', `表情: ${data.expression}`);
            }
            
            // 处理音频播放
            if (data.audio_path) {
                // 创建完整的音频URL
                const audioServer = API_URLS.tts;
                const audioFilename = data.audio_path.split('/').pop();
                const audioUrl = `${audioServer}/audio/${audioFilename}`;
                
                // 设置音频播放器
                const audioPlayer = document.getElementById('audio-player');
                audioPlayer.src = audioUrl;
                document.getElementById('audio-player-container').style.display = 'block';
                
                // 自动播放
                audioPlayer.play().catch(err => {
                    console.error('自动播放失败:', err);
                    addMessageToChat('system', '注意: 由于浏览器政策，需要手动点击播放按钮播放音频。');
                });
            }
        } else {
            updateChatMessage(thinkingId, `处理失败: ${data.error || '未知错误'}`);
        }
    } catch (error) {
        updateChatMessage(thinkingId, `请求出错: ${error.message}`);
    }
}

// 添加消息到聊天历史
function addMessageToChat(type, text) {
    const chatHistory = document.getElementById('chat-history');
    const messageId = 'msg-' + Date.now();
    
    const messageDiv = document.createElement('div');
    messageDiv.id = messageId;
    messageDiv.className = `chat-message ${type}`;
    
    const messageP = document.createElement('p');
    
    // 系统消息可以包含HTML
    if (type === 'system') {
        messageP.innerHTML = text;
    } else {
        messageP.textContent = text;
    }
    
    messageDiv.appendChild(messageP);
    chatHistory.appendChild(messageDiv);
    
    // 滚动到底部
    chatHistory.scrollTop = chatHistory.scrollHeight;
    
    return messageId;
}

// 更新聊天消息
function updateChatMessage(messageId, text) {
    const messageElement = document.getElementById(messageId);
    if (messageElement) {
        messageElement.querySelector('p').textContent = text;
        
        // 滚动到底部
        const chatHistory = document.getElementById('chat-history');
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }
}

// 清空聊天历史
function clearChat() {
    document.getElementById('chat-history').innerHTML = '';
    document.getElementById('audio-player-container').style.display = 'none';
    document.getElementById('audio-player').src = '';
}
