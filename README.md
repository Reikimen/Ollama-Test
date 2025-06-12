# AI Smart Home Assistant with Edge Computing

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-supported-blue.svg)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/python-3.10+-green.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-ESP32-red.svg)](https://espressif.com/)

> **Edge Computing and Large Language Model (LLMs) Powered Semantic Frameworks for Connected Smart Homes**

This project demonstrates a novel smart home framework that leverages Large Language Models (LLMs) and edge computing to enable understanding and processing of user semantics, significantly outperforming traditional rule-based methods in terms of intent extraction performance and user satisfaction.

## 🏗️ System Architecture

The system consists of **5 microservices** running in Docker containers, designed for collaboration between low-power devices (ESP32) and PC-side Docker containers:

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   ESP32 Device  │    │   Edge Computer   │    │  Web Interface  │
│                 │    │   (Docker Host)   │    │                 │
│ • Audio I/O     │◄──►│ • Ollama (LLM)    │◄──►│ • User Mode     │
│ • LCD Display   │    │ • STT Service     │    │ • Developer     │
│ • IoT Control   │    │ • TTS Service     │    │ • Real-time     │
│ • Sensors       │    │ • IoT Controller  │    │   Monitoring    │
└─────────────────┘    │ • Coordinator     │    └─────────────────┘
                       └──────────────────┘
```

### Core Services

1. **🧠 Ollama Service** - LLM processing for natural language understanding
2. **🎤 STT Service** - Speech-to-Text using OpenAI Whisper
3. **🔊 TTS Service** - Text-to-Speech using Microsoft Edge TTS
4. **🏠 IoT Controller** - Smart device management and automation
5. **🎯 Coordinator** - Central orchestration and semantic processing

## ✨ Key Features

### 🚀 Advanced AI Capabilities
- **Intent-based Interaction**: Move beyond command-based to natural conversation
- **Semantic Understanding**: Advanced LLM-powered context awareness
- **Multi-language Support**: English and Chinese voice commands
- **Scene Intelligence**: Automated environment optimization

### 🏡 Comprehensive Smart Home Control
- **Multi-room Support**: Living room, bedroom, kitchen, study, bathroom
- **Device Categories**: Lighting, HVAC, fans, curtains, sensors
- **Environmental Monitoring**: Temperature, humidity, CO2, VOC, light levels
- **Real-time Updates**: WebSocket-based live status monitoring

### 🖥️ Dual Interface Modes
- **👤 User Mode**: Intuitive interface for daily home control
- **⚙️ Developer Mode**: Advanced testing and debugging tools

### 🔧 Hardware Integration
- **ESP32 Ecosystem**: Audio processing, display control, sensor integration
- **Scalable Architecture**: Easy addition of new devices and rooms
- **Edge Processing**: Reduced latency and enhanced privacy

## 🛠️ Technology Stack

### Backend Services
- **Python 3.10+** with FastAPI framework
- **Docker & Docker Compose** for containerization
- **WebSocket** for real-time communication
- **RESTful APIs** for service integration

### AI & Voice Processing
- **Ollama** - Local LLM deployment (Llama 3)
- **OpenAI Whisper** - Speech recognition
- **Microsoft Edge TTS** - Speech synthesis

### Hardware Platform
- **ESP32** microcontrollers
- **I2S Audio** for high-quality voice processing
- **LCD Displays** for visual feedback
- **Environmental Sensors** (CO2, VOC, temperature, humidity)

### Frontend
- **HTML5/CSS3/JavaScript** with Bootstrap 5
- **Real-time WebSocket** connections
- **Responsive Design** for mobile and desktop

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- 8GB+ RAM recommended
- Network access for initial model downloads

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/ai-smart-home-assistant.git
cd ai-smart-home-assistant
```

### 2. Start the System
```bash
# Build and start all services
docker-compose up --build

# Or run in background
docker-compose up -d --build
```

### 3. Access the Interface
- **User Interface**: http://localhost:1145
- **Developer Console**: http://localhost:1145/developer.html
- **API Coordinator**: http://localhost:8080

### 4. Configure ESP32 (Optional)
```cpp
// Update WiFi credentials in ESP32 code
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";
const char* server_ip = "YOUR_DOCKER_HOST_IP";
```

## 📋 Service Endpoints

| Service | Port | Purpose | Health Check |
|---------|------|---------|--------------|
| Coordinator | 8080 | Central orchestration | `GET /` |
| STT Service | 8000 | Speech recognition | `GET /` |
| TTS Service | 8001 | Speech synthesis | `GET /` |
| IoT Control | 8002 | Device management | `GET /` |
| Ollama | 11434 | LLM processing | `GET /` |

### Key API Examples

```bash
# Process text command
curl -X POST http://localhost:8080/process_text \
  -H "Content-Type: application/json" \
  -d '{"text": "Turn on the living room lights"}'

# Control IoT device
curl -X POST http://localhost:8002/control \
  -H "Content-Type: application/json" \
  -d '{"commands": [{"device": "ceiling_light", "action": "on", "location": "living_room"}]}'

# Execute scene mode
curl -X POST http://localhost:8080/execute_scene \
  -H "Content-Type: application/json" \
  -d '{"scene_name": "sleep_mode", "location": "bedroom"}'
```

## 🏠 Supported Devices & Scenes

### Device Types
- **Lighting**: Ceiling lights, desk lamps with brightness/color control
- **Climate**: Air conditioners with temperature and mode control
- **Ventilation**: Fans and exhaust fans with speed control
- **Window Treatments**: Curtains with position control
- **Sensors**: Environmental monitoring (temperature, humidity, air quality)

### Scene Modes
- **🏠 Home Mode**: Welcome lighting and comfort settings
- **😴 Sleep Mode**: Dimmed lights, optimal temperature, closed curtains
- **💼 Work Mode**: Bright lighting, focused environment
- **🎬 Movie Mode**: Ambient lighting, closed curtains
- **👨‍🍳 Cooking Mode**: Bright kitchen lighting, auto ventilation
- **🚗 Away Mode**: Security settings, energy saving

### Voice Command Examples
```
English:
- "Turn on the living room lights"
- "Set bedroom temperature to 24 degrees"
- "Execute sleep mode"
- "Open the curtains halfway"

Chinese:
- "打开客厅的灯"
- "把卧室温度调到24度"
- "执行睡眠模式"
- "窗帘开一半"

Mixed:
- "Turn on 客厅的灯"
- "Set 卧室 temperature to 24度"
```

## 🔧 Configuration

### Environment Variables
```bash
# Ollama Configuration
OLLAMA_MODEL=llama3:8b
OLLAMA_HOST=ollama
OLLAMA_PORT=11434

# Service Hosts
STT_HOST=stt-service
TTS_HOST=tts-service
IOT_HOST=iot-control

# Audio Settings
WHISPER_MODEL=base
TTS_VOICE=en-US-AriaNeural
```

### Custom Device Configuration
Add new device types in `services/iot/app.py`:
```python
device_states = {
    "your_device_type": {
        "room_name": {"status": "off", "custom_property": "value"}
    }
}
```

## 📊 Monitoring & Debugging

### Health Checks
```bash
# Check all services status
curl http://localhost:8080/health

# Individual service checks
curl http://localhost:8000/  # STT
curl http://localhost:8001/  # TTS
curl http://localhost:8002/  # IoT
curl http://localhost:11434/ # Ollama
```

### Logs & Debugging
```bash
# View service logs
docker-compose logs coordinator
docker-compose logs stt-service
docker-compose logs -f --tail=100

# Access developer tools
# Visit http://localhost:1145/developer.html
```

## 🧪 Testing

### Voice Recognition Test
```javascript
// Browser console
testSTTUpload()        // Test file upload
testSTTRecord()        // Test live recording
testSTTWithSample()    // Test with generated audio
```

### IoT Control Test
```javascript
// Execute scene modes
executeSceneFromDev('sleep_mode')
executeSceneFromDev('work_mode')

// Individual device control
sendIoTCommand()
```

## 📈 Performance Optimization

### Model Selection
Choose the appropriate Whisper model based on your hardware:
- `tiny` - Fastest, lower accuracy (39 MB)
- `base` - Balanced performance (74 MB) **[Recommended]**
- `small` - Higher accuracy (244 MB)
- `medium` - Best accuracy (769 MB)

### Resource Usage
- **Minimum**: 4GB RAM, 2 CPU cores
- **Recommended**: 8GB RAM, 4 CPU cores
- **Storage**: 10GB+ for models and data

## 🔒 Security Considerations

- **Network Isolation**: Services communicate through internal Docker network
- **No External Dependencies**: Fully self-contained system
- **Voice Data**: Processed locally, not sent to cloud services
- **Privacy**: All user interactions remain on local network

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

### Development Setup
```bash
# Clone repository
git clone https://github.com/yourusername/ai-smart-home-assistant.git
cd ai-smart-home-assistant

# Create development environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements-dev.txt

# Run tests
pytest tests/
```

## 📖 Research Background

This project is part of UCL CASA dissertation research on "Edge Computing and Large Language Model (LLMs) Powered Semantic Frameworks for Connected Smart Homes."

**Research Hypothesis**: The smart home framework based on LLM and edge computing enables understanding and processing of user semantics, significantly outperforming traditional rule-based methods in terms of intent extraction performance and user satisfaction.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **UCL Centre for Advanced Spatial Analysis** for research support
- **OpenAI** for Whisper speech recognition model
- **Meta** for Llama language models
- **Microsoft** for Edge TTS technology
- **Espressif** for ESP32 platform

**Built with ❤️ for the future of smart homes**