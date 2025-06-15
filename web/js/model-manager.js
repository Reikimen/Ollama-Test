/**
 * Dynamic Model Manager for Smart Home Assistant
 * 实现网页端动态切换Ollama模型的功能
 * 
 * 核心功能：
 * 1. 获取可用模型列表
 * 2. 动态切换当前模型
 * 3. 下载新模型
 * 4. 模型性能测试
 * 5. 实时状态监控
 */

// 全局模型管理状态
const ModelManager = {
    currentModel: '',
    availableModels: [],
    modelInfo: {},
    switchInProgress: false,
    downloadInProgress: false,
    lastUpdateTime: 0,
    updateInterval: 30000, // 30秒更新间隔
    
    // UI元素引用
    elements: {
        currentModelBadge: null,
        modelSelector: null,
        switchButton: null,
        refreshButton: null,
        downloadButton: null,
        downloadInput: null,
        testButton: null,
        statusOutput: null,
        modelInfo: null,
        responseTimeBadge: null,
        modelSizeBadge: null,
        modelsCountBadge: null,
        testResult: null,
        chatCurrentModel: null
    },
    
    // 初始化
    init() {
        console.log('🤖 Initializing Dynamic Model Manager...');
        this.bindElements();
        this.bindEvents();
        this.loadModels();
        this.startPeriodicUpdate();
        console.log('✅ Model Manager initialized');
    },
    
    // 绑定DOM元素
    bindElements() {
        this.elements = {
            currentModelBadge: document.getElementById('current-model-badge'),
            modelSelector: document.getElementById('model-selector'),
            switchButton: document.getElementById('switch-model-btn'),
            refreshButton: document.getElementById('refresh-models-btn'),
            downloadButton: document.getElementById('download-model-btn'),
            downloadInput: document.getElementById('model-download-input'),
            testButton: document.getElementById('test-current-model'),
            statusOutput: document.getElementById('model-status-output'),
            modelInfo: document.getElementById('model-info-display'),
            responseTimeBadge: document.getElementById('response-time-badge'),
            modelSizeBadge: document.getElementById('model-size-badge'),
            modelsCountBadge: document.getElementById('models-count-badge'),
            testResult: document.getElementById('model-test-result'),
            chatCurrentModel: document.getElementById('chat-current-model')
        };
        
        // 检查必要元素是否存在
        const missingElements = Object.entries(this.elements)
            .filter(([key, element]) => !element)
            .map(([key]) => key);
            
        if (missingElements.length > 0) {
            console.warn('⚠️ Some UI elements not found:', missingElements);
        }
    },
    
    // 绑定事件监听器
    bindEvents() {
        // 模型切换
        if (this.elements.switchButton) {
            this.elements.switchButton.addEventListener('click', () => this.switchModel());
        }
        
        // 刷新模型列表
        if (this.elements.refreshButton) {
            this.elements.refreshButton.addEventListener('click', () => this.refreshModels());
        }
        
        // 下载模型
        if (this.elements.downloadButton) {
            this.elements.downloadButton.addEventListener('click', () => this.downloadModel());
        }
        
        // 测试当前模型
        if (this.elements.testButton) {
            this.elements.testButton.addEventListener('click', () => this.testCurrentModel());
        }
        
        // 模型选择器变化
        if (this.elements.modelSelector) {
            this.elements.modelSelector.addEventListener('change', () => this.onModelSelectorChange());
        }
        
        // 下载输入框回车键
        if (this.elements.downloadInput) {
            this.elements.downloadInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.downloadModel();
                }
            });
        }
    },
    
    // 加载可用模型列表
    async loadModels() {
        try {
            this.logStatus('🔍 正在获取可用模型列表...');
            
            const response = await fetch(`${API_URLS.coordinator}/models`);
            const data = await response.json();
            
            if (response.ok) {
                this.availableModels = data.available_models || [];
                this.currentModel = data.current_model || '';
                this.modelInfo = {};
                
                // 构建模型信息映射
                this.availableModels.forEach(model => {
                    this.modelInfo[model.name] = model;
                });
                
                this.updateUI(data);
                this.updateModelSelector();
                
                this.logStatus(`✅ 成功加载 ${this.availableModels.length} 个模型`);
                console.log('📋 Available models:', this.availableModels.map(m => m.name));
                
                this.lastUpdateTime = Date.now();
                
            } else {
                throw new Error(data.error || 'Failed to load models');
            }
            
        } catch (error) {
            console.error('❌ Error loading models:', error);
            this.logStatus(`❌ 加载模型失败: ${error.message}`, 'error');
        }
    },
    
    // 刷新模型列表
    async refreshModels() {
        if (this.elements.refreshButton) {
            this.elements.refreshButton.disabled = true;
            this.elements.refreshButton.innerHTML = '<i class="bi bi-arrow-clockwise"></i> 刷新中...';
        }
        
        try {
            await this.loadModels();
        } finally {
            if (this.elements.refreshButton) {
                this.elements.refreshButton.disabled = false;
                this.elements.refreshButton.innerHTML = '<i class="bi bi-arrow-clockwise"></i> 刷新模型列表';
            }
        }
    },
    
    // 切换模型
    async switchModel() {
        if (!this.elements.modelSelector) return;
        
        const selectedModel = this.elements.modelSelector.value;
        if (!selectedModel) {
            alert('请选择要切换的模型');
            return;
        }
        
        if (selectedModel === this.currentModel) {
            alert('该模型已经是当前使用的模型');
            return;
        }
        
        if (this.switchInProgress) {
            alert('模型切换正在进行中，请稍候');
            return;
        }
        
        this.switchInProgress = true;
        this.updateSwitchButtonState(true);
        
        try {
            this.logStatus(`🔄 正在切换到模型: ${selectedModel}...`);
            
            const startTime = Date.now();
            
            const response = await fetch(`${API_URLS.coordinator}/models/switch`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model_name: selectedModel })
            });
            
            const data = await response.json();
            const switchTime = Date.now() - startTime;
            
            if (response.ok && data.success) {
                this.currentModel = selectedModel;
                
                this.logStatus(`✅ 成功切换到 ${selectedModel} (耗时: ${switchTime}ms)`, 'success');
                
                // 显示模型测试结果
                if (data.test_result) {
                    const testResult = data.test_result;
                    this.logStatus(`📊 模型测试: ${testResult.success ? '✅ 通过' : '❌ 失败'}`);
                    
                    if (testResult.eval_count) {
                        const processingTime = Math.round(testResult.eval_duration / 1000000);
                        this.logStatus(`⚡ 性能: ${testResult.eval_count} tokens, ${processingTime}ms`);
                        
                        // 更新性能指标
                        if (this.elements.responseTimeBadge) {
                            this.elements.responseTimeBadge.textContent = `${processingTime} ms`;
                        }
                    }
                }
                
                // 刷新界面
                await this.loadModels();
                
                // 通知其他组件模型已切换
                this.notifyModelSwitch(selectedModel);
                
            } else {
                throw new Error(data.error || 'Unknown error during model switch');
            }
            
        } catch (error) {
            console.error('❌ Model switch failed:', error);
            this.logStatus(`❌ 模型切换失败: ${error.message}`, 'error');
        } finally {
            this.switchInProgress = false;
            this.updateSwitchButtonState(false);
        }
    },
    
    // 下载新模型
    async downloadModel() {
        if (!this.elements.downloadInput) return;
        
        const modelName = this.elements.downloadInput.value.trim();
        if (!modelName) {
            alert('请输入要下载的模型名称');
            return;
        }
        
        if (this.downloadInProgress) {
            alert('已有模型正在下载中');
            return;
        }
        
        this.downloadInProgress = true;
        this.updateDownloadButtonState(true);
        
        try {
            this.logStatus(`📥 开始下载模型: ${modelName}...`);
            this.logStatus('⏳ 下载可能需要几分钟时间，请耐心等待...');
            
            const response = await fetch(`${API_URLS.coordinator}/models/pull`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model_name: modelName })
            });
            
            const data = await response.json();
            
            if (response.ok && data.success) {
                this.logStatus(`✅ 成功下载模型: ${modelName}`, 'success');
                
                // 清空输入框
                this.elements.downloadInput.value = '';
                
                // 刷新模型列表
                await this.loadModels();
                
            } else {
                throw new Error(data.error || 'Download failed');
            }
            
        } catch (error) {
            console.error('❌ Model download failed:', error);
            this.logStatus(`❌ 下载失败: ${error.message}`, 'error');
        } finally {
            this.downloadInProgress = false;
            this.updateDownloadButtonState(false);
        }
    },
    
    // 测试当前模型
    async testCurrentModel() {
        if (!this.elements.testButton) return;
        
        this.elements.testButton.disabled = true;
        this.elements.testButton.innerHTML = '<i class="bi bi-hourglass-split"></i> 测试中...';
        
        if (this.elements.testResult) {
            this.elements.testResult.textContent = '正在测试模型性能...';
            this.elements.testResult.className = 'text-info';
        }
        
        try {
            const startTime = Date.now();
            
            const response = await fetch(`${API_URLS.coordinator}/process_text`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    text: 'Hello! Please respond briefly to test the current model performance.' 
                })
            });
            
            const endTime = Date.now();
            const responseTime = endTime - startTime;
            
            if (response.ok) {
                const data = await response.json();
                
                if (this.elements.testResult) {
                    const responsePreview = data.ai_response.substring(0, 50);
                    this.elements.testResult.innerHTML = `✅ 模型测试成功！响应时间: ${responseTime}ms<br><small>响应: "${responsePreview}..."</small><br><small>使用模型: ${data.model_used || this.currentModel}</small>`;
                    this.elements.testResult.className = 'text-success';
                }
                
                // 更新性能指标
                if (this.elements.responseTimeBadge) {
                    this.elements.responseTimeBadge.textContent = `${responseTime} ms`;
                }
                
                this.logStatus(`✅ 模型测试成功 (${responseTime}ms)`, 'success');
                
            } else {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
        } catch (error) {
            console.error('❌ Model test failed:', error);
            if (this.elements.testResult) {
                this.elements.testResult.textContent = `❌ 模型测试失败: ${error.message}`;
                this.elements.testResult.className = 'text-danger';
            }
            this.logStatus(`❌ 模型测试失败: ${error.message}`, 'error');
        } finally {
            if (this.elements.testButton) {
                this.elements.testButton.disabled = false;
                this.elements.testButton.innerHTML = '<i class="bi bi-play-circle"></i> 测试当前模型';
            }
        }
    },
    
    // 更新UI
    updateUI(data) {
        // 更新当前模型显示
        if (this.elements.currentModelBadge) {
            this.elements.currentModelBadge.textContent = data.current_model;
        }
        
        if (this.elements.chatCurrentModel) {
            this.elements.chatCurrentModel.textContent = data.current_model;
        }
        
        // 更新模型数量
        if (this.elements.modelsCountBadge) {
            this.elements.modelsCountBadge.textContent = data.total_models;
        }
        
        // 更新当前模型大小
        const currentModelData = data.available_models.find(m => m.is_current);
        if (currentModelData) {
            if (this.elements.modelSizeBadge) {
                this.elements.modelSizeBadge.textContent = `${currentModelData.size_mb} MB`;
            }
        }
    },
    
    // 更新模型选择器
    updateModelSelector() {
        if (!this.elements.modelSelector) return;
        
        this.elements.modelSelector.innerHTML = '';
        
        if (this.availableModels.length === 0) {
            this.elements.modelSelector.innerHTML = '<option value="">没有可用模型</option>';
            if (this.elements.switchButton) {
                this.elements.switchButton.disabled = true;
            }
            return;
        }
        
        // 添加默认选项
        this.elements.modelSelector.innerHTML = '<option value="">选择模型...</option>';
        
        // 添加模型选项
        this.availableModels.forEach(model => {
            const option = document.createElement('option');
            option.value = model.name;
            option.textContent = `${model.name} (${model.size_mb} MB)`;
            
            if (model.is_current) {
                option.textContent += ' [当前使用]';
                option.style.fontWeight = 'bold';
                option.style.color = '#0d6efd';
            }
            
            this.elements.modelSelector.appendChild(option);
        });
        
        if (this.elements.switchButton) {
            this.elements.switchButton.disabled = false;
        }
    },
    
    // 模型选择器变化处理
    onModelSelectorChange() {
        if (!this.elements.modelSelector || !this.elements.modelInfo) return;
        
        const selectedModel = this.elements.modelSelector.value;
        
        if (!selectedModel) {
            this.elements.modelInfo.innerHTML = '<small class="text-muted">选择模型以查看详细信息</small>';
            return;
        }
        
        const modelData = this.modelInfo[selectedModel];
        if (modelData) {
            const modifiedDate = modelData.modified_at ? 
                new Date(modelData.modified_at).toLocaleDateString('zh-CN') : '未知';
            
            this.elements.modelInfo.innerHTML = `
                <strong>${modelData.name}</strong><br>
                <small class="text-muted">
                    大小: ${modelData.size_mb} MB<br>
                    修改时间: ${modifiedDate}<br>
                    状态: ${modelData.is_current ? 
                        '<span class="badge bg-primary">当前使用</span>' : 
                        '<span class="badge bg-secondary">可用</span>'}
                </small>
            `;
        }
    },
    
    // 更新切换按钮状态
    updateSwitchButtonState(switching) {
        if (!this.elements.switchButton) return;
        
        this.elements.switchButton.disabled = switching;
        if (switching) {
            this.elements.switchButton.innerHTML = '<i class="bi bi-hourglass-split"></i> 切换中...';
        } else {
            this.elements.switchButton.innerHTML = '<i class="bi bi-arrow-repeat"></i> 切换模型';
        }
    },
    
    // 更新下载按钮状态
    updateDownloadButtonState(downloading) {
        if (!this.elements.downloadButton) return;
        
        this.elements.downloadButton.disabled = downloading;
        if (downloading) {
            this.elements.downloadButton.innerHTML = '<i class="bi bi-hourglass-split"></i> 下载中...';
        } else {
            this.elements.downloadButton.innerHTML = '<i class="bi bi-download"></i> 下载';
        }
    },
    
    // 记录状态日志
    logStatus(message, type = 'info') {
        if (!this.elements.statusOutput) return;
        
        const timestamp = new Date().toLocaleTimeString('zh-CN');
        const cssClass = type === 'error' ? 'console-output error' : 
                        type === 'success' ? 'console-output success' : 'console-output';
        
        this.elements.statusOutput.innerHTML += `<div class="${cssClass}">[${timestamp}] ${message}</div>`;
        
        // 自动滚动到底部
        this.elements.statusOutput.scrollTop = this.elements.statusOutput.scrollHeight;
        
        // 限制日志条数，避免界面卡顿
        const logs = this.elements.statusOutput.querySelectorAll('div');
        if (logs.length > 50) {
            for (let i = 0; i < 10; i++) {
                if (logs[i]) logs[i].remove();
            }
        }
        
        console.log(`[ModelManager] ${message}`);
    },
    
    // 通知模型切换
    notifyModelSwitch(newModel) {
        // 触发自定义事件
        const event = new CustomEvent('modelSwitched', {
            detail: {
                newModel: newModel,
                oldModel: this.currentModel,
                timestamp: Date.now()
            }
        });
        document.dispatchEvent(event);
        
        // 如果有WebSocket连接，通知服务器
        if (typeof wsConnection !== 'undefined' && wsConnection && wsConnection.readyState === WebSocket.OPEN) {
            wsConnection.send(JSON.stringify({
                type: 'model_switch_notification',
                new_model: newModel,
                timestamp: Date.now()
            }));
        }
        
        console.log(`🔄 Model switched notification sent: ${newModel}`);
    },
    
    // 定期更新
    startPeriodicUpdate() {
        setInterval(() => {
            // 如果没有操作进行中且距离上次更新超过间隔时间，则自动更新
            if (!this.switchInProgress && !this.downloadInProgress) {
                const timeSinceUpdate = Date.now() - this.lastUpdateTime;
                if (timeSinceUpdate > this.updateInterval) {
                    this.loadModels();
                }
            }
        }, this.updateInterval);
    },
    
    // 获取当前模型信息
    getCurrentModel() {
        return this.currentModel;
    },
    
    // 获取可用模型列表
    getAvailableModels() {
        return this.availableModels;
    },
    
    // 检查模型是否可用
    isModelAvailable(modelName) {
        return this.availableModels.some(model => model.name === modelName);
    },
    
    // 获取模型详细信息
    getModelInfo(modelName) {
        return this.modelInfo[modelName] || null;
    },
    
    // 清除状态日志
    clearStatusLog() {
        if (this.elements.statusOutput) {
            this.elements.statusOutput.innerHTML = '<div class="console-output">状态日志已清除</div>';
        }
    }
};

