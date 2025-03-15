// Ollama模型管理模块

// 检查Ollama可用模型
async function checkOllamaModels() {
    const outputArea = document.getElementById('models-output');
    outputArea.innerHTML = '正在获取模型列表...';
    
    try {
        const response = await fetch(`${API_URLS.ollama}/api/tags`);
        const data = await response.json();
        
        if (response.ok) {
            let output = '<div class="console-output"><strong>可用模型：</strong><br>';
            
            if (data.models && data.models.length > 0) {
                data.models.forEach((model, index) => {
                    output += `${index + 1}. <span class="success">${model.name}</span>`;
                    if (model.size) {
                        const sizeMB = (model.size / (1024 * 1024)).toFixed(2);
                        output += ` (${sizeMB} MB)`;
                    }
                    output += '<br>';
                });
            } else {
                output += '<span class="error">没有找到模型</span><br>';
            }
            
            output += '</div>';
            outputArea.innerHTML = output;
        } else {
            outputArea.innerHTML = `<div class="console-output error">获取模型失败: ${data.error || '未知错误'}</div>`;
        }
    } catch (error) {
        outputArea.innerHTML = `<div class="console-output error">请求出错: ${error.message}</div>`;
    }
}

// 拉取Ollama模型
async function pullOllamaModel() {
    const modelName = document.getElementById('model-name').value.trim();
    const outputArea = document.getElementById('models-output');
    
    if (!modelName) {
        outputArea.innerHTML = '<div class="console-output error">请输入模型名称</div>';
        return;
    }
    
    outputArea.innerHTML = `<div class="console-output">正在拉取模型 <strong>${modelName}</strong>...<br>这可能需要几分钟时间，请耐心等待...</div>`;
    
    try {
        const response = await fetch(`${API_URLS.ollama}/api/pull`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ name: modelName })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            outputArea.innerHTML = `<div class="console-output success">模型 <strong>${modelName}</strong> 已成功拉取！</div>`;
            // 刷新模型列表
            setTimeout(checkOllamaModels, 1000);
        } else {
            outputArea.innerHTML = `<div class="console-output error">拉取模型失败: ${data.error || '未知错误'}</div>`;
        }
    } catch (error) {
        outputArea.innerHTML = `<div class="console-output error">请求出错: ${error.message}</div>`;
    }
}
