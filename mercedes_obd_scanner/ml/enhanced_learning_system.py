"""
Enhanced Self-Learning ML System for Mercedes W222 OBD Scanner.
Implements confidence scoring, automated retraining, and drift detection.
"""

import numpy as np
import pandas as pd
import joblib
import logging
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import threading
import time
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.cluster import DBSCAN
import warnings
warnings.filterwarnings('ignore')

@dataclass
class ModelMetrics:
    """Model performance metrics."""
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    confidence_avg: float
    sample_count: int
    timestamp: str
    
@dataclass
class PredictionResult:
    """ML prediction result with confidence."""
    prediction: Any
    confidence: float
    model_version: str
    features_used: List[str]
    timestamp: str
    explanation: str = ""

@dataclass
class DriftDetectionResult:
    """Model drift detection result."""
    drift_detected: bool
    drift_score: float
    affected_features: List[str]
    recommendation: str
    timestamp: str

class EnhancedLearningSystem:
    """Enhanced self-learning ML system with advanced capabilities."""
    
    def __init__(self, model_dir: str = "models", retrain_threshold: float = 0.1):
        """Initialize the enhanced learning system."""
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(exist_ok=True)
        
        self.retrain_threshold = retrain_threshold
        self.logger = logging.getLogger(__name__)
        
        # Model storage
        self.models = {}
        self.scalers = {}
        self.encoders = {}
        self.model_versions = {}
        self.performance_history = {}
        
        # Learning parameters
        self.min_samples_retrain = 100
        self.confidence_threshold = 0.7
        self.drift_detection_window = 1000
        
        # Data storage
        self.training_data = pd.DataFrame()
        self.prediction_history = []
        self.feedback_data = []
        
        # Background retraining
        self.auto_retrain_enabled = True
        self.retrain_interval = 3600  # 1 hour
        self.last_retrain = datetime.now()
        
        # Initialize models
        self._initialize_models()
        
        # Start background processes
        if self.auto_retrain_enabled:
            self._start_background_retraining()
        
        self.logger.info("🧠 Enhanced Learning System initialized")
    
    def _initialize_models(self):
        """Initialize ML models for different tasks."""
        
        # Anomaly Detection Model
        self.models['anomaly_detection'] = IsolationForest(
            contamination=0.1,
            random_state=42,
            n_estimators=100
        )
        
        # Fault Classification Model
        self.models['fault_classification'] = RandomForestClassifier(
            n_estimators=100,
            random_state=42,
            max_depth=10,
            min_samples_split=5
        )
        
        # Performance Prediction Model
        self.models['performance_prediction'] = RandomForestClassifier(
            n_estimators=150,
            random_state=42,
            max_depth=15
        )
        
        # Initialize scalers and encoders
        for model_name in self.models.keys():
            self.scalers[model_name] = StandardScaler()
            self.encoders[model_name] = LabelEncoder()
            self.model_versions[model_name] = "1.0.0"
            self.performance_history[model_name] = []
        
        self.logger.info(f"Initialized {len(self.models)} ML models")
    
    def add_training_data(self, features: Dict[str, float], 
                         target: Any, 
                         model_type: str,
                         metadata: Dict[str, Any] = None):
        """Add new training data to the system."""
        
        # Create data record
        data_record = {
            'timestamp': datetime.now().isoformat(),
            'model_type': model_type,
            'target': target,
            **features
        }
        
        if metadata:
            data_record.update({f"meta_{k}": v for k, v in metadata.items()})
        
        # Add to training data
        new_row = pd.DataFrame([data_record])
        self.training_data = pd.concat([self.training_data, new_row], ignore_index=True)
        
        self.logger.debug(f"Added training data for {model_type}: {len(features)} features")
        
        # Check if retraining is needed
        if len(self.training_data) % self.min_samples_retrain == 0:
            self._schedule_retraining(model_type)
    
    def predict_with_confidence(self, features: Dict[str, float], 
                              model_type: str) -> PredictionResult:
        """Make prediction with confidence scoring."""
        
        if model_type not in self.models:
            raise ValueError(f"Model type {model_type} not found")
        
        model = self.models[model_type]
        scaler = self.scalers[model_type]
        
        # Prepare features
        feature_array = np.array(list(features.values())).reshape(1, -1)
        feature_names = list(features.keys())
        
        # Scale features if scaler is fitted
        try:
            feature_array_scaled = scaler.transform(feature_array)
        except:
            feature_array_scaled = feature_array
        
        # Make prediction
        try:
            if hasattr(model, 'predict_proba'):
                # Classification with probability
                prediction = model.predict(feature_array_scaled)[0]
                probabilities = model.predict_proba(feature_array_scaled)[0]
                confidence = np.max(probabilities)
            elif hasattr(model, 'decision_function'):
                # Anomaly detection
                prediction = model.predict(feature_array_scaled)[0]
                decision_score = model.decision_function(feature_array_scaled)[0]
                # Convert decision score to confidence (0-1)
                confidence = 1 / (1 + np.exp(-decision_score))
            else:
                # Regression or other
                prediction = model.predict(feature_array_scaled)[0]
                confidence = 0.5  # Default confidence for unsupported models
            
            # Generate explanation
            explanation = self._generate_prediction_explanation(
                features, prediction, confidence, model_type
            )
            
            result = PredictionResult(
                prediction=prediction,
                confidence=float(confidence),
                model_version=self.model_versions[model_type],
                features_used=feature_names,
                timestamp=datetime.now().isoformat(),
                explanation=explanation
            )
            
            # Store prediction for analysis
            self.prediction_history.append(asdict(result))
            
            self.logger.debug(f"Prediction made for {model_type}: {prediction} (confidence: {confidence:.3f})")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Prediction failed for {model_type}: {str(e)}")
            return PredictionResult(
                prediction=None,
                confidence=0.0,
                model_version=self.model_versions[model_type],
                features_used=feature_names,
                timestamp=datetime.now().isoformat(),
                explanation=f"Prediction failed: {str(e)}"
            )
    
    def _generate_prediction_explanation(self, features: Dict[str, float], 
                                       prediction: Any, 
                                       confidence: float, 
                                       model_type: str) -> str:
        """Generate human-readable explanation for prediction."""
        
        explanations = {
            'anomaly_detection': {
                1: f"Normal operation detected (confidence: {confidence:.1%}). All parameters within expected ranges.",
                -1: f"Anomaly detected (confidence: {confidence:.1%}). Unusual pattern in vehicle data suggests potential issue."
            },
            'fault_classification': {
                'engine': f"Engine-related fault predicted (confidence: {confidence:.1%}). Check engine parameters and diagnostics.",
                'transmission': f"Transmission issue predicted (confidence: {confidence:.1%}). Monitor shifting patterns and fluid levels.",
                'electrical': f"Electrical system fault predicted (confidence: {confidence:.1%}). Check battery, alternator, and wiring.",
                'emissions': f"Emissions system issue predicted (confidence: {confidence:.1%}). Check catalytic converter and sensors."
            },
            'performance_prediction': {
                'excellent': f"Excellent performance predicted (confidence: {confidence:.1%}). Vehicle operating optimally.",
                'good': f"Good performance predicted (confidence: {confidence:.1%}). Minor optimization opportunities exist.",
                'fair': f"Fair performance predicted (confidence: {confidence:.1%}). Some maintenance may be needed.",
                'poor': f"Poor performance predicted (confidence: {confidence:.1%}). Immediate attention recommended."
            }
        }
        
        if model_type in explanations:
            if prediction in explanations[model_type]:
                return explanations[model_type][prediction]
            else:
                return f"Prediction: {prediction} (confidence: {confidence:.1%})"
        
        return f"Model {model_type} prediction: {prediction} (confidence: {confidence:.1%})"
    
    def detect_model_drift(self, model_type: str) -> DriftDetectionResult:
        """Detect if model performance has drifted."""
        
        if model_type not in self.models:
            raise ValueError(f"Model type {model_type} not found")
        
        # Get recent predictions
        recent_predictions = [
            p for p in self.prediction_history[-self.drift_detection_window:]
            if p.get('model_type') == model_type
        ]
        
        if len(recent_predictions) < 50:
            return DriftDetectionResult(
                drift_detected=False,
                drift_score=0.0,
                affected_features=[],
                recommendation="Insufficient data for drift detection",
                timestamp=datetime.now().isoformat()
            )
        
        # Calculate confidence trend
        confidences = [p['confidence'] for p in recent_predictions]
        recent_avg_confidence = np.mean(confidences[-50:])
        historical_avg_confidence = np.mean(confidences[:-50]) if len(confidences) > 50 else recent_avg_confidence
        
        # Calculate drift score
        confidence_drift = abs(recent_avg_confidence - historical_avg_confidence)
        
        # Feature drift detection (simplified)
        feature_drifts = []
        if len(recent_predictions) > 100:
            # Analyze feature distributions
            recent_features = recent_predictions[-50:]
            historical_features = recent_predictions[-100:-50]
            
            # This is a simplified drift detection - in production, use more sophisticated methods
            for feature in recent_features[0].get('features_used', []):
                # Compare feature usage patterns
                recent_usage = sum(1 for p in recent_features if feature in p.get('features_used', []))
                historical_usage = sum(1 for p in historical_features if feature in p.get('features_used', []))
                
                if abs(recent_usage - historical_usage) > 10:
                    feature_drifts.append(feature)
        
        # Determine if drift is significant
        drift_threshold = 0.15
        drift_detected = confidence_drift > drift_threshold
        
        # Generate recommendation
        if drift_detected:
            recommendation = f"Model retraining recommended. Confidence dropped by {confidence_drift:.1%}."
            if feature_drifts:
                recommendation += f" Features showing drift: {', '.join(feature_drifts)}"
        else:
            recommendation = "Model performance stable. No immediate action required."
        
        result = DriftDetectionResult(
            drift_detected=drift_detected,
            drift_score=confidence_drift,
            affected_features=feature_drifts,
            recommendation=recommendation,
            timestamp=datetime.now().isoformat()
        )
        
        self.logger.info(f"Drift detection for {model_type}: drift={drift_detected}, score={confidence_drift:.3f}")
        
        return result
    
    def retrain_model(self, model_type: str, force: bool = False) -> bool:
        """Retrain a specific model with accumulated data."""
        
        if model_type not in self.models:
            raise ValueError(f"Model type {model_type} not found")
        
        # Get training data for this model
        model_data = self.training_data[self.training_data['model_type'] == model_type].copy()
        
        if len(model_data) < self.min_samples_retrain and not force:
            self.logger.warning(f"Insufficient data for retraining {model_type}: {len(model_data)} samples")
            return False
        
        try:
            # Prepare features and targets
            feature_columns = [col for col in model_data.columns 
                             if col not in ['timestamp', 'model_type', 'target'] and not col.startswith('meta_')]
            
            if len(feature_columns) == 0:
                self.logger.error(f"No feature columns found for {model_type}")
                return False
            
            X = model_data[feature_columns].fillna(0)
            y = model_data['target']
            
            # Handle different target types
            if model_type == 'fault_classification' or model_type == 'performance_prediction':
                # Encode categorical targets
                y_encoded = self.encoders[model_type].fit_transform(y.astype(str))
            else:
                y_encoded = y
            
            # Split data
            if len(X) > 20:
                X_train, X_test, y_train, y_test = train_test_split(
                    X, y_encoded, test_size=0.2, random_state=42
                )
            else:
                X_train, X_test, y_train, y_test = X, X, y_encoded, y_encoded
            
            # Scale features
            X_train_scaled = self.scalers[model_type].fit_transform(X_train)
            X_test_scaled = self.scalers[model_type].transform(X_test)
            
            # Train model
            model = self.models[model_type]
            model.fit(X_train_scaled, y_train)
            
            # Evaluate model
            if len(X_test) > 0:
                y_pred = model.predict(X_test_scaled)
                
                if model_type != 'anomaly_detection':
                    accuracy = accuracy_score(y_test, y_pred)
                    precision = precision_score(y_test, y_pred, average='weighted', zero_division=0)
                    recall = recall_score(y_test, y_pred, average='weighted', zero_division=0)
                    f1 = f1_score(y_test, y_pred, average='weighted', zero_division=0)
                else:
                    # For anomaly detection, use different metrics
                    accuracy = accuracy_score(y_test, y_pred)
                    precision = recall = f1 = accuracy
                
                # Calculate average confidence
                if hasattr(model, 'predict_proba'):
                    probabilities = model.predict_proba(X_test_scaled)
                    confidence_avg = np.mean(np.max(probabilities, axis=1))
                else:
                    confidence_avg = 0.8  # Default for models without probability
                
                # Store performance metrics
                metrics = ModelMetrics(
                    accuracy=accuracy,
                    precision=precision,
                    recall=recall,
                    f1_score=f1,
                    confidence_avg=confidence_avg,
                    sample_count=len(model_data),
                    timestamp=datetime.now().isoformat()
                )
                
                self.performance_history[model_type].append(asdict(metrics))
                
                # Update model version
                current_version = self.model_versions[model_type]
                version_parts = current_version.split('.')
                version_parts[1] = str(int(version_parts[1]) + 1)
                self.model_versions[model_type] = '.'.join(version_parts)
                
                # Save model
                self._save_model(model_type)
                
                self.logger.info(f"Model {model_type} retrained successfully. "
                               f"Accuracy: {accuracy:.3f}, Samples: {len(model_data)}")
                
                return True
            
        except Exception as e:
            self.logger.error(f"Retraining failed for {model_type}: {str(e)}")
            return False
        
        return False
    
    def _save_model(self, model_type: str):
        """Save model, scaler, and encoder to disk."""
        model_path = self.model_dir / f"{model_type}_model.joblib"
        scaler_path = self.model_dir / f"{model_type}_scaler.joblib"
        encoder_path = self.model_dir / f"{model_type}_encoder.joblib"
        
        joblib.dump(self.models[model_type], model_path)
        joblib.dump(self.scalers[model_type], scaler_path)
        joblib.dump(self.encoders[model_type], encoder_path)
        
        # Save metadata
        metadata = {
            'version': self.model_versions[model_type],
            'last_trained': datetime.now().isoformat(),
            'performance_history': self.performance_history[model_type]
        }
        
        metadata_path = self.model_dir / f"{model_type}_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def _load_model(self, model_type: str) -> bool:
        """Load model, scaler, and encoder from disk."""
        try:
            model_path = self.model_dir / f"{model_type}_model.joblib"
            scaler_path = self.model_dir / f"{model_type}_scaler.joblib"
            encoder_path = self.model_dir / f"{model_type}_encoder.joblib"
            metadata_path = self.model_dir / f"{model_type}_metadata.json"
            
            if all(p.exists() for p in [model_path, scaler_path, encoder_path]):
                self.models[model_type] = joblib.load(model_path)
                self.scalers[model_type] = joblib.load(scaler_path)
                self.encoders[model_type] = joblib.load(encoder_path)
                
                if metadata_path.exists():
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                    self.model_versions[model_type] = metadata.get('version', '1.0.0')
                    self.performance_history[model_type] = metadata.get('performance_history', [])
                
                self.logger.info(f"Loaded model {model_type} version {self.model_versions[model_type]}")
                return True
        
        except Exception as e:
            self.logger.error(f"Failed to load model {model_type}: {str(e)}")
        
        return False
    
    def _schedule_retraining(self, model_type: str):
        """Schedule model retraining."""
        # Check if enough time has passed since last retrain
        time_since_retrain = datetime.now() - self.last_retrain
        
        if time_since_retrain.total_seconds() > self.retrain_interval:
            self.logger.info(f"Scheduling retraining for {model_type}")
            # In a production system, this would queue the retraining job
            threading.Thread(target=self.retrain_model, args=(model_type,), daemon=True).start()
            self.last_retrain = datetime.now()
    
    def _start_background_retraining(self):
        """Start background retraining process."""
        def background_retrain():
            while self.auto_retrain_enabled:
                try:
                    # Check each model for retraining needs
                    for model_type in self.models.keys():
                        drift_result = self.detect_model_drift(model_type)
                        if drift_result.drift_detected:
                            self.logger.info(f"Drift detected for {model_type}, initiating retraining")
                            self.retrain_model(model_type)
                    
                    # Sleep for retrain interval
                    time.sleep(self.retrain_interval)
                
                except Exception as e:
                    self.logger.error(f"Background retraining error: {str(e)}")
                    time.sleep(60)  # Wait 1 minute before retrying
        
        threading.Thread(target=background_retrain, daemon=True).start()
        self.logger.info("Background retraining process started")
    
    def get_model_status(self) -> Dict[str, Any]:
        """Get status of all models."""
        status = {}
        
        for model_type in self.models.keys():
            recent_performance = self.performance_history[model_type][-1] if self.performance_history[model_type] else None
            
            status[model_type] = {
                'version': self.model_versions[model_type],
                'training_samples': len(self.training_data[self.training_data['model_type'] == model_type]),
                'recent_performance': recent_performance,
                'drift_status': asdict(self.detect_model_drift(model_type))
            }
        
        return status
    
    def add_feedback(self, prediction_id: str, correct_prediction: bool, actual_outcome: Any):
        """Add feedback for model improvement."""
        feedback = {
            'prediction_id': prediction_id,
            'correct_prediction': correct_prediction,
            'actual_outcome': actual_outcome,
            'timestamp': datetime.now().isoformat()
        }
        
        self.feedback_data.append(feedback)
        self.logger.info(f"Feedback added: correct={correct_prediction}")