// 全局快捷函数，方便其他模块调用
window.ModelManager = ModelManager;

// 快捷访问函数
window.getCurrentModel = () => ModelManager.getCurrentModel();
window.getAvailableModels = () => ModelManager.getAvailableModels();
window.switchToModel = (modelName) => {
    if (ModelManager.elements.modelSelector) {
        ModelManager.elements.modelSelector.value = modelName;
        return ModelManager.switchModel();
    }
};

// 监听模型切换事件（其他模块可以使用）
document.addEventListener('modelSwitched', (event) => {
    console.log('🔔 Model switch event detected:', event.detail);
    
    // 更新聊天界面的模型显示
    const chatModelElements = document.querySelectorAll('[data-current-model]');
    chatModelElements.forEach(element => {
        element.textContent = event.detail.newModel;
    });
    
    // 可以在这里添加其他需要响应模型切换的逻辑
});

// DOM加载完成后自动初始化
document.addEventListener('DOMContentLoaded', () => {
    // 延迟初始化，确保其他模块已加载
    setTimeout(() => {
        ModelManager.init();
    }, 500);
});

// 调试函数 - 仅在开发模式下可用
if (typeof window.DEBUG !== 'undefined' && window.DEBUG) {
    window.debugModelManager = () => {
        console.log('🔧 Model Manager Debug Info:');
        console.log('Current Model:', ModelManager.currentModel);
        console.log('Available Models:', ModelManager.availableModels);
        console.log('Model Info:', ModelManager.modelInfo);
        console.log('Switch in Progress:', ModelManager.switchInProgress);
        console.log('Download in Progress:', ModelManager.downloadInProgress);
        console.log('Last Update Time:', new Date(ModelManager.lastUpdateTime).toLocaleString());
    };
}

// 错误恢复机制
window.addEventListener('beforeunload', () => {
    // 在页面卸载前清理定时器等资源
    if (ModelManager.updateTimer) {
        clearInterval(ModelManager.updateTimer);
    }
});

console.log('📦 Dynamic Model Manager module loaded successfully');