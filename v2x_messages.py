"""
V2X Message Types and Handling
Implements BSM, CAM, and DENM message formats
"""

import json
import time
from typing import Dict, Any
from dataclasses import dataclass, asdict


@dataclass
class BSMMessage:
    """Basic Safety Message - Core V2V communication"""
    vehicle_id: str
    timestamp: float
    position_x: float
    position_y: float
    speed: float
    heading: float
    acceleration: float
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())


@dataclass
class CAMMessage:
    """Cooperative Awareness Message - Extended vehicle status"""
    vehicle_id: str
    timestamp: float
    position_x: float
    position_y: float
    speed: float
    heading: float
    vehicle_type: str
    vehicle_length: float
    vehicle_width: float
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())


@dataclass
class DENMMessage:
    """Decentralized Environmental Notification Message - Road hazards"""
    message_id: str
    timestamp: float
    event_type: str  # "accident", "roadwork", "hazard", etc.
    position_x: float
    position_y: float
    severity: int  # 1-5
    description: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class MessageHandler:
    """Handles V2X message creation and parsing"""
    
    @staticmethod
    def create_bsm(vehicle_id: str, position: tuple, speed: float, 
                   heading: float, acceleration: float = 0.0) -> BSMMessage:
        """Create a Basic Safety Message"""
        return BSMMessage(
            vehicle_id=vehicle_id,
            timestamp=time.time(),
            position_x=position[0],
            position_y=position[1],
            speed=speed,
            heading=heading,
            acceleration=acceleration
        )
    
    @staticmethod
    def create_cam(vehicle_id: str, position: tuple, speed: float,
                   heading: float, vehicle_type: str = "car",
                   length: float = 5.0, width: float = 2.0) -> CAMMessage:
        """Create a Cooperative Awareness Message"""
        return CAMMessage(
            vehicle_id=vehicle_id,
            timestamp=time.time(),
            position_x=position[0],
            position_y=position[1],
            speed=speed,
            heading=heading,
            vehicle_type=vehicle_type,
            vehicle_length=length,
            vehicle_width=width
        )
    
    @staticmethod
    def create_denm(event_type: str, position: tuple, severity: int,
                   description: str) -> DENMMessage:
        """Create a Decentralized Environmental Notification Message"""
        return DENMMessage(
            message_id=f"denm_{int(time.time())}",
            timestamp=time.time(),
            event_type=event_type,
            position_x=position[0],
            position_y=position[1],
            severity=severity,
            description=description
        )
    
    @staticmethod
    def parse_message(message_json: str) -> Dict[str, Any]:
        """Parse a JSON message"""
        return json.loads(message_json)

