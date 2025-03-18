// Main program entry point

// DOM loaded event
document.addEventListener('DOMContentLoaded', function() {
    // Ollama model management
    document.getElementById('check-models').addEventListener('click', checkOllamaModels);
    document.getElementById('pull-model').addEventListener('click', pullOllamaModel);
    
    // Service status check
    document.getElementById('check-coordinator').addEventListener('click', () => checkServiceStatus('coordinator'));
    document.getElementById('check-stt').addEventListener('click', () => checkServiceStatus('stt'));
    document.getElementById('check-tts').addEventListener('click', () => checkServiceStatus('tts'));
    document.getElementById('check-iot').addEventListener('click', () => checkServiceStatus('iot'));
    
    // AI interaction
    document.getElementById('send-text').addEventListener('click', sendTextToAI);
    document.getElementById('clear-chat').addEventListener('click', clearChat);
    document.getElementById('user-input').addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendTextToAI();
        }
    });
    
    // IoT device control
    document.getElementById('send-command').addEventListener('click', sendIoTCommand);
    document.getElementById('get-devices').addEventListener('click', getAllDevices);
    
    // Device type change updates action dropdown
    document.getElementById('device-type').addEventListener('change', updateActionDropdown);
    
    // Text-to-speech
    document.getElementById('synthesize-speech').addEventListener('click', synthesizeSpeech);
    document.getElementById('get-voices').addEventListener('click', getAvailableVoices);
    
    // WebSocket interaction
    document.getElementById('ws-connect').addEventListener('click', connectWebSocket);
    document.getElementById('ws-disconnect').addEventListener('click', disconnectWebSocket);
    document.getElementById('ws-send').addEventListener('click', sendWebSocketMessage);
    document.getElementById('ws-message').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            sendWebSocketMessage();
        }
    });
    
    // Initialize
    updateActionDropdown();
    
    // Display welcome message
    console.log('AI Voice Assistant Control Panel loaded');
});