"""
Real OBD-II integration using ELM327 adapter for Mercedes W222.
Supports both Bluetooth and USB connections.
"""

import serial
import bluetooth
import time
import logging
from typing import Dict, List, Optional, Union
from dataclasses import dataclass
from .base_handler import BaseProtocolHandler

logger = logging.getLogger(__name__)


@dataclass
class OBDCommand:
    """OBD-II command definition."""
    name: str
    pid: str
    description: str
    unit: str
    formula: str
    min_value: float
    max_value: float


class MercedesW222OBDHandler(BaseProtocolHandler):
    """Real OBD-II handler for Mercedes W222 with ELM327 adapter."""
    
    # Mercedes W222 specific PIDs and commands
    MERCEDES_W222_PIDS = {
        # Standard OBD-II PIDs
        "ENGINE_RPM": OBDCommand("ENGINE_RPM", "010C", "Engine RPM", "rpm", "((A*256)+B)/4", 0, 8000),
        "VEHICLE_SPEED": OBDCommand("VEHICLE_SPEED", "010D", "Vehicle Speed", "km/h", "A", 0, 255),
        "ENGINE_LOAD": OBDCommand("ENGINE_LOAD", "0104", "Engine Load", "%", "A*100/255", 0, 100),
        "COOLANT_TEMP": OBDCommand("COOLANT_TEMP", "0105", "Coolant Temperature", "°C", "A-40", -40, 215),
        "INTAKE_TEMP": OBDCommand("INTAKE_TEMP", "010F", "Intake Air Temperature", "°C", "A-40", -40, 215),
        "MAF_RATE": OBDCommand("MAF_RATE", "0110", "Mass Air Flow Rate", "g/s", "((A*256)+B)/100", 0, 655.35),
        "THROTTLE_POS": OBDCommand("THROTTLE_POS", "0111", "Throttle Position", "%", "A*100/255", 0, 100),
        "FUEL_PRESSURE": OBDCommand("FUEL_PRESSURE", "010A", "Fuel Pressure", "kPa", "A*3", 0, 765),
        "INTAKE_PRESSURE": OBDCommand("INTAKE_PRESSURE", "010B", "Intake Manifold Pressure", "kPa", "A", 0, 255),
        
        # Mercedes-specific PIDs (Mode 22)
        "TRANSMISSION_TEMP": OBDCommand("TRANSMISSION_TEMP", "221234", "Transmission Temperature", "°C", "A-40", -40, 200),
        "TURBO_PRESSURE": OBDCommand("TURBO_PRESSURE", "221567", "Turbocharger Pressure", "bar", "A/100", 0, 3.0),
        "DPF_PRESSURE": OBDCommand("DPF_PRESSURE", "221890", "DPF Differential Pressure", "mbar", "A*10", 0, 2550),
        "FUEL_RAIL_PRESSURE": OBDCommand("FUEL_RAIL_PRESSURE", "221123", "Fuel Rail Pressure", "bar", "((A*256)+B)/100", 0, 2000),
        "EGR_POSITION": OBDCommand("EGR_POSITION", "221456", "EGR Valve Position", "%", "A*100/255", 0, 100),
        "LAMBDA_SENSOR": OBDCommand("LAMBDA_SENSOR", "221789", "Lambda Sensor Voltage", "V", "A/100", 0, 5.0),
        
        # W222 specific systems
        "AIRMATIC_PRESSURE_FL": OBDCommand("AIRMATIC_PRESSURE_FL", "222001", "Airmatic Pressure Front Left", "bar", "A/10", 0, 25.5),
        "AIRMATIC_PRESSURE_FR": OBDCommand("AIRMATIC_PRESSURE_FR", "222002", "Airmatic Pressure Front Right", "bar", "A/10", 0, 25.5),
        "AIRMATIC_PRESSURE_RL": OBDCommand("AIRMATIC_PRESSURE_RL", "222003", "Airmatic Pressure Rear Left", "bar", "A/10", 0, 25.5),
        "AIRMATIC_PRESSURE_RR": OBDCommand("AIRMATIC_PRESSURE_RR", "222004", "Airmatic Pressure Rear Right", "bar", "A/10", 0, 25.5),
        "MAGIC_BODY_CONTROL": OBDCommand("MAGIC_BODY_CONTROL", "222100", "Magic Body Control Status", "status", "A", 0, 255),
    }
    
    def __init__(self, connection_type: str = "bluetooth", port: str = "/dev/rfcomm0", 
                 baudrate: int = 9600, timeout: float = 5.0):
        """
        Initialize the real OBD handler.
        
        Args:
            connection_type: "bluetooth" or "usb"
            port: Serial port or Bluetooth MAC address
            baudrate: Communication speed
            timeout: Connection timeout
        """
        super().__init__()
        self.connection_type = connection_type
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.connection = None
        self.is_connected = False
        
    def connect(self) -> bool:
        """Establish connection to ELM327 adapter."""
        try:
            if self.connection_type == "bluetooth":
                return self._connect_bluetooth()
            elif self.connection_type == "usb":
                return self._connect_usb()
            else:
                logger.error(f"Unsupported connection type: {self.connection_type}")
                return False
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False
    
    def _connect_bluetooth(self) -> bool:
        """Connect via Bluetooth."""
        try:
            # For Bluetooth, we use serial over RFCOMM
            self.connection = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            
            # Initialize ELM327
            if self._initialize_elm327():
                self.is_connected = True
                logger.info(f"Connected to ELM327 via Bluetooth on {self.port}")
                return True
            else:
                self.connection.close()
                return False
                
        except Exception as e:
            logger.error(f"Bluetooth connection failed: {e}")
            return False
    
    def _connect_usb(self) -> bool:
        """Connect via USB."""
        try:
            self.connection = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            
            # Initialize ELM327
            if self._initialize_elm327():
                self.is_connected = True
                logger.info(f"Connected to ELM327 via USB on {self.port}")
                return True
            else:
                self.connection.close()
                return False
                
        except Exception as e:
            logger.error(f"USB connection failed: {e}")
            return False
    
    def _initialize_elm327(self) -> bool:
        """Initialize ELM327 adapter with proper settings."""
        try:
            # Reset adapter
            self._send_command("ATZ")
            time.sleep(2)
            
            # Turn off echo
            self._send_command("ATE0")
            
            # Set protocol to automatic
            self._send_command("ATSP0")
            
            # Set headers off
            self._send_command("ATH0")
            
            # Set spaces off
            self._send_command("ATS0")
            
            # Set line feeds off
            self._send_command("ATL0")
            
            # Test communication
            response = self._send_command("0100")
            if response and "41 00" in response:
                logger.info("ELM327 initialized successfully")
                return True
            else:
                logger.error("Failed to initialize ELM327")
                return False
                
        except Exception as e:
            logger.error(f"ELM327 initialization failed: {e}")
            return False
    
    def _send_command(self, command: str) -> Optional[str]:
        """Send command to ELM327 and get response."""
        if not self.connection:
            return None
            
        try:
            # Clear input buffer
            self.connection.flushInput()
            
            # Send command
            self.connection.write((command + "\r").encode())
            
            # Read response
            response = ""
            while True:
                char = self.connection.read(1).decode('utf-8', errors='ignore')
                if not char:
                    break
                if char == '>':
                    break
                response += char
            
            return response.strip()
            
        except Exception as e:
            logger.error(f"Command failed: {command}, Error: {e}")
            return None
    
    def read_parameter(self, parameter_name: str) -> Optional[Dict]:
        """Read a specific OBD parameter."""
        if not self.is_connected:
            logger.error("Not connected to OBD adapter")
            return None
            
        if parameter_name not in self.MERCEDES_W222_PIDS:
            logger.error(f"Unknown parameter: {parameter_name}")
            return None
            
        pid_info = self.MERCEDES_W222_PIDS[parameter_name]
        
        try:
            # Send PID command
            response = self._send_command(pid_info.pid)
            
            if not response:
                logger.error(f"No response for parameter: {parameter_name}")
                return None
            
            # Parse response
            value = self._parse_response(response, pid_info)
            
            if value is not None:
                return {
                    "parameter": parameter_name,
                    "value": value,
                    "unit": pid_info.unit,
                    "timestamp": time.time(),
                    "raw_response": response
                }
            else:
                logger.error(f"Failed to parse response for {parameter_name}: {response}")
                return None
                
        except Exception as e:
            logger.error(f"Error reading parameter {parameter_name}: {e}")
            return None
    
    def _parse_response(self, response: str, pid_info: OBDCommand) -> Optional[float]:
        """Parse OBD response according to PID formula."""
        try:
            # Remove spaces and convert to uppercase
            response = response.replace(" ", "").upper()
            
            # Extract data bytes
            if pid_info.pid.startswith("01"):
                # Standard OBD-II response format: 41 XX YY ZZ...
                if len(response) >= 6:
                    data_bytes = response[4:]  # Skip "41XX"
                else:
                    return None
            elif pid_info.pid.startswith("22"):
                # Mercedes-specific response format: 62 XX XX YY ZZ...
                if len(response) >= 8:
                    data_bytes = response[6:]  # Skip "62XXXX"
                else:
                    return None
            else:
                return None
            
            # Convert hex bytes to integers
            bytes_list = []
            for i in range(0, len(data_bytes), 2):
                if i + 1 < len(data_bytes):
                    byte_val = int(data_bytes[i:i+2], 16)
                    bytes_list.append(byte_val)
            
            if not bytes_list:
                return None
            
            # Apply formula
            A = bytes_list[0] if len(bytes_list) > 0 else 0
            B = bytes_list[1] if len(bytes_list) > 1 else 0
            C = bytes_list[2] if len(bytes_list) > 2 else 0
            D = bytes_list[3] if len(bytes_list) > 3 else 0
            
            # Evaluate formula
            formula = pid_info.formula
            formula = formula.replace("A", str(A))
            formula = formula.replace("B", str(B))
            formula = formula.replace("C", str(C))
            formula = formula.replace("D", str(D))
            
            value = eval(formula)
            
            # Clamp to valid range
            value = max(pid_info.min_value, min(pid_info.max_value, value))
            
            return round(value, 2)
            
        except Exception as e:
            logger.error(f"Error parsing response: {e}")
            return None
    
    def read_all_parameters(self) -> Dict[str, Dict]:
        """Read all available parameters."""
        results = {}
        
        for param_name in self.MERCEDES_W222_PIDS.keys():
            result = self.read_parameter(param_name)
            if result:
                results[param_name] = result
            time.sleep(0.1)  # Small delay between commands
        
        return results
    
    def read_dtcs(self) -> List[Dict]:
        """Read Diagnostic Trouble Codes."""
        if not self.is_connected:
            return []
        
        try:
            # Read stored DTCs
            response = self._send_command("03")
            
            if not response:
                return []
            
            dtcs = []
            # Parse DTC response (simplified)
            if "43" in response:
                # Extract DTC data
                data = response.replace(" ", "").replace("43", "")
                
                # Each DTC is 2 bytes
                for i in range(0, len(data), 4):
                    if i + 3 < len(data):
                        dtc_bytes = data[i:i+4]
                        dtc_code = self._decode_dtc(dtc_bytes)
                        if dtc_code:
                            dtcs.append({
                                "code": dtc_code,
                                "description": self._get_dtc_description(dtc_code),
                                "timestamp": time.time()
                            })
            
            return dtcs
            
        except Exception as e:
            logger.error(f"Error reading DTCs: {e}")
            return []
    
    def _decode_dtc(self, dtc_bytes: str) -> Optional[str]:
        """Decode DTC from hex bytes."""
        try:
            if len(dtc_bytes) != 4:
                return None
            
            first_byte = int(dtc_bytes[0:2], 16)
            second_byte = int(dtc_bytes[2:4], 16)
            
            # Determine DTC prefix
            prefix_map = {0: "P", 1: "C", 2: "B", 3: "U"}
            prefix = prefix_map.get((first_byte >> 6) & 0x03, "P")
            
            # Calculate DTC number
            dtc_num = ((first_byte & 0x3F) << 8) | second_byte
            
            return f"{prefix}{dtc_num:04X}"
            
        except Exception:
            return None
    
    def _get_dtc_description(self, dtc_code: str) -> str:
        """Get description for DTC code."""
        # Mercedes W222 specific DTC descriptions
        dtc_descriptions = {
            "P0001": "Fuel Volume Regulator Control Circuit/Open",
            "P0002": "Fuel Volume Regulator Control Circuit Range/Performance",
            "P0003": "Fuel Volume Regulator Control Circuit Low",
            "P0004": "Fuel Volume Regulator Control Circuit High",
            "P0005": "Fuel Shutoff Valve A Control Circuit/Open",
            "P0171": "System Too Lean (Bank 1)",
            "P0172": "System Too Rich (Bank 1)",
            "P0174": "System Too Lean (Bank 2)",
            "P0175": "System Too Rich (Bank 2)",
            "P0300": "Random/Multiple Cylinder Misfire Detected",
            "P0420": "Catalyst System Efficiency Below Threshold (Bank 1)",
            "P0430": "Catalyst System Efficiency Below Threshold (Bank 2)",
            # Add more Mercedes-specific codes as needed
        }
        
        return dtc_descriptions.get(dtc_code, "Unknown DTC")
    
    def clear_dtcs(self) -> bool:
        """Clear all stored DTCs."""
        if not self.is_connected:
            return False
        
        try:
            response = self._send_command("04")
            return "44" in response if response else False
        except Exception as e:
            logger.error(f"Error clearing DTCs: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from OBD adapter."""
        if self.connection:
            try:
                self.connection.close()
                self.is_connected = False
                logger.info("Disconnected from OBD adapter")
            except Exception as e:
                logger.error(f"Error disconnecting: {e}")
    
    def get_supported_parameters(self) -> List[str]:
        """Get list of supported parameters."""
        return list(self.MERCEDES_W222_PIDS.keys())
    
    def is_parameter_supported(self, parameter_name: str) -> bool:
        """Check if parameter is supported."""
        return parameter_name in self.MERCEDES_W222_PIDS
