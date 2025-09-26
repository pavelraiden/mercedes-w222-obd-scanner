"""
Enhanced Machine Learning Model Trainer for Mercedes W222 OBD Scanner
Supports multiple ML algorithms for anomaly detection and predictive maintenance
"""

import os
import json
import logging
import hashlib
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import joblib

# ML imports
from sklearn.ensemble import IsolationForest, RandomForestRegressor
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.model_selection import train_test_split, GridSearchCV, TimeSeriesSplit
from sklearn.metrics import classification_report, mean_squared_error, r2_score
from sklearn.cluster import DBSCAN
from sklearn.decomposition import PCA
from sklearn.pipeline import Pipeline

# Additional ML models
try:
    from sklearn.ensemble import GradientBoostingRegressor
    from sklearn.svm import OneClassSVM

    ADVANCED_ML_AVAILABLE = True
except ImportError:
    ADVANCED_ML_AVAILABLE = False

from ..inference.anomaly_detector import AnomalyDetector
from ...data.database_manager import DatabaseManager


class EnhancedModelTrainer:
    """Enhanced ML Model Trainer with multiple algorithms and validation"""

    def __init__(
        self, db_manager: DatabaseManager, models_dir: str = "mercedes_obd_scanner/ml/models"
    ):
        self.db_manager = db_manager
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)

        # Model configurations
        self.model_configs = {
            "isolation_forest": {
                "class": IsolationForest,
                "params": {"contamination": 0.1, "random_state": 42, "n_estimators": 100},
                "param_grid": {
                    "contamination": [0.05, 0.1, 0.15, 0.2],
                    "n_estimators": [50, 100, 200],
                },
            },
            "one_class_svm": {
                "class": OneClassSVM if ADVANCED_ML_AVAILABLE else None,
                "params": {"kernel": "rbf", "gamma": "scale", "nu": 0.1},
                "param_grid": {
                    "gamma": ["scale", "auto", 0.001, 0.01, 0.1],
                    "nu": [0.05, 0.1, 0.15, 0.2],
                },
            },
        }

        # Predictive model configurations
        self.predictive_configs = {
            "random_forest": {
                "class": RandomForestRegressor,
                "params": {"n_estimators": 100, "random_state": 42, "max_depth": 10},
                "param_grid": {
                    "n_estimators": [50, 100, 200],
                    "max_depth": [5, 10, 15, None],
                    "min_samples_split": [2, 5, 10],
                },
            },
            "gradient_boosting": {
                "class": GradientBoostingRegressor if ADVANCED_ML_AVAILABLE else None,
                "params": {
                    "n_estimators": 100,
                    "learning_rate": 0.1,
                    "max_depth": 6,
                    "random_state": 42,
                },
                "param_grid": {
                    "n_estimators": [50, 100, 200],
                    "learning_rate": [0.05, 0.1, 0.15],
                    "max_depth": [3, 6, 9],
                },
            },
        }

        # Feature engineering parameters
        self.feature_windows = [5, 10, 20, 50]  # Rolling window sizes
        self.lag_features = [1, 2, 3, 5, 10]  # Lag features

    def prepare_training_data(
        self, vehicle_id: str = None, days_back: int = 30, parameter_names: List[str] = None
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Prepare comprehensive training data with feature engineering"""

        # Define key parameters if not specified
        if parameter_names is None:
            parameter_names = [
                "ENGINE_RPM",
                "COOLANT_TEMP",
                "ENGINE_LOAD",
                "SPEED",
                "FUEL_LEVEL",
                "OIL_PRESSURE",
                "TRANS_TEMP",
                "AIR_PRESSURE_FL",
                "AIR_PRESSURE_FR",
            ]

        # Get raw data
        raw_data = self.db_manager.get_training_data(
            parameter_names=parameter_names, vehicle_id=vehicle_id, days_back=days_back
        )

        if raw_data.empty:
            raise ValueError("No training data available")

        self.logger.info(f"Retrieved {len(raw_data)} raw data points")

        # Pivot data to create feature matrix
        feature_data = raw_data.pivot_table(
            index=["timestamp", "session_id"],
            columns="parameter_name",
            values="value",
            aggfunc="mean",
        ).reset_index()

        # Sort by timestamp
        feature_data = feature_data.sort_values("timestamp")

        # Feature engineering
        engineered_features = self._engineer_features(feature_data, parameter_names)

        # Data quality metrics
        data_info = {
            "total_samples": len(engineered_features),
            "feature_count": len(engineered_features.columns)
            - 2,  # Exclude timestamp and session_id
            "date_range": {
                "start": feature_data["timestamp"].min(),
                "end": feature_data["timestamp"].max(),
            },
            "missing_data_percentage": engineered_features.isnull().sum().sum()
            / (engineered_features.shape[0] * engineered_features.shape[1])
            * 100,
            "parameter_coverage": {
                param: (feature_data[param].notna().sum() / len(feature_data)) * 100
                for param in parameter_names
                if param in feature_data.columns
            },
        }

        self.logger.info(
            f"Engineered {data_info['feature_count']} features from {data_info['total_samples']} samples"
        )

        return engineered_features, data_info

    def _engineer_features(self, data: pd.DataFrame, parameter_names: List[str]) -> pd.DataFrame:
        """Advanced feature engineering for automotive data"""

        engineered_data = data.copy()

        # Rolling statistics for each parameter
        for param in parameter_names:
            if param in data.columns:
                for window in self.feature_windows:
                    # Rolling mean, std, min, max
                    engineered_data[f"{param}_rolling_mean_{window}"] = (
                        data[param].rolling(window=window).mean()
                    )
                    engineered_data[f"{param}_rolling_std_{window}"] = (
                        data[param].rolling(window=window).std()
                    )
                    engineered_data[f"{param}_rolling_min_{window}"] = (
                        data[param].rolling(window=window).min()
                    )
                    engineered_data[f"{param}_rolling_max_{window}"] = (
                        data[param].rolling(window=window).max()
                    )

                    # Rolling percentiles
                    engineered_data[f"{param}_rolling_q25_{window}"] = (
                        data[param].rolling(window=window).quantile(0.25)
                    )
                    engineered_data[f"{param}_rolling_q75_{window}"] = (
                        data[param].rolling(window=window).quantile(0.75)
                    )

                # Lag features
                for lag in self.lag_features:
                    engineered_data[f"{param}_lag_{lag}"] = data[param].shift(lag)

                # Rate of change
                engineered_data[f"{param}_rate_of_change"] = data[param].pct_change()
                engineered_data[f"{param}_diff"] = data[param].diff()

        # Cross-parameter features (automotive-specific)
        if "ENGINE_RPM" in data.columns and "SPEED" in data.columns:
            # Engine efficiency indicator
            engineered_data["rpm_speed_ratio"] = data["ENGINE_RPM"] / (data["SPEED"] + 1)

        if "ENGINE_LOAD" in data.columns and "ENGINE_RPM" in data.columns:
            # Engine stress indicator
            engineered_data["load_rpm_product"] = data["ENGINE_LOAD"] * data["ENGINE_RPM"]

        if "COOLANT_TEMP" in data.columns and "ENGINE_LOAD" in data.columns:
            # Thermal efficiency
            engineered_data["temp_load_ratio"] = data["COOLANT_TEMP"] / (data["ENGINE_LOAD"] + 1)

        if "AIR_PRESSURE_FL" in data.columns and "AIR_PRESSURE_FR" in data.columns:
            # Suspension balance
            engineered_data["air_pressure_diff"] = abs(
                data["AIR_PRESSURE_FL"] - data["AIR_PRESSURE_FR"]
            )
            engineered_data["air_pressure_avg"] = (
                data["AIR_PRESSURE_FL"] + data["AIR_PRESSURE_FR"]
            ) / 2

        # Time-based features
        if "timestamp" in data.columns:
            engineered_data["timestamp"] = pd.to_datetime(engineered_data["timestamp"])
            engineered_data["hour"] = engineered_data["timestamp"].dt.hour
            engineered_data["day_of_week"] = engineered_data["timestamp"].dt.dayofweek
            engineered_data["is_weekend"] = engineered_data["day_of_week"].isin([5, 6]).astype(int)

        # Remove rows with too many NaN values (from rolling windows)
        engineered_data = engineered_data.dropna(thresh=len(engineered_data.columns) * 0.7)

        return engineered_data

    def train_anomaly_detection_model(
        self,
        training_data: pd.DataFrame,
        model_type: str = "isolation_forest",
        optimize_hyperparameters: bool = True,
    ) -> Dict[str, Any]:
        """Train anomaly detection model with hyperparameter optimization"""

        if model_type not in self.model_configs:
            raise ValueError(f"Unknown model type: {model_type}")

        config = self.model_configs[model_type]
        if config["class"] is None:
            raise ValueError(f"Model {model_type} not available")

        # Prepare features (exclude timestamp and session_id)
        feature_columns = [
            col for col in training_data.columns if col not in ["timestamp", "session_id"]
        ]
        X = training_data[feature_columns].fillna(0)

        # Scale features
        scaler = RobustScaler()
        X_scaled = scaler.fit_transform(X)

        # Hyperparameter optimization
        if optimize_hyperparameters and len(X) > 100:
            self.logger.info(f"Optimizing hyperparameters for {model_type}")

            # Use TimeSeriesSplit for time series data
            cv = TimeSeriesSplit(n_splits=3)

            model = config["class"](**config["params"])
            grid_search = GridSearchCV(
                model,
                config["param_grid"],
                cv=cv,
                scoring="neg_mean_squared_error",
                n_jobs=-1,
                verbose=1,
            )

            # For unsupervised models, we need to create pseudo-labels
            # Use distance from median as proxy for anomaly score
            median_point = np.median(X_scaled, axis=0)
            distances = np.linalg.norm(X_scaled - median_point, axis=1)
            y_pseudo = (distances > np.percentile(distances, 90)).astype(int)

            grid_search.fit(X_scaled, y_pseudo)
            best_model = grid_search.best_estimator_
            best_params = grid_search.best_params_

            self.logger.info(f"Best parameters: {best_params}")
        else:
            best_model = config["class"](**config["params"])
            best_model.fit(X_scaled)
            best_params = config["params"]

        # Create pipeline
        pipeline = Pipeline([("scaler", scaler), ("model", best_model)])

        # Evaluate model
        anomaly_scores = pipeline.decision_function(X)
        predictions = pipeline.predict(X)

        # Calculate metrics
        anomaly_rate = (predictions == -1).sum() / len(predictions)
        score_stats = {
            "mean": float(np.mean(anomaly_scores)),
            "std": float(np.std(anomaly_scores)),
            "min": float(np.min(anomaly_scores)),
            "max": float(np.max(anomaly_scores)),
            "percentiles": {
                "5": float(np.percentile(anomaly_scores, 5)),
                "25": float(np.percentile(anomaly_scores, 25)),
                "75": float(np.percentile(anomaly_scores, 75)),
                "95": float(np.percentile(anomaly_scores, 95)),
            },
        }

        # Save model
        model_path = (
            self.models_dir / f"anomaly_{model_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl"
        )
        joblib.dump(pipeline, model_path)

        # Calculate data hash for version tracking
        data_hash = hashlib.sha256(pd.util.hash_pandas_object(training_data).values).hexdigest()

        # Save model metadata
        performance_metrics = {
            "anomaly_rate": float(anomaly_rate),
            "score_statistics": score_stats,
            "feature_count": len(feature_columns),
            "training_samples": len(X),
            "best_parameters": best_params,
        }

        self.db_manager.save_ml_model_metadata(
            model_name=f"anomaly_{model_type}",
            model_type="anomaly_detection",
            version=datetime.now().strftime("%Y%m%d_%H%M%S"),
            training_data_hash=data_hash,
            performance_metrics=performance_metrics,
            model_path=str(model_path),
        )

        self.logger.info(
            f"Anomaly detection model trained successfully. Anomaly rate: {anomaly_rate:.3f}"
        )

        return {
            "model_path": str(model_path),
            "performance_metrics": performance_metrics,
            "feature_columns": feature_columns,
            "model_type": model_type,
        }

    def train_predictive_maintenance_model(
        self,
        training_data: pd.DataFrame,
        target_parameter: str,
        model_type: str = "random_forest",
        prediction_horizon: int = 10,
    ) -> Dict[str, Any]:
        """Train predictive maintenance model"""

        if model_type not in self.predictive_configs:
            raise ValueError(f"Unknown predictive model type: {model_type}")

        config = self.predictive_configs[model_type]
        if config["class"] is None:
            raise ValueError(f"Model {model_type} not available")

        # Prepare features and target
        feature_columns = [
            col
            for col in training_data.columns
            if col not in ["timestamp", "session_id", target_parameter]
        ]

        if target_parameter not in training_data.columns:
            raise ValueError(f"Target parameter {target_parameter} not found in training data")

        X = training_data[feature_columns].fillna(0)
        y = training_data[target_parameter].shift(-prediction_horizon).fillna(method="ffill")

        # Remove samples where target is NaN
        valid_indices = ~y.isna()
        X = X[valid_indices]
        y = y[valid_indices]

        if len(X) < 50:
            raise ValueError("Insufficient data for predictive modeling")

        # Split data (time-aware)
        split_index = int(len(X) * 0.8)
        X_train, X_test = X.iloc[:split_index], X.iloc[split_index:]
        y_train, y_test = y.iloc[:split_index], y.iloc[split_index:]

        # Scale features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        # X_test_scaled = scaler.transform(X_test)

        # Train model with hyperparameter optimization
        self.logger.info(f"Training predictive model for {target_parameter}")

        cv = TimeSeriesSplit(n_splits=3)
        model = config["class"](**config["params"])

        grid_search = GridSearchCV(
            model,
            config["param_grid"],
            cv=cv,
            scoring="neg_mean_squared_error",
            n_jobs=-1,
            verbose=1,
        )

        grid_search.fit(X_train_scaled, y_train)
        best_model = grid_search.best_estimator_

        # Create pipeline
        pipeline = Pipeline([("scaler", scaler), ("model", best_model)])

        # Final training on all training data
        pipeline.fit(X_train, y_train)

        # Evaluate model
        y_pred_train = pipeline.predict(X_train)
        y_pred_test = pipeline.predict(X_test)

        train_mse = mean_squared_error(y_train, y_pred_train)
        test_mse = mean_squared_error(y_test, y_pred_test)
        train_r2 = r2_score(y_train, y_pred_train)
        test_r2 = r2_score(y_test, y_pred_test)

        # Feature importance (if available)
        feature_importance = {}
        if hasattr(best_model, "feature_importances_"):
            feature_importance = dict(zip(feature_columns, best_model.feature_importances_))
            # Sort by importance
            feature_importance = dict(
                sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)
            )

        # Save model
        model_path = (
            self.models_dir
            / f"predictive_{target_parameter}_{model_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl"
        )
        joblib.dump(pipeline, model_path)

        # Performance metrics
        performance_metrics = {
            "train_mse": float(train_mse),
            "test_mse": float(test_mse),
            "train_r2": float(train_r2),
            "test_r2": float(test_r2),
            "prediction_horizon": prediction_horizon,
            "feature_count": len(feature_columns),
            "training_samples": len(X_train),
            "test_samples": len(X_test),
            "best_parameters": grid_search.best_params_,
            "feature_importance": {k: float(v) for k, v in feature_importance.items()},
        }

        # Calculate data hash
        data_hash = hashlib.sha256(pd.util.hash_pandas_object(training_data).values).hexdigest()

        # Save model metadata
        self.db_manager.save_ml_model_metadata(
            model_name=f"predictive_{target_parameter}_{model_type}",
            model_type="predictive_maintenance",
            version=datetime.now().strftime("%Y%m%d_%H%M%S"),
            training_data_hash=data_hash,
            performance_metrics=performance_metrics,
            model_path=str(model_path),
        )

        self.logger.info(
            f"Predictive model trained. Test R²: {test_r2:.3f}, Test MSE: {test_mse:.3f}"
        )

        return {
            "model_path": str(model_path),
            "performance_metrics": performance_metrics,
            "feature_columns": feature_columns,
            "target_parameter": target_parameter,
            "model_type": model_type,
        }

    def train_all_models(self, vehicle_id: str = None, days_back: int = 30) -> Dict[str, Any]:
        """Train all models for comprehensive analysis"""

        results = {
            "training_timestamp": datetime.now().isoformat(),
            "vehicle_id": vehicle_id,
            "days_back": days_back,
            "models_trained": [],
            "errors": [],
        }

        try:
            # Prepare training data
            training_data, data_info = self.prepare_training_data(vehicle_id, days_back)
            results["data_info"] = data_info

            # Train anomaly detection models
            for model_type in ["isolation_forest"]:  # Start with most reliable
                try:
                    model_result = self.train_anomaly_detection_model(training_data, model_type)
                    results["models_trained"].append(
                        {
                            "type": "anomaly_detection",
                            "model_type": model_type,
                            "result": model_result,
                        }
                    )
                except Exception as e:
                    error_msg = f"Failed to train {model_type}: {str(e)}"
                    self.logger.error(error_msg)
                    results["errors"].append(error_msg)

            # Train predictive maintenance models for key parameters
            key_parameters = ["COOLANT_TEMP", "ENGINE_LOAD", "OIL_PRESSURE"]
            for param in key_parameters:
                if param in training_data.columns:
                    try:
                        model_result = self.train_predictive_maintenance_model(
                            training_data, param, "random_forest"
                        )
                        results["models_trained"].append(
                            {
                                "type": "predictive_maintenance",
                                "target_parameter": param,
                                "result": model_result,
                            }
                        )
                    except Exception as e:
                        error_msg = f"Failed to train predictive model for {param}: {str(e)}"
                        self.logger.error(error_msg)
                        results["errors"].append(error_msg)

        except Exception as e:
            error_msg = f"Failed to prepare training data: {str(e)}"
            self.logger.error(error_msg)
            results["errors"].append(error_msg)

        self.logger.info(
            f"Training completed. {len(results['models_trained'])} models trained, {len(results['errors'])} errors"
        )

        return results

    def validate_model_performance(
        self, model_path: str, validation_data: pd.DataFrame
    ) -> Dict[str, Any]:
        """Validate model performance on new data"""

        try:
            # Load model
            model = joblib.load(model_path)

            # Prepare validation data
            feature_columns = [
                col for col in validation_data.columns if col not in ["timestamp", "session_id"]
            ]
            X_val = validation_data[feature_columns].fillna(0)

            # Make predictions
            if hasattr(model, "decision_function"):
                # Anomaly detection model
                scores = model.decision_function(X_val)
                predictions = model.predict(X_val)

                validation_results = {
                    "model_type": "anomaly_detection",
                    "validation_samples": len(X_val),
                    "anomaly_rate": float((predictions == -1).sum() / len(predictions)),
                    "score_statistics": {
                        "mean": float(np.mean(scores)),
                        "std": float(np.std(scores)),
                        "min": float(np.min(scores)),
                        "max": float(np.max(scores)),
                    },
                }
            else:
                # Predictive model - need target values for proper validation
                validation_results = {
                    "model_type": "predictive",
                    "validation_samples": len(X_val),
                    "note": "Predictive model validation requires target values",
                }

            return validation_results

        except Exception as e:
            return {"error": str(e), "model_path": model_path}

    def get_model_recommendations(self, performance_results: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on model performance"""

        recommendations = []

        # Check data quality
        if "data_info" in performance_results:
            data_info = performance_results["data_info"]

            if data_info["missing_data_percentage"] > 20:
                recommendations.append(
                    "High missing data percentage detected. Consider improving data collection."
                )

            if data_info["total_samples"] < 1000:
                recommendations.append(
                    "Limited training data. Collect more data for better model performance."
                )

        # Check model performance
        for model_info in performance_results.get("models_trained", []):
            if model_info["type"] == "anomaly_detection":
                metrics = model_info["result"]["performance_metrics"]
                anomaly_rate = metrics["anomaly_rate"]

                if anomaly_rate > 0.3:
                    recommendations.append(
                        f"High anomaly rate ({anomaly_rate:.1%}) detected. Review model parameters."
                    )
                elif anomaly_rate < 0.01:
                    recommendations.append(
                        f"Very low anomaly rate ({anomaly_rate:.1%}). Model may be too conservative."
                    )

            elif model_info["type"] == "predictive_maintenance":
                metrics = model_info["result"]["performance_metrics"]
                test_r2 = metrics["test_r2"]

                if test_r2 < 0.5:
                    param = model_info["target_parameter"]
                    recommendations.append(
                        f"Low predictive accuracy for {param} (R²={test_r2:.2f}). Consider feature engineering."
                    )

        # Check for errors
        if performance_results.get("errors"):
            recommendations.append(
                "Some models failed to train. Check data quality and model configurations."
            )

        if not recommendations:
            recommendations.append("All models trained successfully with good performance metrics.")

        return recommendations
