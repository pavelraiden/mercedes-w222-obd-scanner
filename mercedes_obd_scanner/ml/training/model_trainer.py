# This module contains the ModelTrainer class for offline model training.

import joblib
import pandas as pd
from sklearn.ensemble import IsolationForest


class ModelTrainer:
    def __init__(
        self,
        data_path,
        model_path="/home/ubuntu/mercedes-obd-scanner/mercedes_obd_scanner/ml/models/anomaly_model.pkl",
    ):
        self.data_path = data_path
        self.model_path = model_path
        self.model = IsolationForest(contamination=0.1)

    def train(self):
        data = self.load_data()
        self.model.fit(data)
        self.save_model()

    def load_data(self):
        # In a real application, this would load from a database or data warehouse
        # For this example, we'll assume a CSV file
        return pd.read_csv(self.data_path)

    def save_model(self):
        joblib.dump(self.model, self.model_path)
