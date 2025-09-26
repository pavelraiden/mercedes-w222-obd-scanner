"""
Comprehensive Production Quality Assurance Tests for Mercedes W222 OBD Scanner
Tests all critical components for commercial-grade reliability
"""

import os
import sys
import pytest
import asyncio
import sqlite3
import tempfile
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import numpy as np

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mercedes_obd_scanner.data.database_manager import DatabaseManager, ParameterData, AnomalyRecord
from mercedes_obd_scanner.trip_analyzer.enhanced_trip_analyzer import (
    EnhancedTripAnalyzer,
    TripAnalysisResult,
)
from mercedes_obd_scanner.ml.training.enhanced_model_trainer import EnhancedModelTrainer
from mercedes_obd_scanner.ml.inference.enhanced_anomaly_detector import (
    EnhancedAnomalyDetector,
    AnomalyResult,
)


class TestDatabaseManagerProduction:
    """Test database manager for production reliability"""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        db_manager = DatabaseManager(db_path)
        yield db_manager

        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)

    def test_database_initialization(self, temp_db):
        """Test database initialization and schema creation"""
        # Check if all tables exist
        with sqlite3.connect(temp_db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

        expected_tables = [
            "obd_parameters",
            "sessions",
            "trip_analysis",
            "anomaly_records",
            "ml_models",
            "vehicle_profiles",
            "maintenance_predictions",
            "performance_benchmarks",
        ]

        for table in expected_tables:
            assert table in tables, f"Table {table} not created"

    def test_session_management(self, temp_db):
        """Test session creation and management"""
        # Create session
        session_id = temp_db.create_session(vehicle_id="TEST123", protocol="DEMO")
        assert session_id.startswith("session_")

        # Log parameters
        param_data = ParameterData(
            name="ENGINE_RPM",
            value=2000.0,
            unit="rpm",
            timestamp=datetime.now(),
            session_id=session_id,
            vehicle_id="TEST123",
        )
        temp_db.log_parameter(param_data)

        # End session with statistics
        trip_stats = {
            "distance": 50.0,
            "fuel_consumed": 4.5,
            "avg_speed": 60.0,
            "max_speed": 120.0,
            "engine_hours": 0.8,
        }
        temp_db.end_session(session_id, "Test session", trip_stats)

        # Verify session summary
        summary = temp_db.get_session_summary(session_id)
        assert summary is not None
        assert summary["session_info"]["trip_distance"] == 50.0
        assert "ENGINE_RPM" in summary["parameters"]

    def test_anomaly_logging(self, temp_db):
        """Test anomaly detection logging"""
        session_id = temp_db.create_session()

        anomaly = AnomalyRecord(
            session_id=session_id,
            parameter_name="COOLANT_TEMP",
            value=120.0,
            anomaly_score=0.95,
            timestamp=datetime.now(),
            severity="high",
            description="Temperature too high",
        )

        temp_db.log_anomaly(anomaly)

        # Verify anomaly was logged
        with sqlite3.connect(temp_db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM anomaly_records WHERE session_id = ?", (session_id,))
            result = cursor.fetchone()

        assert result is not None
        assert result[2] == "COOLANT_TEMP"  # parameter_name
        assert result[5] == "high"  # severity

    def test_vehicle_profile_management(self, temp_db):
        """Test vehicle profile creation and updates"""
        vehicle_id = "WDD2220391A123456"

        profile_data = {
            "make": "Mercedes-Benz",
            "model": "S-Class",
            "year": 2018,
            "engine_type": "V8",
            "transmission_type": "Automatic",
            "mileage": 50000,
            "baseline_parameters": {
                "ENGINE_RPM": {"mean": 2000, "std": 500},
                "COOLANT_TEMP": {"mean": 90, "std": 5},
            },
        }

        temp_db.update_vehicle_profile(vehicle_id, profile_data)

        # Retrieve and verify
        retrieved_profile = temp_db.get_vehicle_profile(vehicle_id)
        assert retrieved_profile is not None
        assert retrieved_profile["make"] == "Mercedes-Benz"
        assert retrieved_profile["baseline_parameters"]["ENGINE_RPM"]["mean"] == 2000

    def test_training_data_preparation(self, temp_db):
        """Test training data preparation for ML"""
        session_id = temp_db.create_session(vehicle_id="TEST123")

        # Add sample data
        parameters = ["ENGINE_RPM", "COOLANT_TEMP", "ENGINE_LOAD"]
        for i in range(100):
            for param in parameters:
                param_data = ParameterData(
                    name=param,
                    value=np.random.normal(2000 if param == "ENGINE_RPM" else 90, 100),
                    unit=(
                        "rpm" if param == "ENGINE_RPM" else "°C" if param == "COOLANT_TEMP" else "%"
                    ),
                    timestamp=datetime.now() - timedelta(minutes=i),
                    session_id=session_id,
                    vehicle_id="TEST123",
                )
                temp_db.log_parameter(param_data)

        # Get training data
        training_data = temp_db.get_training_data(parameters, vehicle_id="TEST123", days_back=1)

        assert not training_data.empty
        assert len(training_data) > 0
        assert all(param in training_data["parameter_name"].values for param in parameters)

    def test_database_performance(self, temp_db):
        """Test database performance under load"""
        session_id = temp_db.create_session()

        # Measure insertion performance
        start_time = time.time()

        for i in range(1000):
            param_data = ParameterData(
                name="ENGINE_RPM",
                value=2000 + np.random.normal(0, 100),
                unit="rpm",
                timestamp=datetime.now(),
                session_id=session_id,
            )
            temp_db.log_parameter(param_data)

        insertion_time = time.time() - start_time

        # Should be able to insert 1000 records in reasonable time (< 5 seconds)
        assert insertion_time < 5.0, f"Database insertion too slow: {insertion_time:.2f}s"

        # Test query performance
        start_time = time.time()
        summary = temp_db.get_session_summary(session_id)
        query_time = time.time() - start_time

        assert query_time < 1.0, f"Database query too slow: {query_time:.2f}s"
        assert summary is not None


class TestEnhancedTripAnalyzer:
    """Test enhanced trip analyzer with AI integration"""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        db_manager = DatabaseManager(db_path)
        yield db_manager

        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)

    @pytest.fixture
    def trip_analyzer(self, temp_db):
        """Create trip analyzer instance"""
        return EnhancedTripAnalyzer(temp_db)

    def test_trip_analyzer_initialization(self, trip_analyzer):
        """Test trip analyzer initialization"""
        assert trip_analyzer.db_manager is not None
        assert trip_analyzer.claude_model is not None
        assert trip_analyzer.max_tokens > 0

    def test_data_preparation(self, trip_analyzer, temp_db):
        """Test trip data preparation"""
        # Create test session with data
        session_id = temp_db.create_session(vehicle_id="TEST123")

        # Add sample parameters
        parameters = {
            "ENGINE_RPM": 2500,
            "COOLANT_TEMP": 95,
            "ENGINE_LOAD": 45,
            "SPEED": 80,
            "FUEL_LEVEL": 75,
        }

        for param, value in parameters.items():
            param_data = ParameterData(
                name=param,
                value=value,
                unit="rpm" if param == "ENGINE_RPM" else "°C" if param == "COOLANT_TEMP" else "%",
                timestamp=datetime.now(),
                session_id=session_id,
                vehicle_id="TEST123",
            )
            temp_db.log_parameter(param_data)

        # End session
        temp_db.end_session(session_id, trip_stats={"distance": 100, "fuel_consumed": 8})

        # Get session summary and prepare data
        session_summary = temp_db.get_session_summary(session_id)
        analysis_data = trip_analyzer._prepare_analysis_data(session_summary, None)

        assert "engine_metrics" in analysis_data
        assert "fuel_efficiency" in analysis_data
        assert analysis_data["distance_km"] == 100
        assert analysis_data["fuel_consumed_liters"] == 8

    @pytest.mark.asyncio
    async def test_fallback_analysis(self, trip_analyzer, temp_db):
        """Test fallback analysis when Claude API is not available"""
        # Create test session

        # Mock session summary
        session_summary = {
            "session_info": {"trip_distance": 50, "fuel_consumed": 4},
            "parameters": {
                "ENGINE_RPM": {"avg": 2000, "max": 4000, "min": 800},
                "COOLANT_TEMP": {"avg": 90, "max": 95, "min": 85},
            },
            "anomalies": {"high": 1, "medium": 2},
            "duration_minutes": 60,
        }

        # Test fallback analysis
        analysis_data = trip_analyzer._prepare_analysis_data(session_summary, None)
        fallback_result = trip_analyzer._fallback_analysis(analysis_data)

        assert "main_analysis" in fallback_result
        assert "driving_score" in fallback_result
        assert "efficiency_score" in fallback_result
        assert "safety_score" in fallback_result
        assert fallback_result["confidence"] > 0

    def test_performance_scoring(self, trip_analyzer):
        """Test performance scoring algorithms"""
        # Mock analysis data
        analysis_data = {
            "fuel_efficiency": {"consumption_per_100km": 9.5},
            "engine_metrics": {"avg_rpm": 2200, "max_rpm": 4500},
            "anomalies": {"high": 0, "medium": 1, "low": 2},
        }

        # Mock Claude analysis
        claude_analysis = {"driving_score": 85, "efficiency_score": 78, "safety_score": 92}

        scores = trip_analyzer._calculate_performance_scores(analysis_data, claude_analysis)

        assert 0 <= scores["driving_score"] <= 100
        assert 0 <= scores["efficiency_score"] <= 100
        assert 0 <= scores["safety_score"] <= 100


class TestEnhancedAnomalyDetector:
    """Test enhanced anomaly detection system"""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        db_manager = DatabaseManager(db_path)
        yield db_manager

        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)

    @pytest.fixture
    def anomaly_detector(self, temp_db):
        """Create anomaly detector instance"""
        return EnhancedAnomalyDetector(temp_db)

    def test_threshold_anomaly_detection(self, anomaly_detector):
        """Test threshold-based anomaly detection"""
        # Test normal values
        normal_data = {"ENGINE_RPM": 2000, "COOLANT_TEMP": 90, "OIL_PRESSURE": 4.0}

        anomalies = anomaly_detector._detect_threshold_anomalies(normal_data, datetime.now())
        assert len(anomalies) == 0

        # Test abnormal values
        abnormal_data = {
            "ENGINE_RPM": 7000,  # Too high
            "COOLANT_TEMP": 120,  # Too high
            "OIL_PRESSURE": 1.0,  # Too low
        }

        anomalies = anomaly_detector._detect_threshold_anomalies(abnormal_data, datetime.now())
        assert len(anomalies) > 0

        # Check severity classification
        high_severity_count = sum(1 for a in anomalies if a.severity in ["high", "critical"])
        assert high_severity_count > 0

    def test_contextual_anomaly_detection(self, anomaly_detector):
        """Test contextual rule-based anomaly detection"""
        # Test high RPM with low speed (potential transmission issue)
        contextual_data = {"ENGINE_RPM": 4000, "SPEED": 20, "COOLANT_TEMP": 85, "ENGINE_LOAD": 30}

        anomalies = anomaly_detector._detect_contextual_anomalies(contextual_data, datetime.now())

        # Should detect high RPM at low speed
        rpm_speed_anomaly = any(a.anomaly_type == "contextual" for a in anomalies)
        assert rpm_speed_anomaly

    def test_pattern_anomaly_detection(self, anomaly_detector):
        """Test pattern-based anomaly detection"""
        session_id = "test_session"

        # Build historical data buffer
        for i in range(20):
            historical_data = {
                "ENGINE_RPM": 2000 + np.random.normal(0, 50),
                "COOLANT_TEMP": 90 + np.random.normal(0, 2),
                "timestamp": datetime.now() - timedelta(minutes=i),
            }
            anomaly_detector._update_data_buffer(
                session_id, historical_data, historical_data["timestamp"]
            )

        # Test with normal current data
        normal_current = {"ENGINE_RPM": 2050, "COOLANT_TEMP": 91}

        anomalies = anomaly_detector._detect_pattern_anomalies(
            session_id, normal_current, datetime.now()
        )
        assert len(anomalies) == 0

        # Test with anomalous current data
        anomalous_current = {
            "ENGINE_RPM": 4000,  # Significantly different from historical pattern
            "COOLANT_TEMP": 91,
        }

        anomalies = anomaly_detector._detect_pattern_anomalies(
            session_id, anomalous_current, datetime.now()
        )
        assert len(anomalies) > 0

        # Check that RPM anomaly was detected
        rpm_anomaly = any(a.parameter_name == "ENGINE_RPM" for a in anomalies)
        assert rpm_anomaly

    def test_comprehensive_anomaly_detection(self, anomaly_detector, temp_db):
        """Test comprehensive anomaly detection pipeline"""
        session_id = temp_db.create_session(vehicle_id="TEST123")

        # Test data with multiple anomaly types
        test_data = {
            "ENGINE_RPM": 6500,  # Threshold anomaly
            "SPEED": 25,  # Contextual anomaly (high RPM, low speed)
            "COOLANT_TEMP": 85,
            "ENGINE_LOAD": 40,
            "OIL_PRESSURE": 3.5,
        }

        anomalies = anomaly_detector.detect_anomalies(test_data, session_id, "TEST123")

        assert len(anomalies) > 0

        # Check different anomaly types are detected
        anomaly_types = {a.anomaly_type for a in anomalies}
        assert "threshold" in anomaly_types or "contextual" in anomaly_types

        # Verify anomalies were logged to database
        with sqlite3.connect(temp_db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM anomaly_records WHERE session_id = ?", (session_id,)
            )
            count = cursor.fetchone()[0]

        assert count > 0

    def test_vehicle_baseline_update(self, anomaly_detector, temp_db):
        """Test vehicle baseline parameter updates"""
        vehicle_id = "TEST123"

        # Create sample data
        data = []
        for i in range(50):
            data.append(
                {
                    "ENGINE_RPM": 2000 + np.random.normal(0, 100),
                    "COOLANT_TEMP": 90 + np.random.normal(0, 5),
                    "timestamp": datetime.now() - timedelta(minutes=i),
                }
            )

        df = pd.DataFrame(data)

        # Update baseline
        anomaly_detector.update_vehicle_baseline(vehicle_id, df)

        # Verify baseline was updated
        profile = temp_db.get_vehicle_profile(vehicle_id)
        assert profile is not None
        assert "baseline_parameters" in profile
        assert "ENGINE_RPM" in profile["baseline_parameters"]
        assert "mean" in profile["baseline_parameters"]["ENGINE_RPM"]


