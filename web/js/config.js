// API基础URL配置
const API_URLS = {
    coordinator: 'http://localhost:8080',
    stt: 'http://localhost:8000',
    tts: 'http://localhost:8001',
    iot: 'http://localhost:8002',
    ollama: 'http://localhost:11434'
};

// 服务名称映射
const SERVICE_NAMES = {
    coordinator: '协调',
    stt: '语音识别',
    tts: '语音合成',
    iot: 'IoT控制',
    ollama: 'Ollama'
};

// 设备类型动作映射
const DEVICE_ACTIONS = {
    light: [
        { value: 'on', text: '打开' },
        { value: 'off', text: '关闭' },
        { value: 'brighten', text: '调亮' },
        { value: 'dim', text: '调暗' }
    ],
    fan: [
        { value: 'on', text: '打开' },
        { value: 'off', text: '关闭' },
        { value: 'speed_up', text: '加速' },
        { value: 'speed_down', text: '减速' }
    ],
    ac: [
        { value: 'on', text: '打开' },
        { value: 'off', text: '关闭' },
        { value: 'temp_up', text: '升温' },
        { value: 'temp_down', text: '降温' }
    ],
    curtain: [
        { value: 'on', text: '打开' },
        { value: 'off', text: '关闭' }
    ]
};
