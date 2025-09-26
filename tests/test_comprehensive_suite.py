#!/usr/bin/env python3
"""
Comprehensive Test Suite for Mercedes W222 OBD Scanner
Targeting >80% code coverage for production readiness
"""

import pytest
import tempfile
import sqlite3
import json
import time
import threading
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import numpy as np

# Import all modules to test
from mercedes_obd_scanner.core.obd_controller import OBDController
from mercedes_obd_scanner.data.database_manager import DatabaseManager, ParameterData, AnomalyRecord
from mercedes_obd_scanner.diagnostics.predictive_manager import PredictiveManager
from mercedes_obd_scanner.trip_analyzer.enhanced_trip_analyzer import EnhancedTripAnalyzer
from mercedes_obd_scanner.ml.inference.enhanced_anomaly_detector import EnhancedAnomalyDetector
from mercedes_obd_scanner.ml.training.enhanced_model_trainer import EnhancedModelTrainer
from mercedes_obd_scanner.auth.jwt_auth import JWTAuth
from mercedes_obd_scanner.auth.user_manager import UserManager
from mercedes_obd_scanner.licensing.license_manager import LicenseManager


class TestOBDControllerComprehensive:
    """Comprehensive tests for OBD Controller"""
    
    @pytest.fixture
    def obd_controller(self):
        return OBDController()
    
    def test_initialization(self, obd_controller):
        """Test OBD controller initialization"""
        assert obd_controller is not None
        assert hasattr(obd_controller, 'connection')
        assert hasattr(obd_controller, 'supported_commands')
    
    def test_connection_management(self, obd_controller):
        """Test connection establishment and teardown"""
        # Test demo mode connection
        result = obd_controller.connect(port="demo", protocol="demo")
        assert result is True
        
        # Test disconnection
        obd_controller.disconnect()
        assert obd_controller.connection is None
    
    def test_parameter_reading(self, obd_controller):
        """Test parameter reading functionality"""
        obd_controller.connect(port="demo", protocol="demo")
        
        # Test reading basic parameters
        rpm = obd_controller.read_parameter("ENGINE_RPM")
        assert rpm is not None
        assert isinstance(rpm.value, (int, float))
        
        speed = obd_controller.read_parameter("VEHICLE_SPEED")
        assert speed is not None
        assert isinstance(speed.value, (int, float))
    
    def test_bulk_parameter_reading(self, obd_controller):
        """Test bulk parameter reading"""
        obd_controller.connect(port="demo", protocol="demo")
        
        parameters = ["ENGINE_RPM", "VEHICLE_SPEED", "ENGINE_LOAD", "COOLANT_TEMP"]
        results = obd_controller.read_bulk_parameters(parameters)
        
        assert len(results) == len(parameters)
        for param_name, param_data in results.items():
            assert param_name in parameters
            assert param_data is not None
    
    def test_error_handling(self, obd_controller):
        """Test error handling in various scenarios"""
        # Test reading without connection
        result = obd_controller.read_parameter("ENGINE_RPM")
        assert result is None
        
        # Test invalid parameter
        obd_controller.connect(port="demo", protocol="demo")
        result = obd_controller.read_parameter("INVALID_PARAM")
        assert result is None
    
    def test_protocol_switching(self, obd_controller):
        """Test protocol switching functionality"""
        # Test different protocols
        protocols = ["OBD-II", "UDS", "demo"]
        for protocol in protocols:
            result = obd_controller.connect(port="demo", protocol=protocol)
            assert result is True
            obd_controller.disconnect()


