"""
Enhanced Anomaly Detector for Real-time Mercedes W222 OBD Analysis
Supports multiple models, confidence scoring, and automotive-specific anomaly types
"""
import os
import json
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import joblib
from dataclasses import dataclass

from ...data.database_manager import DatabaseManager, AnomalyRecord

@dataclass
class AnomalyResult:
    """Enhanced anomaly detection result"""
    parameter_name: str
    value: float
    anomaly_score: float
    is_anomaly: bool
    confidence: float
    severity: str  # low, medium, high, critical
    anomaly_type: str  # statistical, pattern, threshold, contextual
    description: str
    recommended_action: str
    timestamp: datetime

class EnhancedAnomalyDetector:
    """Enhanced Anomaly Detector with multiple detection methods"""
    
    def __init__(self, db_manager: DatabaseManager, models_dir: str = "mercedes_obd_scanner/ml/models"):
        self.db_manager = db_manager
        self.models_dir = Path(models_dir)
        self.logger = logging.getLogger(__name__)
        
        # Load models
        self.models = {}
        self.scalers = {}
        self.load_available_models()
        
        # Mercedes W222 specific thresholds and patterns
        self.w222_thresholds = {
            'ENGINE_RPM': {'min': 600, 'max': 6500, 'optimal_range': (800, 4000)},
            'COOLANT_TEMP': {'min': 70, 'max': 110, 'optimal_range': (85, 95)},
            'ENGINE_LOAD': {'min': 0, 'max': 100, 'optimal_range': (10, 80)},
            'SPEED': {'min': 0, 'max': 250, 'optimal_range': (0, 180)},
            'OIL_PRESSURE': {'min': 1.5, 'max': 8.0, 'optimal_range': (2.5, 6.0)},
            'TRANS_TEMP': {'min': 60, 'max': 120, 'optimal_range': (80, 100)},
            'AIR_PRESSURE_FL': {'min': 8, 'max': 16, 'optimal_range': (10, 14)},
            'AIR_PRESSURE_FR': {'min': 8, 'max': 16, 'optimal_range': (10, 14)},
            'FUEL_LEVEL': {'min': 0, 'max': 100, 'optimal_range': (10, 90)}
        }
        
        # Contextual rules for Mercedes W222
        self.contextual_rules = {
            'high_rpm_low_speed': {
                'condition': lambda data: data.get('ENGINE_RPM', 0) > 3000 and data.get('SPEED', 0) < 30,
                'severity': 'medium',
                'description': 'High RPM at low speed - possible transmission issue or aggressive driving',
                'action': 'Check transmission fluid and driving patterns'
            },
            'high_temp_normal_load': {
                'condition': lambda data: data.get('COOLANT_TEMP', 0) > 100 and data.get('ENGINE_LOAD', 0) < 50,
                'severity': 'high',
                'description': 'High coolant temperature with normal load - possible cooling system issue',
                'action': 'Check cooling system, thermostat, and coolant levels'
            },
            'low_oil_pressure': {
                'condition': lambda data: data.get('OIL_PRESSURE', 0) < 2.0 and data.get('ENGINE_RPM', 0) > 1000,
                'severity': 'critical',
                'description': 'Low oil pressure at operating RPM - immediate attention required',
                'action': 'Stop engine immediately and check oil level and pump'
            },
            'air_suspension_imbalance': {
                'condition': lambda data: abs(data.get('AIR_PRESSURE_FL', 0) - data.get('AIR_PRESSURE_FR', 0)) > 2,
                'severity': 'medium',
                'description': 'Air suspension pressure imbalance detected',
                'action': 'Check air suspension system and struts'
            },
            'transmission_overheating': {
                'condition': lambda data: data.get('TRANS_TEMP', 0) > 110,
                'severity': 'high',
                'description': 'Transmission overheating detected',
                'action': 'Reduce load and check transmission cooling system'
            }
        }
        
        # Historical data buffer for pattern analysis
        self.data_buffer = {}
        self.buffer_size = 100
        
    def load_available_models(self):
        """Load all available trained models"""
        if not self.models_dir.exists():
            self.logger.warning(f"Models directory {self.models_dir} does not exist")
            return
        
        model_files = list(self.models_dir.glob("*.pkl"))
        self.logger.info(f"Found {len(model_files)} model files")
        
        for model_file in model_files:
            try:
                model = joblib.load(model_file)
                model_name = model_file.stem
                self.models[model_name] = model
                self.logger.info(f"Loaded model: {model_name}")
            except Exception as e:
                self.logger.error(f"Failed to load model {model_file}: {str(e)}")
    
    def detect_anomalies(self, current_data: Dict[str, float], 
                        session_id: str, vehicle_id: str = None) -> List[AnomalyResult]:
        """Comprehensive anomaly detection using multiple methods"""
        
        anomalies = []
        timestamp = datetime.now()
        
        # Update data buffer
        self._update_data_buffer(session_id, current_data, timestamp)
        
        # 1. Threshold-based detection
        threshold_anomalies = self._detect_threshold_anomalies(current_data, timestamp)
        anomalies.extend(threshold_anomalies)
        
        # 2. Contextual rule-based detection
        contextual_anomalies = self._detect_contextual_anomalies(current_data, timestamp)
        anomalies.extend(contextual_anomalies)
        
        # 3. Statistical model-based detection
        if self.models:
            statistical_anomalies = self._detect_statistical_anomalies(current_data, timestamp)
            anomalies.extend(statistical_anomalies)
        
        # 4. Pattern-based detection (using historical data)
        pattern_anomalies = self._detect_pattern_anomalies(session_id, current_data, timestamp)
        anomalies.extend(pattern_anomalies)
        
        # 5. Vehicle-specific detection (if vehicle profile available)
        if vehicle_id:
            profile_anomalies = self._detect_profile_based_anomalies(
                vehicle_id, current_data, timestamp
            )
            anomalies.extend(profile_anomalies)
        
        # Log anomalies to database
        for anomaly in anomalies:
            anomaly_record = AnomalyRecord(
                session_id=session_id,
                parameter_name=anomaly.parameter_name,
                value=anomaly.value,
                anomaly_score=anomaly.anomaly_score,
                timestamp=anomaly.timestamp,
                severity=anomaly.severity,
                description=f"{anomaly.anomaly_type}: {anomaly.description}"
            )
            self.db_manager.log_anomaly(anomaly_record)
        
        return anomalies
    
    def _update_data_buffer(self, session_id: str, data: Dict[str, float], timestamp: datetime):
        """Update historical data buffer for pattern analysis"""
        if session_id not in self.data_buffer:
            self.data_buffer[session_id] = []
        
        # Add current data point
        data_point = {**data, 'timestamp': timestamp}
        self.data_buffer[session_id].append(data_point)
        
        # Maintain buffer size
        if len(self.data_buffer[session_id]) > self.buffer_size:
            self.data_buffer[session_id] = self.data_buffer[session_id][-self.buffer_size:]
    
    def _detect_threshold_anomalies(self, data: Dict[str, float], 
                                  timestamp: datetime) -> List[AnomalyResult]:
        """Detect anomalies based on Mercedes W222 specific thresholds"""
        anomalies = []
        
        for param, value in data.items():
            if param in self.w222_thresholds:
                thresholds = self.w222_thresholds[param]
                
                # Check absolute limits
                if value < thresholds['min'] or value > thresholds['max']:
                    severity = 'critical' if (value < thresholds['min'] * 0.8 or 
                                            value > thresholds['max'] * 1.2) else 'high'
                    
                    anomaly = AnomalyResult(
                        parameter_name=param,
                        value=value,
                        anomaly_score=self._calculate_threshold_score(value, thresholds),
                        is_anomaly=True,
                        confidence=0.9,
                        severity=severity,
                        anomaly_type='threshold',
                        description=f'{param} value {value} outside safe range [{thresholds["min"]}, {thresholds["max"]}]',
                        recommended_action=f'Check {param.lower().replace("_", " ")} system immediately',
                        timestamp=timestamp
                    )
                    anomalies.append(anomaly)
                
                # Check optimal range
                elif not (thresholds['optimal_range'][0] <= value <= thresholds['optimal_range'][1]):
                    anomaly = AnomalyResult(
                        parameter_name=param,
                        value=value,
                        anomaly_score=self._calculate_threshold_score(value, thresholds, optimal=True),
                        is_anomaly=True,
                        confidence=0.7,
                        severity='low',
                        anomaly_type='threshold',
                        description=f'{param} value {value} outside optimal range {thresholds["optimal_range"]}',
                        recommended_action=f'Monitor {param.lower().replace("_", " ")} trends',
                        timestamp=timestamp
                    )
                    anomalies.append(anomaly)
        
        return anomalies
    
    def _detect_contextual_anomalies(self, data: Dict[str, float], 
                                   timestamp: datetime) -> List[AnomalyResult]:
        """Detect contextual anomalies using Mercedes W222 specific rules"""
        anomalies = []
        
        for rule_name, rule in self.contextual_rules.items():
            if rule['condition'](data):
                # Find the most relevant parameter for this rule
                param = self._get_primary_parameter_for_rule(rule_name, data)
                
                anomaly = AnomalyResult(
                    parameter_name=param,
                    value=data.get(param, 0),
                    anomaly_score=0.8,  # High confidence for rule-based detection
                    is_anomaly=True,
                    confidence=0.85,
                    severity=rule['severity'],
                    anomaly_type='contextual',
                    description=rule['description'],
                    recommended_action=rule['action'],
                    timestamp=timestamp
                )
                anomalies.append(anomaly)
        
        return anomalies
    
    def _detect_statistical_anomalies(self, data: Dict[str, float], 
                                    timestamp: datetime) -> List[AnomalyResult]:
        """Detect anomalies using trained ML models"""
        anomalies = []
        
        # Prepare data for model input
        feature_data = self._prepare_model_input(data)
        if feature_data is None:
            return anomalies
        
        for model_name, model in self.models.items():
            if 'anomaly' in model_name.lower():
                try:
                    # Get anomaly score
                    if hasattr(model, 'decision_function'):
                        score = model.decision_function([feature_data])[0]
                        prediction = model.predict([feature_data])[0]
                        
                        if prediction == -1:  # Anomaly detected
                            # Determine primary parameter (simplified approach)
                            primary_param = max(data.keys(), key=lambda k: abs(data[k]) if data[k] != 0 else 0)
                            
                            # Map score to severity
                            severity = self._map_score_to_severity(score)
                            
                            anomaly = AnomalyResult(
                                parameter_name=primary_param,
                                value=data[primary_param],
                                anomaly_score=abs(score),
                                is_anomaly=True,
                                confidence=min(abs(score), 1.0),
                                severity=severity,
                                anomaly_type='statistical',
                                description=f'Statistical anomaly detected by {model_name}',
                                recommended_action='Review recent parameter trends and vehicle condition',
                                timestamp=timestamp
                            )
                            anomalies.append(anomaly)
                
                except Exception as e:
                    self.logger.error(f"Error in statistical anomaly detection with {model_name}: {str(e)}")
        
        return anomalies
    
    def _detect_pattern_anomalies(self, session_id: str, current_data: Dict[str, float], 
                                timestamp: datetime) -> List[AnomalyResult]:
        """Detect anomalies based on historical patterns"""
        anomalies = []
        
        if session_id not in self.data_buffer or len(self.data_buffer[session_id]) < 10:
            return anomalies  # Need sufficient history
        
        historical_data = self.data_buffer[session_id]
        
        for param, current_value in current_data.items():
            if param in ['timestamp']:
                continue
            
            # Get historical values for this parameter
            historical_values = [d.get(param, 0) for d in historical_data if param in d]
            
            if len(historical_values) < 5:
                continue
            
            # Calculate statistical measures
            mean_val = np.mean(historical_values)
            std_val = np.std(historical_values)
            
            if std_val > 0:
                z_score = abs(current_value - mean_val) / std_val
                
                # Detect significant deviations
                if z_score > 3:  # 3-sigma rule
                    anomaly = AnomalyResult(
                        parameter_name=param,
                        value=current_value,
                        anomaly_score=min(z_score / 3, 1.0),
                        is_anomaly=True,
                        confidence=0.8,
                        severity='medium' if z_score < 4 else 'high',
                        anomaly_type='pattern',
                        description=f'{param} deviates significantly from recent pattern (Z-score: {z_score:.2f})',
                        recommended_action=f'Investigate cause of {param.lower().replace("_", " ")} variation',
                        timestamp=timestamp
                    )
                    anomalies.append(anomaly)
        
        return anomalies
    
    def _detect_profile_based_anomalies(self, vehicle_id: str, current_data: Dict[str, float], 
                                      timestamp: datetime) -> List[AnomalyResult]:
        """Detect anomalies based on vehicle-specific profile"""
        anomalies = []
        
        try:
            # Get vehicle profile
            profile = self.db_manager.get_vehicle_profile(vehicle_id)
            if not profile or not profile.get('baseline_parameters'):
                return anomalies
            
            baseline_params = profile['baseline_parameters']
            
            for param, current_value in current_data.items():
                if param in baseline_params:
                    baseline = baseline_params[param]
                    expected_value = baseline.get('mean', current_value)
                    tolerance = baseline.get('std', 0) * 2  # 2-sigma tolerance
                    
                    if tolerance > 0 and abs(current_value - expected_value) > tolerance:
                        deviation_ratio = abs(current_value - expected_value) / tolerance
                        
                        anomaly = AnomalyResult(
                            parameter_name=param,
                            value=current_value,
                            anomaly_score=min(deviation_ratio / 2, 1.0),
                            is_anomaly=True,
                            confidence=0.75,
                            severity='low' if deviation_ratio < 1.5 else 'medium',
                            anomaly_type='profile',
                            description=f'{param} deviates from vehicle baseline (expected: {expected_value:.1f})',
                            recommended_action=f'Compare with historical {param.lower().replace("_", " ")} values',
                            timestamp=timestamp
                        )
                        anomalies.append(anomaly)
        
        except Exception as e:
            self.logger.error(f"Error in profile-based anomaly detection: {str(e)}")
        
        return anomalies
    
    def _calculate_threshold_score(self, value: float, thresholds: Dict[str, Any], 
                                 optimal: bool = False) -> float:
        """Calculate anomaly score based on threshold deviation"""
        if optimal:
            opt_min, opt_max = thresholds['optimal_range']
            if value < opt_min:
                return min((opt_min - value) / opt_min, 1.0)
            elif value > opt_max:
                return min((value - opt_max) / opt_max, 1.0)
        else:
            if value < thresholds['min']:
                return min((thresholds['min'] - value) / thresholds['min'], 1.0)
            elif value > thresholds['max']:
                return min((value - thresholds['max']) / thresholds['max'], 1.0)
        
        return 0.0
    
    def _get_primary_parameter_for_rule(self, rule_name: str, data: Dict[str, float]) -> str:
        """Get the primary parameter associated with a contextual rule"""
        rule_param_map = {
            'high_rpm_low_speed': 'ENGINE_RPM',
            'high_temp_normal_load': 'COOLANT_TEMP',
            'low_oil_pressure': 'OIL_PRESSURE',
            'air_suspension_imbalance': 'AIR_PRESSURE_FL',
            'transmission_overheating': 'TRANS_TEMP'
        }
        
        return rule_param_map.get(rule_name, list(data.keys())[0] if data else 'UNKNOWN')
    
    def _map_score_to_severity(self, score: float) -> str:
        """Map anomaly score to severity level"""
        abs_score = abs(score)
        if abs_score > 0.8:
            return 'high'
        elif abs_score > 0.5:
            return 'medium'
        else:
            return 'low'
    
    def _prepare_model_input(self, data: Dict[str, float]) -> Optional[List[float]]:
        """Prepare data for ML model input"""
        try:
            # This is a simplified approach - in practice, you'd need to match
            # the exact feature engineering used during training
            expected_params = ['ENGINE_RPM', 'COOLANT_TEMP', 'ENGINE_LOAD', 'SPEED',
                             'OIL_PRESSURE', 'TRANS_TEMP', 'AIR_PRESSURE_FL', 'AIR_PRESSURE_FR']
            
            feature_vector = []
            for param in expected_params:
                feature_vector.append(data.get(param, 0))
            
            return feature_vector
        
        except Exception as e:
            self.logger.error(f"Error preparing model input: {str(e)}")
            return None
    
    def get_anomaly_summary(self, session_id: str, hours_back: int = 1) -> Dict[str, Any]:
        """Get summary of anomalies for a session or time period"""
        try:
            # This would typically query the database for recent anomalies
            # For now, return a placeholder summary
            
            summary = {
                'session_id': session_id,
                'time_period_hours': hours_back,
                'total_anomalies': 0,
                'severity_breakdown': {
                    'critical': 0,
                    'high': 0,
                    'medium': 0,
                    'low': 0
                },
                'anomaly_types': {
                    'threshold': 0,
                    'contextual': 0,
                    'statistical': 0,
                    'pattern': 0,
                    'profile': 0
                },
                'most_affected_parameters': [],
                'recommendations': []
            }
            
            return summary
        
        except Exception as e:
            self.logger.error(f"Error generating anomaly summary: {str(e)}")
            return {'error': str(e)}
    
    def update_vehicle_baseline(self, vehicle_id: str, recent_data: pd.DataFrame):
        """Update vehicle baseline parameters based on recent normal operation"""
        try:
            # Calculate new baseline statistics
            baseline_params = {}
            
            for column in recent_data.columns:
                if column not in ['timestamp', 'session_id']:
                    values = recent_data[column].dropna()
                    if len(values) > 10:  # Minimum data points
                        baseline_params[column] = {
                            'mean': float(values.mean()),
                            'std': float(values.std()),
                            'min': float(values.min()),
                            'max': float(values.max()),
                            'median': float(values.median()),
                            'last_updated': datetime.now().isoformat()
                        }
            
            # Update vehicle profile
            profile_data = {
                'baseline_parameters': baseline_params,
                'learned_patterns': {}  # Could add pattern learning here
            }
            
            self.db_manager.update_vehicle_profile(vehicle_id, profile_data)
            self.logger.info(f"Updated baseline for vehicle {vehicle_id} with {len(baseline_params)} parameters")
        
        except Exception as e:
            self.logger.error(f"Error updating vehicle baseline: {str(e)}")
    
    def cleanup_old_buffers(self, max_age_hours: int = 24):
        """Clean up old data buffers to prevent memory issues"""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        sessions_to_remove = []
        for session_id, buffer_data in self.data_buffer.items():
            if buffer_data and buffer_data[-1]['timestamp'] < cutoff_time:
                sessions_to_remove.append(session_id)
        
        for session_id in sessions_to_remove:
            del self.data_buffer[session_id]
        
        if sessions_to_remove:
            self.logger.info(f"Cleaned up {len(sessions_to_remove)} old data buffers")