class TestMLModelTrainer:
    """Test ML model training system"""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database with sample data"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        db_manager = DatabaseManager(db_path)

        # Add sample training data
        session_id = db_manager.create_session(vehicle_id="TEST123")

        parameters = ["ENGINE_RPM", "COOLANT_TEMP", "ENGINE_LOAD", "SPEED"]
        for i in range(200):
            for param in parameters:
                base_value = {
                    "ENGINE_RPM": 2000,
                    "COOLANT_TEMP": 90,
                    "ENGINE_LOAD": 50,
                    "SPEED": 60,
                }[param]
                param_data = ParameterData(
                    name=param,
                    value=base_value + np.random.normal(0, base_value * 0.1),
                    unit=(
                        "rpm" if param == "ENGINE_RPM" else "°C" if param == "COOLANT_TEMP" else "%"
                    ),
                    timestamp=datetime.now() - timedelta(minutes=i),
                    session_id=session_id,
                    vehicle_id="TEST123",
                )
                db_manager.log_parameter(param_data)

        yield db_manager

        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)

    @pytest.fixture
    def model_trainer(self, temp_db):
        """Create model trainer instance"""
        return EnhancedModelTrainer(temp_db)

    def test_training_data_preparation(self, model_trainer):
        """Test training data preparation and feature engineering"""
        training_data, data_info = model_trainer.prepare_training_data(
            vehicle_id="TEST123", days_back=1
        )

        assert not training_data.empty
        assert data_info["total_samples"] > 0
        assert data_info["feature_count"] > 4  # Should have engineered features
        assert data_info["missing_data_percentage"] < 50  # Reasonable data quality

    def test_anomaly_model_training(self, model_trainer):
        """Test anomaly detection model training"""
        # Prepare training data
        training_data, _ = model_trainer.prepare_training_data(vehicle_id="TEST123", days_back=1)

        # Train model
        result = model_trainer.train_anomaly_detection_model(
            training_data,
            model_type="isolation_forest",
            optimize_hyperparameters=False,  # Skip optimization for speed
        )

        assert "model_path" in result
        assert "performance_metrics" in result
        assert os.path.exists(result["model_path"])

        # Check performance metrics
        metrics = result["performance_metrics"]
        assert "anomaly_rate" in metrics
        assert 0 <= metrics["anomaly_rate"] <= 1
        assert metrics["training_samples"] > 0

    def test_predictive_model_training(self, model_trainer):
        """Test predictive maintenance model training"""
        # Prepare training data
        training_data, _ = model_trainer.prepare_training_data(vehicle_id="TEST123", days_back=1)

        # Train predictive model for coolant temperature
        result = model_trainer.train_predictive_maintenance_model(
            training_data,
            target_parameter="COOLANT_TEMP",
            model_type="random_forest",
            prediction_horizon=5,
        )

        assert "model_path" in result
        assert "performance_metrics" in result
        assert os.path.exists(result["model_path"])

        # Check performance metrics
        metrics = result["performance_metrics"]
        assert "test_r2" in metrics
        assert "test_mse" in metrics
        assert metrics["training_samples"] > 0

    def test_model_recommendations(self, model_trainer):
        """Test model performance recommendations"""
        # Mock performance results
        performance_results = {
            "data_info": {"total_samples": 500, "missing_data_percentage": 15},
            "models_trained": [
                {
                    "type": "anomaly_detection",
                    "result": {"performance_metrics": {"anomaly_rate": 0.15}},
                },
                {
                    "type": "predictive_maintenance",
                    "target_parameter": "COOLANT_TEMP",
                    "result": {"performance_metrics": {"test_r2": 0.75}},
                },
            ],
            "errors": [],
        }

        recommendations = model_trainer.get_model_recommendations(performance_results)

        assert isinstance(recommendations, list)
        assert len(recommendations) > 0
        assert any("successfully" in rec.lower() for rec in recommendations)


