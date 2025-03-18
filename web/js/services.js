// Service status check module

// Check service status
async function checkServiceStatus(service) {
    const outputArea = document.getElementById('status-output');
    const currentContent = outputArea.innerHTML;
    const serviceName = SERVICE_NAMES[service] || service;
    
    outputArea.innerHTML = `${currentContent}<div>Checking ${serviceName} service status...</div>`;
    
    try {
        const response = await fetch(API_URLS[service]);
        const data = await response.json();
        
        if (response.ok) {
            outputArea.innerHTML = `${outputArea.innerHTML.replace(`<div>Checking ${serviceName} service status...</div>`, '')}<div class="console-output">${serviceName} service: <span class="success">Online</span><br>Response: ${JSON.stringify(data)}</div>`;
        } else {
            outputArea.innerHTML = `${outputArea.innerHTML.replace(`<div>Checking ${serviceName} service status...</div>`, '')}<div class="console-output">${serviceName} service: <span class="error">Error</span><br>Response: ${JSON.stringify(data)}</div>`;
        }
    } catch (error) {
        outputArea.innerHTML = `${outputArea.innerHTML.replace(`<div>Checking ${serviceName} service status...</div>`, '')}<div class="console-output">${serviceName} service: <span class="error">Offline</span><br>Error: ${error.message}</div>`;
    }
}

// Check all services status
async function checkAllServices() {
    const outputArea = document.getElementById('status-output');
    outputArea.innerHTML = '<div class="console-output">Checking all services...</div>';
    
    const services = ['coordinator', 'stt', 'tts', 'iot', 'ollama'];
    
    for (const service of services) {
        await checkServiceStatus(service);
    }
}