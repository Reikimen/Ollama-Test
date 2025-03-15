// 语音合成模块

// 合成语音
async function synthesizeSpeech() {
    const text = document.getElementById('tts-text').value.trim();
    const voice = document.getElementById('tts-voice').value;
    const outputArea = document.getElementById('tts-output');
    
    if (!text) {
        outputArea.innerHTML = '<div class="console-output error">请输入要合成的文本</div>';
        return;
    }
    
    outputArea.innerHTML = '<div class="console-output">正在合成语音...</div>';
    
    try {
        const response = await fetch(`${API_URLS.tts}/synthesize`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                text,
                voice,
                format: 'mp3'
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // 创建完整的音频URL
            const audioServer = API_URLS.tts;
            const audioFilename = data.audio_path.split('/').pop();
            const audioUrl = `${audioServer}/audio/${audioFilename}`;
            
            outputArea.innerHTML = `
                <div class="console-output success">
                    语音合成成功！<br>
                    语音: ${data.voice}<br>
                    格式: ${data.format}<br>
                    <audio controls src="${audioUrl}" style="width:100%; margin-top:10px;"></audio>
                </div>`;
        } else {
            outputArea.innerHTML = `<div class="console-output error">语音合成失败: ${data.error || '未知错误'}</div>`;
        }
    } catch (error) {
        outputArea.innerHTML = `<div class="console-output error">请求出错: ${error.message}</div>`;
    }
}

// 获取可用语音列表
async function getAvailableVoices() {
    const outputArea = document.getElementById('tts-output');
    outputArea.innerHTML = '<div class="console-output">正在获取可用语音列表...</div>';
    
    try {
        const response = await fetch(`${API_URLS.tts}/voices`);
        const data = await response.json();
        
        if (response.ok && data.voices) {
            let output = '<div class="console-output"><strong>可用语音列表:</strong><br>';
            
            // 过滤中文语音
            const chineseVoices = data.voices.filter(voice => voice.Name.startsWith('zh-'));
            
            if (chineseVoices.length > 0) {
                chineseVoices.forEach((voice, index) => {
                    output += `${index + 1}. <span class="success">${voice.Name}</span> - ${voice.Gender || '未知性别'}<br>`;
                });
            } else {
                output += '没有找到中文语音<br>';
                
                // 显示前10个语音
                data.voices.slice(0, 10).forEach((voice, index) => {
                    output += `${index + 1}. ${voice.Name} - ${voice.Gender || '未知性别'}<br>`;
                });
            }
            
            output += '</div>';
            outputArea.innerHTML = output;
        } else {
            outputArea.innerHTML = `<div class="console-output error">获取语音列表失败: ${data.error || '未知错误'}</div>`;
        }
    } catch (error) {
        outputArea.innerHTML = `<div class="console-output error">请求出错: ${error.message}</div>`;
    }
}