class TestSystemIntegration:
    """Test system integration and end-to-end workflows"""

    def test_complete_workflow(self):
        """Test complete workflow from data collection to analysis"""
        # This would test the entire pipeline in a real scenario
        # For now, we'll test the basic integration points

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            # Initialize components
            db_manager = DatabaseManager(db_path)
            trip_analyzer = EnhancedTripAnalyzer(db_manager)
            anomaly_detector = EnhancedAnomalyDetector(db_manager)

            # Create session and add data
            session_id = db_manager.create_session(vehicle_id="INTEGRATION_TEST")

            # Simulate real-time data collection
            for i in range(10):
                data = {
                    "ENGINE_RPM": 2000 + np.random.normal(0, 100),
                    "COOLANT_TEMP": 90 + np.random.normal(0, 5),
                    "ENGINE_LOAD": 50 + np.random.normal(0, 10),
                    "SPEED": 60 + np.random.normal(0, 15),
                }

                # Log parameters
                for param, value in data.items():
                    param_data = ParameterData(
                        name=param,
                        value=value,
                        unit=(
                            "rpm"
                            if param == "ENGINE_RPM"
                            else "°C" if param == "COOLANT_TEMP" else "%"
                        ),
                        timestamp=datetime.now(),
                        session_id=session_id,
                        vehicle_id="INTEGRATION_TEST",
                    )
                    db_manager.log_parameter(param_data)

                # Detect anomalies
                anomalies = anomaly_detector.detect_anomalies(data, session_id, "INTEGRATION_TEST")

                # Verify anomalies are properly handled
                assert isinstance(anomalies, list)

            # End session
            db_manager.end_session(session_id, "Integration test")

            # Verify session summary
            summary = db_manager.get_session_summary(session_id)
            assert summary is not None
            assert len(summary["parameters"]) > 0

            # Test trip analysis preparation
            analysis_data = trip_analyzer._prepare_analysis_data(summary, None)
            assert "engine_metrics" in analysis_data

        finally:
            # Cleanup
            if os.path.exists(db_path):
                os.unlink(db_path)

    def test_error_handling(self):
        """Test system error handling and resilience"""
        # Test with invalid database path
        with pytest.raises(Exception):
            DatabaseManager("/invalid/path/database.db")

        # Test with empty data
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            db_manager = DatabaseManager(db_path)

            # Test getting summary for non-existent session
            summary = db_manager.get_session_summary("non_existent_session")
            assert summary is None

            # Test getting training data with no data
            training_data = db_manager.get_training_data(["ENGINE_RPM"], days_back=1)
            assert training_data.empty

        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