# Example usage and testing
def test_enhanced_learning_system():
    """Test the enhanced learning system."""
    system = EnhancedLearningSystem()
    
    # Generate sample training data
    np.random.seed(42)
    for i in range(200):
        # Simulate OBD features
        features = {
            'engine_rpm': np.random.normal(2000, 500),
            'coolant_temp': np.random.normal(85, 10),
            'engine_load': np.random.normal(50, 20),
            'fuel_level': np.random.normal(60, 30)
        }
        
        # Simulate targets
        if i % 3 == 0:  # Anomaly detection
            target = 1 if features['coolant_temp'] < 100 else -1
            system.add_training_data(features, target, 'anomaly_detection')
        
        elif i % 3 == 1:  # Fault classification
            if features['coolant_temp'] > 95:
                target = 'engine'
            elif features['engine_load'] > 80:
                target = 'transmission'
            else:
                target = 'normal'
            system.add_training_data(features, target, 'fault_classification')
        
        else:  # Performance prediction
            if features['engine_rpm'] > 2500:
                target = 'excellent'
            elif features['engine_rpm'] > 1500:
                target = 'good'
            else:
                target = 'fair'
            system.add_training_data(features, target, 'performance_prediction')
    
    # Test predictions
    test_features = {
        'engine_rpm': 2200,
        'coolant_temp': 88,
        'engine_load': 45,
        'fuel_level': 70
    }
    
    # Make predictions
    anomaly_result = system.predict_with_confidence(test_features, 'anomaly_detection')
    fault_result = system.predict_with_confidence(test_features, 'fault_classification')
    performance_result = system.predict_with_confidence(test_features, 'performance_prediction')
    
    print("=== ENHANCED LEARNING SYSTEM TEST ===")
    print(f"Anomaly Detection: {anomaly_result.prediction} (confidence: {anomaly_result.confidence:.3f})")
    print(f"Fault Classification: {fault_result.prediction} (confidence: {fault_result.confidence:.3f})")
    print(f"Performance Prediction: {performance_result.prediction} (confidence: {performance_result.confidence:.3f})")
    
    # Test drift detection
    drift_result = system.detect_model_drift('anomaly_detection')
    print(f"\\nDrift Detection: {drift_result.drift_detected} (score: {drift_result.drift_score:.3f})")
    
    # Get model status
    status = system.get_model_status()
    print(f"\\nModel Status: {len(status)} models active")
    
    return system

if __name__ == "__main__":
    test_enhanced_learning_system()
