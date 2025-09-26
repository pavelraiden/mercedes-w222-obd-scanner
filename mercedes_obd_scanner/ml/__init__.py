# This file initializes the machine learning module for the Mercedes OBD Scanner.

from .training.model_trainer import ModelTrainer
from .inference.anomaly_detector import AnomalyDetector

__all__ = ["ModelTrainer", "AnomalyDetector"]

