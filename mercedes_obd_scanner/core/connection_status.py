"""
Connection status enumeration for OBD Scanner
"""

from enum import Enum


class ConnectionStatus(Enum):
    """Enumeration of possible connection states for OBD interface"""
    
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    
    def __str__(self):
        return self.value
    
    @property
    def is_connected(self) -> bool:
        """Check if status represents a successful connection"""
        return self == ConnectionStatus.CONNECTED
    
    @property
    def is_error(self) -> bool:
        """Check if status represents an error state"""
        return self == ConnectionStatus.ERROR
    
    @property
    def is_transitional(self) -> bool:
        """Check if status represents a transitional state"""
        return self == ConnectionStatus.CONNECTING
