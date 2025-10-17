"""
用电安全检测系统 - 快速原型
基于现有智能家居框架的数据结构
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import datetime
import json

# ============================================
# 数据结构定义（借用现有智能家居架构）
# ============================================

@dataclass
class DeviceConfig:
    """设备配置（复用现有数据结构）"""
    device_id: str
    device_type: str  # "ceiling_light", "ac", "fan", etc.
    location: str     # "living_room", "bedroom", etc.
    max_power: float  # 最大功率 (W)
    rated_current: float  # 额定电流 (A)
    rated_voltage: float  # 额定电压 (V)
    
@dataclass
class SensorData:
    """传感器数据"""
    timestamp: datetime
    device_id: str
    
    # 电气参数
    current: float      # 电流 (A)
    voltage: float      # 电压 (V)
    power: float        # 功率 (W)
    power_factor: float # 功率因数
    
    # 热力学参数
    temperature: float  # 温度 (°C)
    
    # 环境参数
    humidity: float     # 湿度 (%)
    
@dataclass
class AnomalyEvent:
    """异常事件"""
    event_id: str
    timestamp: datetime
    device_id: str
    anomaly_type: str   # "overload", "short_circuit", "leakage", etc.
    risk_level: str     # "low", "medium", "high", "critical"
    confidence: float
    explanation: str
    recommended_action: str

# ============================================
# 快速原型：基于规则的异常检测
# ============================================

class RuleBasedDetector:
    """
    基于规则的检测器（Baseline方法）
    用于快速验证数据流和系统架构
    """
    
    def __init__(self, device_config: DeviceConfig):
        self.device_config = device_config
        
        # 定义阈值规则
        self.rules = {
            'overload': {
                'current_threshold': device_config.rated_current * 1.2,
                'power_threshold': device_config.max_power * 1.15
            },
            'voltage_anomaly': {
                'low_voltage': device_config.rated_voltage * 0.9,
                'high_voltage': device_config.rated_voltage * 1.1
            },
            'thermal': {
                'warning_temp': 50,   # °C
                'critical_temp': 70   # °C
            }
        }
    
    def detect(self, sensor_data: SensorData) -> Optional[AnomalyEvent]:
        """
        基于规则的检测
        """
        # 检查过载
        if sensor_data.current > self.rules['overload']['current_threshold']:
            return AnomalyEvent(
                event_id=f"EVT_{int(sensor_data.timestamp.timestamp())}",
                timestamp=sensor_data.timestamp,
                device_id=sensor_data.device_id,
                anomaly_type="overload",
                risk_level="high",
                confidence=0.95,
                explanation=f"电流 {sensor_data.current:.2f}A 超过额定值 {self.device_config.rated_current:.2f}A",
                recommended_action="立即断电检查"
            )
        
        # 检查电压异常
        if sensor_data.voltage < self.rules['voltage_anomaly']['low_voltage']:
            return AnomalyEvent(
                event_id=f"EVT_{int(sensor_data.timestamp.timestamp())}",
                timestamp=sensor_data.timestamp,
                device_id=sensor_data.device_id,
                anomaly_type="low_voltage",
                risk_level="medium",
                confidence=0.90,
                explanation=f"电压 {sensor_data.voltage:.1f}V 低于正常范围",
                recommended_action="检查线路连接"
            )
        
        # 检查温度
        if sensor_data.temperature > self.rules['thermal']['critical_temp']:
            return AnomalyEvent(
                event_id=f"EVT_{int(sensor_data.timestamp.timestamp())}",
                timestamp=sensor_data.timestamp,
                device_id=sensor_data.device_id,
                anomaly_type="overheating",
                risk_level="critical",
                confidence=0.98,
                explanation=f"设备温度 {sensor_data.temperature:.1f}°C 过高",
                recommended_action="立即断电，等待冷却"
            )
        
        return None

# ============================================
# 快速原型：简单的ML模型
# ============================================

class SimpleMLDetector:
    """
    简单的机器学习检测器
    用于验证ML方法的可行性
    """
    
    def __init__(self):
        # 使用Isolation Forest作为快速原型
        from sklearn.ensemble import IsolationForest
        self.model = IsolationForest(
            contamination=0.1,
            random_state=42
        )
        
    def extract_features(self, sensor_data: SensorData) -> np.ndarray:
        """
        提取特征向量
        """
        features = [
            sensor_data.current,
            sensor_data.voltage,
            sensor_data.power,
            sensor_data.power_factor,
            sensor_data.temperature,
            sensor_data.humidity,
            # 可以添加更多特征
        ]
        return np.array(features).reshape(1, -1)
    
    def train(self, training_data: List[SensorData]):
        """
        训练模型
        """
        features = np.vstack([
            self.extract_features(data) for data in training_data
        ])
        self.model.fit(features)
        print(f"模型训练完成，样本数：{len(training_data)}")
    
    def detect(self, sensor_data: SensorData) -> Dict:
        """
        检测异常
        """
        features = self.extract_features(sensor_data)
        prediction = self.model.predict(features)[0]
        anomaly_score = self.model.score_samples(features)[0]
        
        is_anomaly = (prediction == -1)
        
        return {
            'is_anomaly': is_anomaly,
            'anomaly_score': float(anomaly_score),
            'confidence': abs(anomaly_score) if is_anomaly else 1 - abs(anomaly_score)
        }

# ============================================
# 数据生成器（用于测试）
# ============================================

class SyntheticDataGenerator:
    """
    生成合成数据用于快速测试
    """
    
    @staticmethod
    def generate_normal_data(device_config: DeviceConfig, 
                            num_samples: int = 1000) -> List[SensorData]:
        """
        生成正常使用数据
        """
        data_list = []
        base_time = datetime.now()
        
        for i in range(num_samples):
            # 正常范围内的随机波动
            current = np.random.normal(
                device_config.rated_current * 0.8, 
                device_config.rated_current * 0.1
            )
            voltage = np.random.normal(
                device_config.rated_voltage,
                device_config.rated_voltage * 0.02
            )
            
            data = SensorData(
                timestamp=base_time,
                device_id=device_config.device_id,
                current=max(0, current),
                voltage=voltage,
                power=current * voltage * 0.95,  # 考虑功率因数
                power_factor=np.random.uniform(0.9, 0.98),
                temperature=np.random.uniform(25, 35),
                humidity=np.random.uniform(40, 60)
            )
            data_list.append(data)
            
        return data_list
    
    @staticmethod
    def generate_anomaly_data(device_config: DeviceConfig,
                             anomaly_type: str = "overload") -> SensorData:
        """
        生成异常数据
        """
        base_time = datetime.now()
        
        if anomaly_type == "overload":
            current = device_config.rated_current * 1.5
            voltage = device_config.rated_voltage
            temperature = 60
        elif anomaly_type == "short_circuit":
            current = device_config.rated_current * 3
            voltage = device_config.rated_voltage * 0.5
            temperature = 80
        else:  # normal
            current = device_config.rated_current * 0.8
            voltage = device_config.rated_voltage
            temperature = 30
            
        return SensorData(
            timestamp=base_time,
            device_id=device_config.device_id,
            current=current,
            voltage=voltage,
            power=current * voltage * 0.9,
            power_factor=0.85,
            temperature=temperature,
            humidity=50
        )

# ============================================
# 测试代码
# ============================================

def test_prototype():
    """
    测试快速原型
    """
    print("=" * 60)
    print("用电安全检测系统 - 快速原型测试")
    print("=" * 60)
    
    # 1. 创建设备配置（复用智能家居数据结构）
    device = DeviceConfig(
        device_id="AC_LIVING_ROOM_001",
        device_type="ac",
        location="living_room",
        max_power=2000,
        rated_current=9.1,  # 2000W / 220V
        rated_voltage=220
    )
    print(f"\n设备配置：{device.device_type} @ {device.location}")
    print(f"额定功率：{device.max_power}W, 额定电流：{device.rated_current}A")
    
    # 2. 测试基于规则的检测器
    print("\n" + "=" * 60)
    print("测试1：基于规则的检测器 (Baseline)")
    print("=" * 60)
    
    rule_detector = RuleBasedDetector(device)
    
    # 生成正常数据
    normal_data = SyntheticDataGenerator.generate_normal_data(device, num_samples=10)
    print(f"\n正常数据测试 ({len(normal_data)}个样本):")
    anomalies = [rule_detector.detect(data) for data in normal_data]
    detected = sum(1 for a in anomalies if a is not None)
    print(f"  检测到异常：{detected}/{len(normal_data)}")
    
    # 生成异常数据
    print("\n异常数据测试:")
    for anomaly_type in ["overload", "short_circuit"]:
        anomaly_data = SyntheticDataGenerator.generate_anomaly_data(device, anomaly_type)
        result = rule_detector.detect(anomaly_data)
        if result:
            print(f"  ✓ {anomaly_type}: 检测成功")
            print(f"    风险等级: {result.risk_level}")
            print(f"    说明: {result.explanation}")
        else:
            print(f"  ✗ {anomaly_type}: 未检测到")
    
    # 3. 测试ML检测器
    print("\n" + "=" * 60)
    print("测试2：机器学习检测器")
    print("=" * 60)
    
    ml_detector = SimpleMLDetector()
    
    # 训练
    training_data = SyntheticDataGenerator.generate_normal_data(device, num_samples=500)
    print("\n训练模型...")
    ml_detector.train(training_data)
    
    # 测试正常数据
    test_normal = SyntheticDataGenerator.generate_normal_data(device, num_samples=50)
    normal_results = [ml_detector.detect(data) for data in test_normal]
    normal_anomalies = sum(1 for r in normal_results if r['is_anomaly'])
    print(f"\n正常数据测试: {normal_anomalies}/{len(test_normal)} 被标记为异常")
    
    # 测试异常数据
    print("\n异常数据测试:")
    for anomaly_type in ["overload", "short_circuit"]:
        anomaly_data = SyntheticDataGenerator.generate_anomaly_data(device, anomaly_type)
        result = ml_detector.detect(anomaly_data)
        status = "检测成功" if result['is_anomaly'] else "未检测到"
        print(f"  {anomaly_type}: {status} (置信度: {result['confidence']:.2f})")
    
    print("\n" + "=" * 60)
    print("原型测试完成！")
    print("=" * 60)
    
    # 4. 输出总结
    print("\n下一步工作：")
    print("1. 集成到现有智能家居系统")
    print("2. 收集真实传感器数据")
    print("3. 开发深度学习模型")
    print("4. 进行大规模实验")

if __name__ == "__main__":
    test_prototype()
