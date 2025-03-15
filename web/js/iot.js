// IoT设备控制模块

// 更新动作下拉菜单
function updateActionDropdown() {
    const deviceType = document.getElementById('device-type').value;
    const actionSelect = document.getElementById('device-action');
    
    // 清空现有选项
    actionSelect.innerHTML = '';
    
    // 根据设备类型添加选项
    const options = DEVICE_ACTIONS[deviceType] || [];
    
    // 添加选项到下拉菜单
    options.forEach(opt => {
        const option = document.createElement('option');
        option.value = opt.value;
        option.textContent = opt.text;
        actionSelect.appendChild(option);
    });
}

// 发送IoT控制命令
async function sendIoTCommand() {
    const device = document.getElementById('device-type').value;
    const action = document.getElementById('device-action').value;
    const location = document.getElementById('device-location').value;
    const outputArea = document.getElementById('iot-output');
    
    outputArea.innerHTML = `<div class="console-output">正在发送命令: ${device} (${location}) - ${action}...</div>`;
    
    try {
        const response = await fetch(`${API_URLS.iot}/control`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                commands: [
                    { device, action, location }
                ]
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            outputArea.innerHTML = `<div class="console-output">命令发送成功！<br>结果: ${JSON.stringify(data, null, 2)}</div>`;
        } else {
            outputArea.innerHTML = `<div class="console-output error">命令发送失败: ${data.error || '未知错误'}</div>`;
        }
    } catch (error) {
        outputArea.innerHTML = `<div class="console-output error">请求出错: ${error.message}</div>`;
    }
}

// 获取所有设备状态
async function getAllDevices() {
    const outputArea = document.getElementById('iot-output');
    outputArea.innerHTML = '<div class="console-output">正在获取设备状态...</div>';
    
    try {
        const response = await fetch(`${API_URLS.iot}/devices`);
        const data = await response.json();
        
        if (response.ok) {
            outputArea.innerHTML = `<div class="console-output">设备状态:<br><pre>${JSON.stringify(data, null, 2)}</pre></div>`;
        } else {
            outputArea.innerHTML = `<div class="console-output error">获取设备状态失败: ${data.error || '未知错误'}</div>`;
        }
    } catch (error) {
        outputArea.innerHTML = `<div class="console-output error">请求出错: ${error.message}</div>`;
    }
}
