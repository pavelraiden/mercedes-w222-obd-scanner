# This is the main FastAPI application for the Mercedes OBD Scanner web interface.

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi import Request
import asyncio
import json
import sys
import os

# Add the parent directory to the path to import the mercedes_obd_scanner module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mercedes_obd_scanner.gui.app_controller import AppController

app = FastAPI(title="Mercedes W222 OBD Scanner", version="2.0.0")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Global app controller instance
app_controller = AppController()

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

# Register callbacks with the app controller
def on_data_update(param_data):
    asyncio.create_task(manager.broadcast(json.dumps({
        "type": "data_update",
        "name": param_data.name,
        "value": param_data.value,
        "unit": param_data.unit,
        "timestamp": param_data.timestamp.isoformat()
    })))

def on_status_update(status, message):
    asyncio.create_task(manager.broadcast(json.dumps({
        "type": "status_update",
        "status": status,
        "message": message
    })))

def on_prediction_update(predictions):
    asyncio.create_task(manager.broadcast(json.dumps({
        "type": "prediction_update",
        "predictions": predictions
    })))

def on_anomaly_detected(anomaly_data):
    asyncio.create_task(manager.broadcast(json.dumps({
        "type": "anomaly_detected",
        "score": float(anomaly_data["score"]),
        "data": str(anomaly_data["data"])
    })))

app_controller.add_observer("data_update", on_data_update)
app_controller.add_observer("status_update", on_status_update)
app_controller.add_observer("prediction_update", on_prediction_update)
app_controller.add_observer("anomaly_detected", on_anomaly_detected)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/ports")
async def get_available_ports():
    return {"ports": app_controller.get_available_ports()}

@app.post("/api/connect")
async def connect_obd(data: dict):
    protocol = data.get("protocol", "DEMO")
    port = data.get("port", "DEMO")
    vehicle_id = data.get("vehicle_id")
    
    app_controller.connect_obd(protocol, port, vehicle_id)
    return {"status": "connecting"}

@app.post("/api/disconnect")
async def disconnect_obd():
    app_controller.disconnect_obd()
    return {"status": "disconnecting"}

@app.get("/api/trip-history")
async def get_trip_history():
    return {"trips": app_controller.get_trip_history()}

@app.get("/api/trip-details/{session_id}")
async def get_trip_details(session_id: str):
    return app_controller.get_trip_details(session_id)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle incoming WebSocket messages if needed
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
