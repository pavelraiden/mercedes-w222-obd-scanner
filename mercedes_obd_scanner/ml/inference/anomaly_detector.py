# This module contains the AnomalyDetector class for real-time inference.

import joblib
import pandas as pd
from sklearn.ensemble import IsolationForest


class AnomalyDetector:
    def __init__(
        self,
        model_path="/home/ubuntu/mercedes-obd-scanner/mercedes_obd_scanner/ml/models/anomaly_model.pkl",
    ):
        self.model_path = model_path
        self.model = self.load_model()

    def load_model(self):
        try:
            return joblib.load(self.model_path)
        except FileNotFoundError:
            # Return a default, untrained model if no model is found
            return IsolationForest(contamination=0.1)

    def predict(self, data):
        if not isinstance(data, pd.DataFrame):
            data = pd.DataFrame([data])
        return self.model.predict(data)

    def get_anomaly_score(self, data):
        if not isinstance(data, pd.DataFrame):
            data = pd.DataFrame([data])
        return self.model.decision_function(data)
