// 服务状态检查模块

// 检查服务状态
async function checkServiceStatus(service) {
    const outputArea = document.getElementById('status-output');
    const currentContent = outputArea.innerHTML;
    const serviceName = SERVICE_NAMES[service] || service;
    
    outputArea.innerHTML = `${currentContent}<div>正在检查${serviceName}服务状态...</div>`;
    
    try {
        const response = await fetch(API_URLS[service]);
        const data = await response.json();
        
        if (response.ok) {
            outputArea.innerHTML = `${outputArea.innerHTML.replace(`<div>正在检查${serviceName}服务状态...</div>`, '')}<div class="console-output">${serviceName}服务: <span class="success">在线</span><br>响应: ${JSON.stringify(data)}</div>`;
        } else {
            outputArea.innerHTML = `${outputArea.innerHTML.replace(`<div>正在检查${serviceName}服务状态...</div>`, '')}<div class="console-output">${serviceName}服务: <span class="error">错误</span><br>响应: ${JSON.stringify(data)}</div>`;
        }
    } catch (error) {
        outputArea.innerHTML = `${outputArea.innerHTML.replace(`<div>正在检查${serviceName}服务状态...</div>`, '')}<div class="console-output">${serviceName}服务: <span class="error">离线</span><br>错误: ${error.message}</div>`;
    }
}

// 检查所有服务状态
async function checkAllServices() {
    const outputArea = document.getElementById('status-output');
    outputArea.innerHTML = '<div class="console-output">正在检查所有服务...</div>';
    
    const services = ['coordinator', 'stt', 'tts', 'iot', 'ollama'];
    
    for (const service of services) {
        await checkServiceStatus(service);
    }
}