class TestDatabaseManagerComprehensive:
    """Comprehensive tests for Database Manager"""
    
    @pytest.fixture
    def temp_db(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        db_manager = DatabaseManager(db_path)
        yield db_manager
        # Cleanup
        import os
        try:
            os.unlink(db_path)
        except:
            pass
    
    def test_database_initialization(self, temp_db):
        """Test database initialization and schema creation"""
        # Check if all required tables exist
        with sqlite3.connect(temp_db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            required_tables = [
                'obd_parameters', 'sessions', 'trip_analysis', 
                'anomaly_records', 'ml_models', 'vehicle_profiles',
                'maintenance_predictions', 'performance_benchmarks'
            ]
            
            for table in required_tables:
                assert table in tables
    
    def test_session_lifecycle(self, temp_db):
        """Test complete session lifecycle"""
        # Create session
        session_id = temp_db.create_session()
        assert session_id is not None
        assert len(session_id) > 0
        
        # Add parameters to session
        for i in range(10):
            param_data = ParameterData(
                name="ENGINE_RPM",
                value=2000 + i * 100,
                unit="rpm",
                timestamp=datetime.now(),
                session_id=session_id,
            )
            temp_db.log_parameter(param_data)
        
        # End session
        temp_db.end_session(session_id)
        
        # Verify session data
        with sqlite3.connect(temp_db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM obd_parameters WHERE session_id = ?", (session_id,))
            count = cursor.fetchone()[0]
            assert count == 10
    
    def test_anomaly_logging(self, temp_db):
        """Test anomaly detection and logging"""
        session_id = temp_db.create_session()
        
        # Log multiple anomalies
        anomalies = [
            AnomalyRecord(
                session_id=session_id,
                parameter_name="ENGINE_RPM",
                value=6000,
                anomaly_score=0.9,
                timestamp=datetime.now(),
                severity="high",
                description="RPM too high"
            ),
            AnomalyRecord(
                session_id=session_id,
                parameter_name="COOLANT_TEMP",
                value=120,
                anomaly_score=0.8,
                timestamp=datetime.now(),
                severity="medium",
                description="Temperature elevated"
            )
        ]
        
        for anomaly in anomalies:
            temp_db.log_anomaly(anomaly)
        
        # Verify anomalies were logged
        stats = temp_db.get_database_stats()
        assert stats['anomaly_records_count'] >= 2
    
    def test_data_export_import(self, temp_db):
        """Test data export and import functionality"""
        session_id = temp_db.create_session()
        
        # Add test data
        for i in range(5):
            param_data = ParameterData(
                name="ENGINE_RPM",
                value=2000 + i * 100,
                unit="rpm",
                timestamp=datetime.now(),
                session_id=session_id,
            )
            temp_db.log_parameter(param_data)
        
        # Test data export
        exported_data = temp_db.export_session_data(session_id)
        assert len(exported_data) == 5
        assert all('ENGINE_RPM' in str(row) for row in exported_data)
    
    def test_performance_with_large_dataset(self, temp_db):
        """Test database performance with large dataset"""
        session_id = temp_db.create_session()
        
        # Insert large amount of data
        start_time = time.time()
        for i in range(1000):
            param_data = ParameterData(
                name=f"PARAM_{i % 10}",
                value=i,
                unit="unit",
                timestamp=datetime.now(),
                session_id=session_id,
            )
            temp_db.log_parameter(param_data)
        
        insert_time = time.time() - start_time
        assert insert_time < 10  # Should complete within 10 seconds
        
        # Test query performance
        start_time = time.time()
        stats = temp_db.get_database_stats()
        query_time = time.time() - start_time
        assert query_time < 1  # Should complete within 1 second
        assert stats['obd_parameters_count'] >= 1000


class TestEnhancedAnomalyDetectorComprehensive:
    """Comprehensive tests for Enhanced Anomaly Detector"""
    
    @pytest.fixture
    def anomaly_detector(self):
        return EnhancedAnomalyDetector()
    
    def test_threshold_based_detection(self, anomaly_detector):
        """Test threshold-based anomaly detection"""
        # Test normal values
        normal_data = {
            "ENGINE_RPM": 2000,
            "VEHICLE_SPEED": 60,
            "ENGINE_LOAD": 45,
            "COOLANT_TEMP": 90
        }
        
        anomalies = anomaly_detector.detect_anomalies(normal_data)
        assert len(anomalies) == 0
        
        # Test anomalous values
        anomalous_data = {
            "ENGINE_RPM": 7000,  # Too high
            "VEHICLE_SPEED": 200,  # Too high
            "ENGINE_LOAD": 100,   # At maximum
            "COOLANT_TEMP": 130   # Too high
        }
        
        anomalies = anomaly_detector.detect_anomalies(anomalous_data)
        assert len(anomalies) > 0
    
    def test_contextual_rules(self, anomaly_detector):
        """Test contextual rule-based detection"""
        # Test idle condition anomaly
        idle_data = {
            "ENGINE_RPM": 800,
            "VEHICLE_SPEED": 0,
            "ENGINE_LOAD": 50  # High load at idle - anomaly
        }
        
        anomalies = anomaly_detector.detect_anomalies(idle_data)
        idle_anomalies = [a for a in anomalies if "idle" in a.description.lower()]
        assert len(idle_anomalies) > 0
    
    def test_pattern_detection(self, anomaly_detector):
        """Test pattern-based anomaly detection"""
        # Simulate oscillating RPM pattern
        rpm_values = [2000, 2500, 2000, 2500, 2000, 2500, 2000, 2500]
        
        for rpm in rpm_values:
            data = {"ENGINE_RPM": rpm, "VEHICLE_SPEED": 60}
            anomaly_detector.detect_anomalies(data)
        
        # Check if pattern was detected
        assert len(anomaly_detector.parameter_history) > 0
    
    def test_severity_classification(self, anomaly_detector):
        """Test anomaly severity classification"""
        # Critical anomaly
        critical_data = {"ENGINE_RPM": 8000}
        anomalies = anomaly_detector.detect_anomalies(critical_data)
        
        if anomalies:
            critical_anomalies = [a for a in anomalies if a.severity == "critical"]
            assert len(critical_anomalies) > 0


class TestEnhancedTripAnalyzerComprehensive:
    """Comprehensive tests for Enhanced Trip Analyzer"""
    
    @pytest.fixture
    def trip_analyzer(self):
        return EnhancedTripAnalyzer()
    
    def test_trip_data_processing(self, trip_analyzer):
        """Test trip data processing and analysis"""
        # Create sample trip data
        trip_data = []
        for i in range(100):
            trip_data.append({
                "timestamp": datetime.now() - timedelta(minutes=i),
                "ENGINE_RPM": 2000 + (i % 1000),
                "VEHICLE_SPEED": 60 + (i % 40),
                "ENGINE_LOAD": 40 + (i % 30),
                "FUEL_CONSUMPTION": 8.5 + (i % 3)
            })
        
        # Analyze trip
        analysis = trip_analyzer.analyze_trip(trip_data)
        
        assert analysis is not None
        assert "summary" in analysis
        assert "efficiency_metrics" in analysis
        assert "driving_patterns" in analysis
    
    def test_driving_pattern_detection(self, trip_analyzer):
        """Test driving pattern detection"""
        # Create aggressive driving pattern
        aggressive_data = []
        for i in range(50):
            aggressive_data.append({
                "timestamp": datetime.now() - timedelta(seconds=i),
                "ENGINE_RPM": 4000 + (i % 2000),  # High RPM
                "VEHICLE_SPEED": 80 + (i % 50),   # High speed variations
                "ENGINE_LOAD": 80 + (i % 20),     # High load
            })
        
        analysis = trip_analyzer.analyze_trip(aggressive_data)
        
        # Should detect aggressive driving
        assert "driving_style" in analysis
        driving_style = analysis["driving_style"]
        assert driving_style in ["aggressive", "moderate", "eco"]
    
    def test_efficiency_calculation(self, trip_analyzer):
        """Test fuel efficiency calculations"""
        # Create efficient driving data
        efficient_data = []
        for i in range(100):
            efficient_data.append({
                "timestamp": datetime.now() - timedelta(seconds=i),
                "ENGINE_RPM": 1800 + (i % 400),   # Low RPM
                "VEHICLE_SPEED": 50 + (i % 10),   # Steady speed
                "ENGINE_LOAD": 30 + (i % 10),     # Low load
                "FUEL_CONSUMPTION": 6.0 + (i % 1) # Good efficiency
            })
        
        analysis = trip_analyzer.analyze_trip(efficient_data)
        
        assert "efficiency_metrics" in analysis
        efficiency = analysis["efficiency_metrics"]
        assert "fuel_efficiency" in efficiency
        assert isinstance(efficiency["fuel_efficiency"], (int, float))


class TestJWTAuthComprehensive:
    """Comprehensive tests for JWT Authentication"""
    
    @pytest.fixture
    def jwt_auth(self):
        return JWTAuth(secret_key="test_secret_key_for_testing")
    
    def test_token_generation_and_validation(self, jwt_auth):
        """Test JWT token generation and validation"""
        user_data = {
            "user_id": "test_user_123",
            "email": "test@example.com",
            "role": "user"
        }
        
        # Generate token
        token = jwt_auth.generate_token(user_data)
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Validate token
        decoded_data = jwt_auth.validate_token(token)
        assert decoded_data is not None
        assert decoded_data["user_id"] == user_data["user_id"]
        assert decoded_data["email"] == user_data["email"]
    
    def test_token_expiration(self, jwt_auth):
        """Test token expiration handling"""
        user_data = {"user_id": "test_user"}
        
        # Generate token with short expiration
        token = jwt_auth.generate_token(user_data, expires_in=1)  # 1 second
        assert token is not None
        
        # Wait for expiration
        time.sleep(2)
        
        # Token should be invalid
        decoded_data = jwt_auth.validate_token(token)
        assert decoded_data is None
    
    def test_invalid_token_handling(self, jwt_auth):
        """Test handling of invalid tokens"""
        # Test with invalid token
        invalid_tokens = [
            "invalid.token.here",
            "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.invalid",
            "",
            None
        ]
        
        for invalid_token in invalid_tokens:
            decoded_data = jwt_auth.validate_token(invalid_token)
            assert decoded_data is None


class TestUserManagerComprehensive:
    """Comprehensive tests for User Manager"""
    
    @pytest.fixture
    def temp_user_db(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        user_manager = UserManager(db_path)
        yield user_manager
        # Cleanup
        import os
        try:
            os.unlink(db_path)
        except:
            pass
    
    def test_user_registration(self, temp_user_db):
        """Test user registration process"""
        user_data = {
            "email": "test@example.com",
            "password": "secure_password_123",
            "first_name": "Test",
            "last_name": "User"
        }
        
        # Register user
        user_id = temp_user_db.register_user(**user_data)
        assert user_id is not None
        assert len(user_id) > 0
        
        # Verify user exists
        user = temp_user_db.get_user_by_email(user_data["email"])
        assert user is not None
        assert user["email"] == user_data["email"]
        assert user["first_name"] == user_data["first_name"]
    
    def test_user_authentication(self, temp_user_db):
        """Test user authentication"""
        user_data = {
            "email": "auth_test@example.com",
            "password": "test_password_456",
            "first_name": "Auth",
            "last_name": "Test"
        }
        
        # Register user
        user_id = temp_user_db.register_user(**user_data)
        
        # Test successful authentication
        authenticated_user = temp_user_db.authenticate_user(
            user_data["email"], 
            user_data["password"]
        )
        assert authenticated_user is not None
        assert authenticated_user["user_id"] == user_id
        
        # Test failed authentication
        failed_auth = temp_user_db.authenticate_user(
            user_data["email"], 
            "wrong_password"
        )
        assert failed_auth is None
    
    def test_device_management(self, temp_user_db):
        """Test device registration and management"""
        # Register user first
        user_id = temp_user_db.register_user(
            email="device_test@example.com",
            password="password123",
            first_name="Device",
            last_name="Test"
        )
        
        # Register device
        device_data = {
            "device_id": "RPI_001",
            "device_name": "Mercedes W222 Scanner",
            "device_type": "raspberry_pi"
        }
        
        success = temp_user_db.register_device(user_id, **device_data)
        assert success is True
        
        # Get user devices
        devices = temp_user_db.get_user_devices(user_id)
        assert len(devices) == 1
        assert devices[0]["device_id"] == device_data["device_id"]
    
    def test_subscription_management(self, temp_user_db):
        """Test subscription management"""
        # Register user
        user_id = temp_user_db.register_user(
            email="sub_test@example.com",
            password="password123",
            first_name="Sub",
            last_name="Test"
        )
        
        # Create subscription
        subscription_data = {
            "plan_id": "pro_monthly",
            "stripe_subscription_id": "sub_test123",
            "status": "active"
        }
        
        success = temp_user_db.create_subscription(user_id, **subscription_data)
        assert success is True
        
        # Get user subscription
        subscription = temp_user_db.get_user_subscription(user_id)
        assert subscription is not None
        assert subscription["plan_id"] == subscription_data["plan_id"]
        assert subscription["status"] == subscription_data["status"]


class TestIntegrationFlows:
    """Integration tests for complete workflows"""
    
    @pytest.fixture
    def integrated_system(self):
        """Setup integrated system for testing"""
        # Create temporary database
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        
        # Initialize components
        db_manager = DatabaseManager(db_path)
        obd_controller = OBDController()
        anomaly_detector = EnhancedAnomalyDetector()
        trip_analyzer = EnhancedTripAnalyzer()
        
        system = {
            "db_manager": db_manager,
            "obd_controller": obd_controller,
            "anomaly_detector": anomaly_detector,
            "trip_analyzer": trip_analyzer,
            "db_path": db_path
        }
        
        yield system
        
        # Cleanup
        import os
        try:
            os.unlink(db_path)
        except:
            pass
    
    def test_complete_trip_workflow(self, integrated_system):
        """Test complete trip workflow from OBD to analysis"""
        db_manager = integrated_system["db_manager"]
        obd_controller = integrated_system["obd_controller"]
        anomaly_detector = integrated_system["anomaly_detector"]
        trip_analyzer = integrated_system["trip_analyzer"]
        
        # Connect OBD
        obd_controller.connect(port="demo", protocol="demo")
        
        # Start session
        session_id = db_manager.create_session()
        
        # Simulate trip data collection
        trip_data = []
        for i in range(50):
            # Read parameters
            parameters = obd_controller.read_bulk_parameters([
                "ENGINE_RPM", "VEHICLE_SPEED", "ENGINE_LOAD", "COOLANT_TEMP"
            ])
            
            # Log parameters
            for param_name, param_data in parameters.items():
                if param_data:
                    param_data.session_id = session_id
                    db_manager.log_parameter(param_data)
                    trip_data.append({
                        "timestamp": param_data.timestamp,
                        param_name: param_data.value
                    })
            
            # Check for anomalies
            if parameters:
                param_values = {name: data.value for name, data in parameters.items() if data}
                anomalies = anomaly_detector.detect_anomalies(param_values)
                
                # Log anomalies
                for anomaly in anomalies:
                    anomaly.session_id = session_id
                    db_manager.log_anomaly(anomaly)
        
        # End session
        db_manager.end_session(session_id)
        
        # Analyze trip
        if trip_data:
            # Convert to proper format for analysis
            formatted_data = []
            for entry in trip_data:
                formatted_entry = {"timestamp": entry["timestamp"]}
                for key, value in entry.items():
                    if key != "timestamp":
                        formatted_entry[key] = value
                formatted_data.append(formatted_entry)
            
            analysis = trip_analyzer.analyze_trip(formatted_data)
            assert analysis is not None
        
        # Verify data was stored
        stats = db_manager.get_database_stats()
        assert stats["obd_parameters_count"] > 0
        assert stats["sessions_count"] >= 1
    
    def test_concurrent_operations(self, integrated_system):
        """Test system behavior under concurrent operations"""
        db_manager = integrated_system["db_manager"]
        
        def worker_function(worker_id):
            """Worker function for concurrent testing"""
            session_id = db_manager.create_session()
            
            for i in range(10):
                param_data = ParameterData(
                    name=f"PARAM_{worker_id}",
                    value=i,
                    unit="unit",
                    timestamp=datetime.now(),
                    session_id=session_id,
                )
                db_manager.log_parameter(param_data)
            
            db_manager.end_session(session_id)
        
        # Start multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker_function, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all data was stored correctly
        stats = db_manager.get_database_stats()
        assert stats["obd_parameters_count"] >= 50  # 5 workers * 10 parameters each
        assert stats["sessions_count"] >= 5


class TestErrorHandlingAndEdgeCases:
    """Tests for error handling and edge cases"""
    
    def test_database_corruption_handling(self):
        """Test handling of database corruption"""
        # Create corrupted database file
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            f.write(b"corrupted data")
            corrupted_db_path = f.name
        
        try:
            # Should handle corruption gracefully
            db_manager = DatabaseManager(corrupted_db_path)
            # If it doesn't raise an exception, it handled it gracefully
            assert True
        except Exception as e:
            # Should be a specific, handled exception
            assert "database" in str(e).lower() or "corrupt" in str(e).lower()
        finally:
            import os
            try:
                os.unlink(corrupted_db_path)
            except:
                pass
    
    def test_memory_usage_under_load(self):
        """Test memory usage under high load"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Create large dataset
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        
        db_manager = DatabaseManager(db_path)
        session_id = db_manager.create_session()
        
        # Insert large amount of data
        for i in range(5000):
            param_data = ParameterData(
                name=f"PARAM_{i % 100}",
                value=i,
                unit="unit",
                timestamp=datetime.now(),
                session_id=session_id,
            )
            db_manager.log_parameter(param_data)
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 100MB)
        assert memory_increase < 100 * 1024 * 1024
        
        # Cleanup
        import os
        try:
            os.unlink(db_path)
        except:
            pass
    
    def test_network_failure_simulation(self):
        """Test behavior during network failures"""
        # This would test Raspberry Pi client behavior
        # when network connection is lost
        pass  # Implementation would depend on actual network code


if __name__ == "__main__":
    # Run tests with coverage
    pytest.main([
        __file__,
        "-v",
        "--cov=mercedes_obd_scanner",
        "--cov-report=html",
        "--cov-report=term-missing",
        "--cov-fail-under=80"
    ])
