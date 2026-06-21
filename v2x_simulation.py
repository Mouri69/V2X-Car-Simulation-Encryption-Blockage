"""
V2X Simulation with MITM Attack and Post-Quantum Security
Main simulation script using SUMO TraCI
"""

import os
import sys
import subprocess
import traci
import time
import json
import math
import tkinter as tk
from tkinter import ttk, messagebox
import threading
from typing import Dict, List, Tuple

# Set UTF-8 encoding and UNBUFFERED OUTPUT FIRST!
os.environ['PYTHONIOENCODING'] = 'utf-8'
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
else:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)

# Import V2X modules
from v2x_messages import MessageHandler, BSMMessage
from crypto_classical import ClassicalCrypto
from crypto_postquantum import PostQuantumCrypto
from mitm_attacker import MITMAttacker

# SUMO configuration
SUMO_HOME = r"C:\Program Files (x86)\Eclipse\Sumo"
sys.path.append(os.path.join(SUMO_HOME, "tools"))

# Simulation parameters
SIM_CONFIG = "sumo_test/sim.sumocfg"
COMMUNICATION_RANGE = 50  # meters
SIMULATION_END = 300  # seconds


class Vehicle:
    """Represents a vehicle in the simulation"""
    
    def __init__(self, vehicle_id: str, route_id: str, depart_time: float):
        self.id = vehicle_id
        self.route_id = route_id
        self.depart_time = depart_time
        self.position = (0, 0)
        self.speed = 0
        self.heading = 0
        self.neighbors = []  # Nearby vehicles for V2V communication
        
    def update(self):
        """Update vehicle state from SUMO"""
        try:
            self.position = traci.vehicle.getPosition(self.id)
            self.speed = traci.vehicle.getSpeed(self.id)
            self.heading = traci.vehicle.getAngle(self.id)
        except traci.exceptions.TraCIException:
            pass  # Vehicle may have left the simulation


class V2XSimulation:
    """Main V2X simulation controller"""
    
    def __init__(self):
        self.vehicles: Dict[str, Vehicle] = {}
        self.messages = []  # All V2V messages
        self.mitm_active = False
        self.mitm_vehicle_id = None
        self.message_handler = MessageHandler()
        self.classical_crypto = ClassicalCrypto()  # RSA/AES simulation
        self.postquantum_crypto = PostQuantumCrypto()  # Quantum-resistant
        self.mitm_attacker = None
        self.crypto_mode = "classical"  # "classical" or "postquantum"
        self.communication_log = []  # Log all communications
        self.recent_messages = {}  # Store recent messages per vehicle for GUI display
        self.message_pois = []  # Track POI IDs for message bubbles
        self.communication_circles: Dict[str, bool] = {}  # Track drawn comm ranges
        self.vehicle_colors: Dict[str, Tuple[int, int, int]] = {}
        self.communication_radius = COMMUNICATION_RANGE  # meters for on-screen circle (visual only)
        self.menu_active = False
        self.menu_mode = "main"  # "main" for main menu, "target" for selecting target
        self.selected_target = None  # Stores selected target vehicle ID
        
        # State tracking for interaction spam control
        # Set of tuples: (id1, id2, has_mitm)
        self.active_interactions = set()
        
        # Friendly names for logging
        self.vehicle_names = {
            "vehicle1": "Red Car",
            "vehicle2": "Green Car",
            "vehicle3": "Blue Car",
            "vehicle4": "Purple Car",  # Attacker
            "vehicle5": "Dark Green Truck",
            "vehicle6": "Orange Car",
            "vehicle7": "Cyan Car",
            "vehicle8": "Purple Truck",
            "vehicle9": "Olive Car",
            "vehicle10": "Maroon Car",
            "vehicle11": "Teal Truck",
            "vehicle12": "Grey Car"
        }
        
        # Owner names for each vehicle
        self.vehicle_owners = {
            "vehicle1": "James",
            "vehicle2": "Don",
            "vehicle3": "Sarah",
            "vehicle4": "Eve (Attacker)",
            "vehicle5": "Mike",
            "vehicle6": "Lisa",
            "vehicle7": "Tom",
            "vehicle8": "Anna",
            "vehicle9": "David",
            "vehicle10": "Emma",
            "vehicle11": "Chris",
            "vehicle12": "Sophia"
        }
        
        # Car serial numbers
        self.vehicle_serial_numbers = {
            "vehicle1": "VIN-1HGCM82633A123456",
            "vehicle2": "VIN-2HGCM82633A654321",
            "vehicle3": "VIN-3HGCM82633A112233",
            "vehicle4": "VIN-4HGCM82633A445566",
            "vehicle5": "VIN-5HGCM82633A778899",
            "vehicle6": "VIN-6HGCM82633A001122",
            "vehicle7": "VIN-7HGCM82633A334455",
            "vehicle8": "VIN-8HGCM82633A667788",
            "vehicle9": "VIN-9HGCM82633A990011",
            "vehicle10": "VIN-AHGCM82633A223344",
            "vehicle11": "VIN-BHGCM82633A556677",
            "vehicle12": "VIN-CHGCM82633A889900"
        }
        
        # Owner security numbers (simulated)
        self.owner_security_numbers = {
            "vehicle1": "SSN-123-45-6789",
            "vehicle2": "SSN-234-56-7890",
            "vehicle3": "SSN-345-67-8901",
            "vehicle4": "SSN-456-78-9012",
            "vehicle5": "SSN-567-89-0123",
            "vehicle6": "SSN-678-90-1234",
            "vehicle7": "SSN-789-01-2345",
            "vehicle8": "SSN-890-12-3456",
            "vehicle9": "SSN-901-23-4567",
            "vehicle10": "SSN-012-34-5678",
            "vehicle11": "SSN-135-79-2468",
            "vehicle12": "SSN-246-80-1357"
        }
        
        # Track which cars purple car has been in range with at least once
        self.purple_encountered_cars = set()
        
        # Track vehicles controlled by our attacks
        self.controlled_vehicles = {}  # key: vehicle_id, value: target_speed (m/s)
        
        # References to GUI instances (set by main())
        self.normal_v2x_gui = None
        self.attacker_gui = None
        
    def start_simulation(self):
        """Start SUMO and connect via TraCI"""
        # Build network if needed
        network_file = "sumo_test/network.net.xml"
        if not os.path.exists(network_file):
            print("Building network...")
            self._build_network()
        
        # Start SUMO (use sumo-gui.exe for visualization, sumo.exe for headless)
        sumo_binary = os.path.join(SUMO_HOME, "bin", "sumo-gui.exe")
        # Add delay to GUI so you can see the simulation
        # --step-length: 0.1s per step (slower)
        # --delay: 100ms between steps in GUI
        # --end: simulation end time (increased to 1000s to allow long running)
        sumo_cmd = [sumo_binary, "-c", SIM_CONFIG, "--start", "--step-length", "0.1", "--delay", "300", "--end", "1000"]
        
        traci.start(sumo_cmd)
        print("[OK] SUMO GUI simulation started")
        print("  Note: Vehicles will appear after a few seconds...")
        
    def _build_network(self):
        """Build network file if it doesn't exist"""
        netconvert = os.path.join(SUMO_HOME, "bin", "netconvert.exe")
        cmd = [
            netconvert,
            "--node-files", "sumo_test/nodes.nod.xml",
            "--edge-files", "sumo_test/edges.edg.xml",
            "--output-file", "sumo_test/network.net.xml"
        ]
        subprocess.run(cmd, check=True)
        
    def add_vehicle(self, vehicle_id: str, route_edges: List[str], 
                   depart_time: float, color: Tuple[int, int, int] = (255, 0, 0)):
        """Add a vehicle to the simulation"""
        try:
            # Filter out internal edges (those starting with ':')
            # Internal edges can't be used in routes
            route_edges = [e for e in route_edges if not e.startswith(":")]
            
            # Remove duplicate consecutive edges (e.g., ['A1', 'A1'] -> ['A1'])
            cleaned_edges = []
            for edge in route_edges:
                if not cleaned_edges or edge != cleaned_edges[-1]:
                    cleaned_edges.append(edge)
            route_edges = cleaned_edges
            
            # Validate edges exist and are not internal
            all_edges = traci.edge.getIDList()
            valid_edges = []
            for edge in route_edges:
                # Skip internal edges (double check)
                if edge.startswith(":"):
                    continue
                if edge in all_edges:
                    valid_edges.append(edge)
                else:
                    print(f"[WARN]  Edge '{edge}' not found in network, skipping")
            
            if not valid_edges:
                print(f"[ERROR] No valid edges for vehicle {vehicle_id}")
                return
            
            # Validate route using SUMO's findRoute before creating it
            # Only validate if we have multiple edges - don't reduce to single edge
            if len(valid_edges) > 1:
                try:
                    # Validate route from first to last edge
                    route_result = traci.simulation.findRoute(valid_edges[0], valid_edges[-1])
                    if route_result and route_result.length > 0:
                        # Get the validated route edges
                        validated_route = [e for e in route_result.edges if not e.startswith(":")]
                        # Only use validated route if it has multiple edges (don't reduce to single edge)
                        if len(validated_route) > 1:
                            valid_edges = validated_route
                            print(f"  [OK] Validated route for {vehicle_id}: {valid_edges}")
                        # If validated route is single edge but original had multiple, keep original
                        elif len(validated_route) == 1 and len(valid_edges) > 1:
                            print(f"  [WARN]  Validation reduced route to single edge, keeping original: {valid_edges}")
                except Exception as validate_error:
                    # If validation fails, keep original route
                    print(f"  [WARN]  Route validation failed for {vehicle_id}, using original route: {validate_error}")
                    # Don't reduce to single edge - keep the original route
            
            # Create route if it doesn't exist
            route_id = f"route_{vehicle_id}"
            try:
                # Check if route already exists, delete it first
                existing_routes = traci.route.getIDList()
                if route_id in existing_routes:
                    try:
                        traci.route.delete(route_id)
                    except:
                        pass
                traci.route.add(route_id, valid_edges)
            except Exception as route_error:
                print(f"[ERROR] Error creating route for {vehicle_id}: {route_error}")
                print(f"   Attempted edges: {valid_edges}")
                # Try with just the first edge as fallback
                if len(valid_edges) > 0:
                    try:
                        if route_id in traci.route.getIDList():
                            traci.route.delete(route_id)
                        traci.route.add(route_id, [valid_edges[0]])
                        print(f"   Retrying with single edge: {valid_edges[0]}")
                    except:
                        print(f"   Could not create route even with single edge")
                        return
                else:
                    return
            
            # Define vehicle type if it doesn't exist
            vehicle_types = traci.vehicletype.getIDList()
            if "car" not in vehicle_types:
                # Try to create vehicle type from default
                try:
                    # Check if DEFAULT_VEHTYPE exists
                    if "DEFAULT_VEHTYPE" in vehicle_types:
                        traci.vehicletype.copy("DEFAULT_VEHTYPE", "car")
                    else:
                        # Use the first available type as base
                        base_type = vehicle_types[0] if vehicle_types else "DEFAULT_VEHTYPE"
                        traci.vehicletype.copy(base_type, "car")
                    
                    traci.vehicletype.setLength("car", 5.0)
                    traci.vehicletype.setMaxSpeed("car", 13.89)
                    traci.vehicletype.setAccel("car", 2.6)
                    traci.vehicletype.setDecel("car", 4.5)
                except Exception as type_error:
                    print(f"[WARN]  Could not create vehicle type 'car': {type_error}")
                    # Will try without typeID below
            
            # Get current simulation time
            current_time = traci.simulation.getTime()
            # If depart_time is in the past, use current time + small delay
            actual_depart = max(depart_time, current_time + 0.1)
            
            # Add vehicle (try with typeID first, fallback to default)
            try:
                traci.vehicle.add(
                    vehicle_id,
                    route_id,
                    depart=actual_depart,
                    typeID="car"
                )
            except Exception as add_error:
                # Fallback: add without typeID (uses default)
                print(f"[WARN]  Could not add vehicle with type 'car', using default: {add_error}")
                traci.vehicle.add(
                    vehicle_id,
                    route_id,
                    depart=actual_depart
                )
            
            # Set vehicle color separately
            traci.vehicle.setColor(vehicle_id, color)
            self.vehicle_colors[vehicle_id] = color
            
            # Set initial vehicle label in SUMO GUI
            try:
                traci.vehicle.setParameter(vehicle_id, "guiLabel", vehicle_id)
            except:
                pass  # Some SUMO versions don't support this
            
            # Create Vehicle object
            vehicle = Vehicle(vehicle_id, route_id, depart_time)
            self.vehicles[vehicle_id] = vehicle
            print(f"[OK] Added vehicle: {vehicle_id} on route: {valid_edges}")
            
        except Exception as e:
            print(f"[ERROR] Error adding vehicle {vehicle_id}: {e}")
            import traceback
            traceback.print_exc()
    
    def get_network_edges(self) -> List[str]:
        """Get all available edges in the network"""
        return traci.edge.getIDList()
    
    def find_neighbors(self, vehicle_id: str) -> List[str]:
        """Find vehicles within communication range"""
        if vehicle_id not in self.vehicles:
            return []
        
        vehicle = self.vehicles[vehicle_id]
        neighbors = []
        
        for other_id, other_vehicle in self.vehicles.items():
            if other_id == vehicle_id:
                continue
                
            # Calculate distance
            dx = vehicle.position[0] - other_vehicle.position[0]
            dy = vehicle.position[1] - other_vehicle.position[1]
            distance = (dx**2 + dy**2)**0.5
            
            if distance <= COMMUNICATION_RANGE:
                neighbors.append(other_id)
        
        return neighbors
    
    def send_v2v_message(self, sender_id: str, receiver_id: str, 
                        message_type: str, data: Dict, use_encryption: bool = True,
                        display_text: str = None, intercepted: bool = False):
        """Send a V2V message between vehicles with encryption"""
        # Create message
        message = {
            "sender": sender_id,
            "receiver": receiver_id,
            "type": message_type,
            "data": data,
            "timestamp": traci.simulation.getTime(),
            "encrypted": use_encryption,
            "display_text": display_text,
            "intercepted": intercepted
        }
        
        # Encrypt if requested
        if use_encryption:
            if self.crypto_mode == "classical":
                encrypted_msg = self.classical_crypto.encrypt_message(message)
                message = {**message, **encrypted_msg}
            else:
                encrypted_msg = self.postquantum_crypto.encrypt_message(message)
                message = {**message, **encrypted_msg}
        
        # MITM attacker intercepts
        if self.mitm_attacker:
            message = self.mitm_attacker.intercept_message(message)
        
        # Log communication
        log_entry = {
            "time": traci.simulation.getTime(),
            "sender": sender_id,
            "receiver": receiver_id,
            "type": message_type,
            "encrypted": use_encryption,
            "crypto_type": message.get("crypto_type", "none"),
            # Only mark intercepted when interaction flagged it
            "mitm_intercepted": bool(message.get("intercepted", False)),
            "forged": message.get("forged_by_attacker", False)
        }
        self.communication_log.append(log_entry)
        
        # Print communication with clear encryption status
        crypto_type = message.get('crypto_type', 'unencrypted')
        crypto_status = "[WARN] UNENCRYPTED"
        if use_encryption:
            if crypto_type == 'classical':
                crypto_status = "[LOCK] CLASSICAL (AES/RSA)"
            elif crypto_type in ('post_quantum', 'postquantum'):
                crypto_status = "[PQ-LOCK] POST-QUANTUM"
            else:
                crypto_status = f"[LOCK] {crypto_type}"
        
        mitm_status = ""
        if self.mitm_attacker:
            if log_entry.get("forged"):
                mitm_status = " [WARN] [MITM ATTACK SUCCESSFUL - MESSAGE FORGED]"
            elif log_entry.get("mitm_intercepted"):
                if crypto_type in ('post_quantum', 'postquantum'):
                    mitm_status = " [SAFE] [MITM BLOCKED - ENCRYPTION SECURE]"
                else:
                    mitm_status = " [WARN] [MITM INTERCEPTED]"
        
        text_part = message.get("display_text") or f"{sender_id} -> {receiver_id}"
        log_line = f"[MSG] {text_part} | {message_type} | {crypto_status}{mitm_status}"
        print(log_line)
        
        # Send to appropriate GUI
        is_attacker_message = (sender_id == "vehicle4") or log_entry.get("forged") or (mitm_status and "MITM" in mitm_status)
        if self.attacker_gui and is_attacker_message:
            try:
                self.attacker_gui.log(log_line)
            except:
                pass
        if self.normal_v2x_gui and not is_attacker_message:
            try:
                self.normal_v2x_gui.log(log_line)
            except:
                pass
        
        # Store message for GUI display
        current_time = traci.simulation.getTime()
        if sender_id not in self.recent_messages:
            self.recent_messages[sender_id] = []
        self.recent_messages[sender_id].append({
            "time": current_time,
            "to": receiver_id,
            "type": message_type,
            "crypto": crypto_status,
            "mitm": mitm_status,
            "text": text_part,
            "forged": log_entry.get("forged", False)
        })
        # Keep only last 3 messages per vehicle
        if len(self.recent_messages[sender_id]) > 3:
            self.recent_messages[sender_id] = self.recent_messages[sender_id][-3:]
        
        # Display message in SUMO GUI as vehicle label
        self._update_vehicle_gui_label(sender_id)
        
        self.messages.append(message)
        return message
    
    def _update_vehicle_gui_label(self, vehicle_id: str):
        """Update vehicle label in SUMO GUI to show recent messages and crypto status"""
        try:
            if vehicle_id not in self.vehicles:
                return
            
            vehicle = self.vehicles[vehicle_id]
            # Get recent messages
            recent = self.recent_messages.get(vehicle_id, [])
            
            # Build label text
            label_parts = [vehicle_id]
            
            # Add crypto mode indicator
            if self.crypto_mode == "postquantum":
                label_parts.append("[PQ-LOCK] PQ")
            else:
                label_parts.append("[LOCK] CL")
            
            # Add neighbor count
            if vehicle.neighbors:
                label_parts.append(f"[N]{len(vehicle.neighbors)}")
            
            # Add last message info if available
            if recent:
                last_msg = recent[-1]
                msg_short = last_msg["type"][:3]  # BSM -> BSM
                label_parts.append(f"->{last_msg['to'][-1]}")  # vehicle2 -> 2
                if last_msg.get("text"):
                    # Shorten text for label
                    snippet = last_msg["text"]
                    if len(snippet) > 22:
                        snippet = snippet[:22] + "..."
                    if last_msg.get("forged"):
                        snippet = f"[WARN] {snippet}"
                    label_parts.append(snippet)
            
            label_text = " | ".join(label_parts)
            
            # Update vehicle label in SUMO GUI
            try:
                traci.vehicle.setParameter(vehicle_id, "guiLabel", label_text)
            except:
                # Fallback: try setting as vehicle name
                try:
                    traci.vehicle.setParameter(vehicle_id, "name", label_text)
                except:
                    pass
        except:
            pass

    def _circle_points(self, center: tuple, radius: float, segments: int = 24) -> List[tuple]:
        """Generate points approximating a circle for SUMO polygons"""
        cx, cy = center
        points = []
        for i in range(segments):
            angle = 2 * math.pi * i / segments
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            points.append((x, y))
        return points

    def _update_communication_circle(self, vehicle_id: str, radius: float = None):
        """Draw or update a faint circle around a vehicle to show comms reach"""
        if vehicle_id not in self.vehicles:
            return
        radius = radius or self.communication_radius
        vehicle = self.vehicles[vehicle_id]
        circle_id = f"comm_{vehicle_id}"
        color = self.vehicle_colors.get(vehicle_id, (255, 255, 255))
        polygon_color = (color[0], color[1], color[2], 70)
        shape = self._circle_points(vehicle.position, radius)
        try:
            if circle_id in self.communication_circles:
                traci.polygon.setShape(circle_id, shape)
                traci.polygon.setColor(circle_id, polygon_color)
            else:
                traci.polygon.add(circle_id, shape, color=polygon_color, fill=True, layer=2)
                self.communication_circles[circle_id] = True
        except:
            # If something goes wrong creating polygon, skip silently
            return

    def _update_all_communication_circles(self):
        """Update communication circles for all active vehicles"""
        for vehicle_id in list(self.vehicles.keys()):
            try:
                self._update_communication_circle(vehicle_id)
            except:
                continue
    
    def check_interactions(self, current_time: float):
        """Check for vehicle interactions and log them based on specific rules"""
        # Identify active vehicles
        active_ids = [v for v in self.vehicles if v in traci.vehicle.getIDList()]
        mitm_id = None
        if self.mitm_attacker:
            mitm_id = getattr(self.mitm_attacker, "attacker_id", None)
        if not mitm_id:
            if "mitm_attacker" in active_ids:
                mitm_id = "mitm_attacker"
            elif "vehicle4" in active_ids:
                mitm_id = "vehicle4"
        mitm_active = bool(mitm_id)
        
        # Helper to get friendly name
        def get_name(vid):
            return self.vehicle_names.get(vid, vid)
            
        # Get neighbors for everyone
        neighbors_map = {}
        for vid in active_ids:
            neighbors_map[vid] = self.find_neighbors(vid)
            
        # Track current frame interactions to clean up old ones
        current_interactions = set()
        
        # 1. Check for Fake Alert (Purple in range of a victim who has NO other friends)
        # DISABLED: No automatic attacks - only user-initiated attacks via GUI
        # if mitm_active:
        #     mitm_neighbors = neighbors_map.get(mitm_id, [])
        #     for victim_id in mitm_neighbors:
        #         if victim_id == mitm_id: continue
        #         
        #         # Check if victim has other neighbors (excluding MITM)
        #         victim_neighbors = neighbors_map.get(victim_id, [])
        #         real_friends = [n for n in victim_neighbors if n != mitm_id and n != victim_id]
        #         
        #         if not real_friends:
        #             # Condition: Purple in range with only 1 car
        #             interaction_key = tuple(sorted([mitm_id, victim_id]) + ["fake_alert"])
        #             current_interactions.add(interaction_key)
        #             
        #             if interaction_key not in self.active_interactions:
        #                 self.send_v2v_message(
        #                     mitm_id,
        #                     victim_id,
        #                     "WARNING",
        #                     {"content": "STOP! accident ahead", "is_fake": True},
        #                     use_encryption=True,
        #                     display_text=f"{get_name(mitm_id)} -> {get_name(victim_id)}: Fake Alert STOP! accident ahead",
        #                     intercepted=False
        #                 )
        #                 self.active_interactions.add(interaction_key)
        
        # 2. Check for Normal Communication vs Interception
        # Iterate all pairs of non-attacker vehicles
        sorted_ids = sorted([v for v in active_ids if v != mitm_id])
        for i in range(len(sorted_ids)):
            for j in range(i + 1, len(sorted_ids)):
                id1 = sorted_ids[i]
                id2 = sorted_ids[j]
                
                # Check if they are in range of each other
                # (Assuming symmetric range for simplicity)
                if id2 in neighbors_map.get(id1, []):
                    # They are communicating
                    
                    # Check if MITM is intercepting
                    # Condition: Purple is in range (we assume of the pair/communication)
                    is_intercepted = False
                    if mitm_active:
                        mitm_neighbors = neighbors_map.get(mitm_id, [])
                        if (id1 in mitm_neighbors) or (id2 in mitm_neighbors):
                            is_intercepted = True
                    
                    if is_intercepted:
                        interaction_key = tuple(sorted([id1, id2]) + ["intercepted"])
                        current_interactions.add(interaction_key)
                        
                        if interaction_key not in self.active_interactions:
                            v = self.vehicles.get(id1)
                            if v:
                                px, py, spd = v.position[0], v.position[1], v.speed
                                self.send_v2v_message(
                                    id1,
                                    id2,
                                    "STATUS",
                                    {"position_x": px, "position_y": py, "speed": spd},
                                    use_encryption=True,
                                    display_text=f"{get_name(id1)} -> {get_name(id2)}: pos=({px:.1f},{py:.1f}), speed={spd:.2f}",
                                    intercepted=True
                                )
                            self.active_interactions.add(interaction_key)
                    else:
                        # Normal communication
                        interaction_key = tuple(sorted([id1, id2]) + ["normal"])
                        current_interactions.add(interaction_key)
                        
                        if interaction_key not in self.active_interactions:
                            v = self.vehicles.get(id1)
                            if v:
                                px, py, spd = v.position[0], v.position[1], v.speed
                                self.send_v2v_message(
                                    id1,
                                    id2,
                                    "STATUS",
                                    {"position_x": px, "position_y": py, "speed": spd},
                                    use_encryption=True,
                                    display_text=f"{get_name(id1)} -> {get_name(id2)}: pos=({px:.1f},{py:.1f}), speed={spd:.2f}",
                                    intercepted=False
                                )
                            self.active_interactions.add(interaction_key)

        # Cleanup: Remove interactions that are no longer happening
        # This allows the message to be printed again if they leave and come back
        # or if conditions change (e.g. MITM leaves -> becomes normal)
        self.active_interactions = self.active_interactions.intersection(current_interactions)

    def _handle_menu_action(self, action_key: str):
        """Handle menu actions for purple car"""
        all_active_vids = traci.vehicle.getIDList()
        if "vehicle4" not in traci.vehicle.getIDList():
            log_line = "[WARN]  Purple car (vehicle4) is not active yet!"
            print(log_line)
            if self.attacker_gui:
                try:
                    self.attacker_gui.log(log_line)
                except:
                    pass
            return
        
        all_active_vehicles = traci.vehicle.getIDList()
        active_vehicles = [vid for vid in all_active_vehicles if vid != "vehicle4"]  # For targets only
        if not active_vehicles:
            log_line = "[WARN]  No other vehicles to interact with!"
            print(log_line)
            if self.attacker_gui:
                try:
                    self.attacker_gui.log(log_line)
                except:
                    pass
            return
        
        # Get purple car position
        try:
            purple_pos = traci.vehicle.getPosition("vehicle4")
        except:
            log_line = "[ERROR] Could not get purple car position!"
            print(log_line)
            if self.attacker_gui:
                try:
                    self.attacker_gui.log(log_line)
                except:
                    pass
            return
        
        # Check if we are in post-quantum mode (attacks & data retrieval won't work!)
        if self.crypto_mode == "postquantum":
            log_line = "[FAIL] ACCESS DENIED! Post-Quantum Encryption is active! Cannot retrieve vehicle info or perform attacks!"
            print(log_line)
            if self.attacker_gui:
                try:
                    self.attacker_gui.log(log_line)
                except:
                    pass
            if self.normal_v2x_gui:
                try:
                    self.normal_v2x_gui.log("[SAFE] Vehicle info retrieval blocked by Post-Quantum Encryption!")
                except:
                    pass
            return
        
        if action_key == '4':
            # GET ALL ENCOUNTERED VEHICLE DATA
            print("\n[DATA] ALL ENCOUNTERED VEHICLE DATA:")
            if not self.purple_encountered_cars:
                log_line = "  No cars encountered yet!"
                print(log_line)
                if self.attacker_gui:
                    try:
                        self.attacker_gui.log(log_line)
                    except:
                        pass
                return
            for vid in self.purple_encountered_cars:
                if vid not in active_vehicles:
                    continue
                try:
                    pos = traci.vehicle.getPosition(vid)
                    speed = traci.vehicle.getSpeed(vid)
                    edge = traci.vehicle.getRoadID(vid)
                    
                    # Calculate distance to purple car
                    dx = purple_pos[0] - pos[0]
                    dy = purple_pos[1] - pos[1]
                    dist = (dx**2 + dy**2)**0.5
                    
                    name = self.vehicle_names.get(vid, vid)
                    owner = self.vehicle_owners.get(vid, "Unknown")
                    serial = self.vehicle_serial_numbers.get(vid, "Unknown")
                    ssn = self.owner_security_numbers.get(vid, "Unknown")
                    log_line1 = f"  {name} (Owner: {owner}):"
                    log_line2 = f"    Car Serial: {serial}"
                    log_line3 = f"    Owner Security Number: {ssn}"
                    log_line4 = f"    Position: ({pos[0]:.1f}, {pos[1]:.1f})"
                    log_line5 = f"    Speed: {speed:.2f} m/s"
                    log_line6 = f"    Edge: {edge}"
                    log_line7 = f"    Distance to purple: {dist:.1f}m {'(IN RANGE)' if dist <= COMMUNICATION_RANGE else '(OUT OF RANGE)'}"
                    print(log_line1)
                    print(log_line2)
                    print(log_line3)
                    print(log_line4)
                    print(log_line5)
                    print(log_line6)
                    print(log_line7)
                    if self.attacker_gui:
                        try:
                            self.attacker_gui.log(log_line1)
                            self.attacker_gui.log(log_line2)
                            self.attacker_gui.log(log_line3)
                            self.attacker_gui.log(log_line4)
                            self.attacker_gui.log(log_line5)
                            self.attacker_gui.log(log_line6)
                            self.attacker_gui.log(log_line7)
                        except:
                            pass
                except:
                    pass
            print()
            return
        
        if action_key == '5':
            # GET SELECTED TARGET DATA ONLY
            if not self.selected_target:
                log_line = "[WARN] No target selected! Please select a target first!"
                print(log_line)
                if self.attacker_gui:
                    try:
                        self.attacker_gui.log(log_line)
                    except:
                        pass
                return
            if self.selected_target not in active_vehicles:
                log_line = f"[WARN] Selected target {self.vehicle_names.get(self.selected_target, self.selected_target)} no longer exists!"
                print(log_line)
                if self.attacker_gui:
                    try:
                        self.attacker_gui.log(log_line)
                    except:
                        pass
                return
            vid = self.selected_target
            try:
                pos = traci.vehicle.getPosition(vid)
                speed = traci.vehicle.getSpeed(vid)
                edge = traci.vehicle.getRoadID(vid)
                
                # Calculate distance to purple car
                dx = purple_pos[0] - pos[0]
                dy = purple_pos[1] - pos[1]
                dist = (dx**2 + dy**2)**0.5
                
                name = self.vehicle_names.get(vid, vid)
                owner = self.vehicle_owners.get(vid, "Unknown")
                serial = self.vehicle_serial_numbers.get(vid, "Unknown")
                ssn = self.owner_security_numbers.get(vid, "Unknown")
                log_line1 = f"\n[DATA] SELECTED TARGET DATA: {name} (Owner: {owner})"
                log_line2 = f"  Car Serial: {serial}"
                log_line3 = f"  Owner Security Number: {ssn}"
                log_line4 = f"  Position: ({pos[0]:.1f}, {pos[1]:.1f})"
                log_line5 = f"  Speed: {speed:.2f} m/s"
                log_line6 = f"  Edge: {edge}"
                log_line7 = f"  Distance to purple: {dist:.1f}m {'(IN RANGE)' if dist <= COMMUNICATION_RANGE else '(OUT OF RANGE)'}"
                print(log_line1)
                print(log_line2)
                print(log_line3)
                print(log_line4)
                print(log_line5)
                print(log_line6)
                print(log_line7)
                if self.attacker_gui:
                    try:
                        self.attacker_gui.log(log_line1)
                        self.attacker_gui.log(log_line2)
                        self.attacker_gui.log(log_line3)
                        self.attacker_gui.log(log_line4)
                        self.attacker_gui.log(log_line5)
                        self.attacker_gui.log(log_line6)
                        self.attacker_gui.log(log_line7)
                    except:
                        pass
            except Exception as e:
                log_line = f"[ERROR] Could not retrieve data for target: {str(e)}"
                print(log_line)
                if self.attacker_gui:
                    try:
                        self.attacker_gui.log(log_line)
                    except:
                        pass
            print()
            return
        
        # For actions 1-3, need selected target
        if not self.selected_target:
            log_line = "[WARN]  No target selected! Choose option 6 first!"
            print(log_line)
            if self.attacker_gui:
                try:
                    self.attacker_gui.log(log_line)
                except:
                    pass
            return
        
        if self.selected_target not in active_vehicles:
            log_line = f"[WARN]  Selected target {self.vehicle_names.get(self.selected_target, self.selected_target)} no longer exists!"
            print(log_line)
            if self.attacker_gui:
                try:
                    self.attacker_gui.log(log_line)
                except:
                    pass
            self.selected_target = None
            return
        
        target_vehicle = self.selected_target
        target_name = self.vehicle_names.get(target_vehicle, target_vehicle)
        
        # Get purple car's current position first
        purple_pos = None
        if "vehicle4" not in all_active_vehicles:
            log_line = "[ERROR] Purple Car (vehicle4) is not active!"
            print(log_line)
            if self.attacker_gui:
                try:
                    self.attacker_gui.log(log_line)
                except:
                    pass
            return
        try:
            purple_pos = traci.vehicle.getPosition("vehicle4")
        except Exception as e:
            log_line = f"[ERROR] Could not get Purple Car position: {e}"
            print(log_line)
            if self.attacker_gui:
                try:
                    self.attacker_gui.log(log_line)
                except:
                    pass
            return
        
        # Check if target has been encountered before (not range, just encounter)
        if target_vehicle not in self.purple_encountered_cars:
            log_line = f"[WARN]  {target_name} has not been encountered yet! Purple car must be in range of it at least once before attacking!"
            print(log_line)
            if self.attacker_gui:
                try:
                    self.attacker_gui.log(log_line)
                except:
                    pass
            return
        
        if action_key == '1':
            # Send FAKE WARNING - Make target INSTANTLY go 25 m/s
            self.send_v2v_message(
                "vehicle4",
                target_vehicle,
                "WARNING",
                {"content": "You're driving too slow! Be faster!", "is_fake": True},
                use_encryption=True,
                display_text=f"Purple Car -> {target_name}: 'You're driving too slow! Be faster!'",
                intercepted=False
            )
            self.controlled_vehicles[target_vehicle] = 25  # Lock to 25 m/s
            traci.vehicle.setSpeed(target_vehicle, 25)
            # Disable SUMO's automatic speed control
            traci.vehicle.setSpeedMode(target_vehicle, 0)
            log_line = f"[ACTION] {target_name} speed LOCKED to 25.0 m/s!"
            print(log_line)
            if self.attacker_gui:
                try:
                    self.attacker_gui.log(log_line)
                except:
                    pass
        
        elif action_key == '2':
            # Send ACCIDENT AHEAD! - Make target stop completely
            self.send_v2v_message(
                "vehicle4",
                target_vehicle,
                "DENM",
                {"content": "ACCIDENT AHEAD! Stop immediately!", "event_type": "accident", "is_fake": True},
                use_encryption=True,
                display_text=f"Purple Car -> {target_name}: 'ACCIDENT AHEAD! Stop immediately!'",
                intercepted=False
            )
            self.controlled_vehicles[target_vehicle] = 0  # Lock to 0 m/s
            traci.vehicle.setSpeed(target_vehicle, 0)
            # Disable SUMO's automatic speed control
            traci.vehicle.setSpeedMode(target_vehicle, 0)
            log_line = f"[ACTION] {target_name} LOCKED to 0 m/s (stopped)!"
            print(log_line)
            if self.attacker_gui:
                try:
                    self.attacker_gui.log(log_line)
                except:
                    pass
        
        elif action_key == '3':
            # Send SLOW DOWN - Make target INSTANTLY go very slow (2 m/s)
            self.send_v2v_message(
                "vehicle4",
                target_vehicle,
                "WARNING",
                {"content": "SLOW DOWN! Hazard detected!", "is_fake": True},
                use_encryption=True,
                display_text=f"Purple Car -> {target_name}: 'SLOW DOWN! Hazard detected!'",
                intercepted=False
            )
            self.controlled_vehicles[target_vehicle] = 2  # Lock to 2 m/s
            traci.vehicle.setSpeed(target_vehicle, 2)
            # Disable SUMO's automatic speed control
            traci.vehicle.setSpeedMode(target_vehicle, 0)
            log_line = f"[ACTION] {target_name} speed LOCKED to 2.0 m/s!"
            print(log_line)
            if self.attacker_gui:
                try:
                    self.attacker_gui.log(log_line)
                except:
                    pass

    def _show_main_menu(self):
        """Show main menu"""
        print("\n" + "="*60)
        print("PURPLE CAR ACTION MENU")
        print("="*60)
        
        # Show selected target
        if self.selected_target:
            target_name = self.vehicle_names.get(self.selected_target, self.selected_target)
            print(f"[*] Selected Target: {target_name}")
        else:
            print("[!] No target selected! Choose option 5 first!")
        
        print("\n1 - Send FAKE WARNING")
        print("2 - Send ACCIDENT AHEAD!")
        print("3 - Send SLOW DOWN")
        print("4 - Get VEHICLE DATA")
        print("5 - Select Target Vehicle")
        print("M/Q - Close menu")
        print("="*60 + "\n")

    def _show_target_selection(self):
        """Show target selection menu"""
        active_vehicles = [vid for vid in traci.vehicle.getIDList() if vid != "vehicle4"]
        print("\n" + "="*60)
        print("SELECT TARGET VEHICLE")
        print("="*60)
        if not active_vehicles:
            print("[WARN] No other vehicles available!")
        else:
            for i, vid in enumerate(active_vehicles):
                name = self.vehicle_names.get(vid, vid)
                # Get distance info
                try:
                    purple_pos = traci.vehicle.getPosition("vehicle4")
                    target_pos = traci.vehicle.getPosition(vid)
                    dx = purple_pos[0] - target_pos[0]
                    dy = purple_pos[1] - target_pos[1]
                    dist = (dx**2 + dy**2)**0.5
                    in_range = dist <= COMMUNICATION_RANGE
                    range_info = f" [{'IN RANGE' if in_range else 'OUT OF RANGE'} - {dist:.1f}m]"
                except:
                    range_info = ""
                
                print(f"{i+1} - {name}{range_info}")
        print("\nM/Q - Back to main menu")
        print("="*60 + "\n")

    def run_simulation_step(self):
        """Run one simulation step"""
        traci.simulationStep()
        current_time = traci.simulation.getTime()
        
        # Prevent vehicles from disappearing by teleporting them back
        active_vehicle_ids = traci.vehicle.getIDList()
        for vid in active_vehicle_ids:
            try:
                # Check if vehicle is at the end of its route
                route_index = traci.vehicle.getRouteIndex(vid)
                route = traci.vehicle.getRoute(vid)
                if route_index >= len(route) - 1:
                    # Teleport back to start of route
                    start_edge = route[0]
                    traci.vehicle.moveTo(vid, start_edge, 0)
                    # If vehicle is controlled, keep its target speed
                    if vid in self.controlled_vehicles:
                        traci.vehicle.setSpeed(vid, self.controlled_vehicles[vid])
                        traci.vehicle.setSpeedMode(vid, 0)
                    else:
                        traci.vehicle.setSpeed(vid, -1)  # Let SUMO control
            except:
                pass
        
        # Keep controlled vehicles at their target speed only in classical crypto mode
        if self.crypto_mode == "classical":
            for vid, target_speed in self.controlled_vehicles.items():
                if vid in active_vehicle_ids:
                    try:
                        traci.vehicle.setSpeed(vid, target_speed)
                        traci.vehicle.setSpeedMode(vid, 0)  # Disable SUMO's speed control
                    except:
                        pass
        
        # Track cars purple car has been in range with
        if "vehicle4" in active_vehicle_ids:
            try:
                purple_pos = traci.vehicle.getPosition("vehicle4")
                for vid in active_vehicle_ids:
                    if vid == "vehicle4":
                        continue
                    try:
                        target_pos = traci.vehicle.getPosition(vid)
                        dx = purple_pos[0] - target_pos[0]
                        dy = purple_pos[1] - target_pos[1]
                        dist = (dx**2 + dy**2)**0.5
                        if dist <= COMMUNICATION_RANGE:
                            self.purple_encountered_cars.add(vid)
                    except:
                        continue
            except:
                pass
        
        # Check for collisions and handle them
        try:
            colliding_ids = traci.simulation.getCollidingVehiclesIDList()
            if colliding_ids:
                # Get friendly names
                names = [self.vehicle_names.get(vid, vid) for vid in colliding_ids]
                log_line = f"[COLLISION] Crash between: {' and '.join(names)} at time {current_time:.1f}s"
                print(log_line)
                if self.attacker_gui:
                    try:
                        self.attacker_gui.log(log_line)
                    except:
                        pass
                if self.normal_v2x_gui:
                    try:
                        self.normal_v2x_gui.log(log_line)
                    except:
                        pass
                
                # Stop all colliding vehicles and keep them stopped
                for vid in colliding_ids:
                    try:
                        traci.vehicle.setSpeed(vid, 0)
                        traci.vehicle.setSpeedMode(vid, 0)
                        # Change color to black to indicate a crash
                        traci.vehicle.setColor(vid, (0, 0, 0))
                        log_line2 = f"[STOP] {self.vehicle_names.get(vid, vid)} stopped due to collision"
                        print(log_line2)
                        if self.attacker_gui:
                            self.attacker_gui.log(log_line2)
                        if self.normal_v2x_gui:
                            self.normal_v2x_gui.log(log_line2)
                        
                        # Remove them from controlled vehicles list if present
                        if vid in self.controlled_vehicles:
                            del self.controlled_vehicles[vid]
                    except:
                        pass
        except Exception as e:
            pass
        
        # Terminal keyboard menu disabled - using GUI instead
        
        # Get list of vehicles that actually exist in SUMO
        active_vehicle_ids = traci.vehicle.getIDList()
        
        # Update only vehicles that exist in SUMO
        for vehicle_id in list(self.vehicles.keys()):
            if vehicle_id in active_vehicle_ids:
                try:
                    old_speed = self.vehicles[vehicle_id].speed
                    self.vehicles[vehicle_id].update()
                    
                    # Check if vehicle stopped
                    # if old_speed > 0.1 and self.vehicles[vehicle_id].speed < 0.1:
                    #    print(f"[STOP] {vehicle_id} STOPPED at time {current_time:.1f}s")
                    
                    # Update neighbors
                    self.vehicles[vehicle_id].neighbors = self.find_neighbors(vehicle_id)
                    
                    # Update GUI label with current status
                    self._update_vehicle_gui_label(vehicle_id)
                    # Update on-screen communication radius
                    self._update_communication_circle(vehicle_id)
                    
                    # Send V2V messages to neighbors (every 2 seconds)
                    # REPLACED BY NEW INTERACTION LOGIC IN check_interactions()
                    # We keep this block only for visualization/GUI updates if needed,
                    # but we disable the printing/logging here to avoid spam/duplication.
                    pass
                        
                    # If vehicle completed route, make it loop by changing route to loop back
                    try:
                        route_id = traci.vehicle.getRouteID(vehicle_id)
                        route_index = traci.vehicle.getRouteIndex(vehicle_id)
                        route = traci.route.getEdges(route_id)
                        
                        # Only extend route if it has MULTIPLE edges
                        # Single-edge routes complete instantly and cause infinite restart loops
                        if len(route) > 1 and route_index >= len(route) - 1:
                            # Vehicle completed multi-edge route, extend it to loop back
                            try:
                                # Get current edge
                                current_edge = traci.vehicle.getRoadID(vehicle_id)
                                
                                # Only extend if vehicle is actually at the last edge
                                if current_edge == route[-1]:
                                    # Try to find a route back to the start edge
                                    start_edge = route[0]
                                    try:
                                        # Use findRoute to find path back to start
                                        loop_route_result = traci.simulation.findRoute(current_edge, start_edge)
                                        if loop_route_result and loop_route_result.length > 0:
                                            loop_edges = [e for e in loop_route_result.edges if not e.startswith(":")]
                                            if loop_edges:
                                                # Create extended route: original + loop back
                                                extended_route = route + loop_edges
                                                # Update route
                                                try:
                                                    traci.route.delete(route_id)
                                                except:
                                                    pass
                                                traci.route.add(route_id, extended_route)
                                                # Change vehicle route
                                                traci.vehicle.setRoute(vehicle_id, extended_route)
                                                print(f"  [LOOP] {vehicle_id} route extended ({len(extended_route)} edges)")
                                                continue  # Success, move to next vehicle
                                    except:
                                        pass
                                    # If can't extend, don't restart - let vehicle finish naturally
                            except:
                                pass
                        # Single-edge routes: Skip restart logic completely to avoid infinite loop
                    except:
                        pass
                        
                except traci.exceptions.TraCIException:
                    # Vehicle may have left
                    if vehicle_id in self.vehicles:
                        del self.vehicles[vehicle_id]
            # If vehicle is not active yet, keep it in our list but don't update
        
        # Call the centralized interaction logic to print messages
        self.check_interactions(current_time)

        return current_time
    
    def _send_periodic_messages(self, vehicle_id: str, current_time: float):
        """Send periodic V2V messages to neighbors"""
        vehicle = self.vehicles[vehicle_id]
        
        # Create BSM (Basic Safety Message)
        bsm = self.message_handler.create_bsm(
            vehicle_id,
            vehicle.position,
            vehicle.speed,
            vehicle.heading
        )
        
        # Send to first neighbor (or broadcast)
        if vehicle.neighbors:
            receiver = vehicle.neighbors[0]
            self.send_v2v_message(
                vehicle_id,
                receiver,
                "BSM",
                bsm.to_dict(),
                use_encryption=True
            )
    
    def run(self):
        """Run the complete simulation"""
        self.start_simulation()
        
        # Wait for SUMO to initialize
        time.sleep(1)
        traci.simulationStep()  # Take one step to initialize
        
        # Get network edges for routing
        edges = self.get_network_edges()
        if not edges:
            print("[ERROR] No edges found in network!")
            return
        
        # Filter out internal edges (those starting with ":")
        road_edges = [e for e in edges if not e.startswith(":")]
        
        if not road_edges:
            print("[ERROR] No road edges found!")
            print(f"All edges: {edges[:10]}...")  # Show first 10 edges for debugging
            return
        
        print(f"[OK] Found {len(road_edges)} road edges")
        print(f"Sample edges: {road_edges[:5]}")  # Debug: show first 5 edges
        
        # Try to find valid routes using SUMO's route finding
        # Get junctions to find start/end points
        junctions = traci.junction.getIDList()
        print(f"[OK] Found {len(junctions)} junctions")
        
        # Use a simpler approach: find connected edge sequences directly
        print("\n[SEARCH] Attempting to add vehicles...")
        current_time = traci.simulation.getTime()
        
        def find_connected_route(start_edge: str, max_length: int = 10) -> List[str]:
            """Find a connected route using SUMO's findRoute - validates entire route"""
            # Start with just the first edge
            route = [start_edge]
            
            # Try to extend the route by finding valid connected edges
            for _ in range(max_length - 1):
                try:
                    current_edge = route[-1]
                    # Get the "to" junction of current edge
                    to_junction = traci.edge.getToJunction(current_edge)
                    
                    # Get all outgoing edges from this junction
                    outgoing_edges = []
                    for edge in road_edges:
                        try:
                            from_junction = traci.edge.getFromJunction(edge)
                            # Check if it's a reverse edge (e.g., A1A0 -> A0A1)
                            is_reverse = False
                            if len(current_edge) == len(edge) and len(current_edge) >= 4:
                                # Check if it's the reverse (A1A0 -> A0A1)
                                # Split edge names: A1A0 = A1 -> A0, A0A1 = A0 -> A1
                                # They're reverse if: current starts with edge's end, and current ends with edge's start
                                current_start = current_edge[:len(current_edge)//2]
                                current_end = current_edge[len(current_edge)//2:]
                                edge_start = edge[:len(edge)//2]
                                edge_end = edge[len(edge)//2:]
                                if current_start == edge_end and current_end == edge_start:
                                    is_reverse = True
                            
                            # Must connect at junction AND not be the reverse of current edge
                            if (from_junction == to_junction and 
                                edge != current_edge and 
                                edge not in route and
                                not is_reverse):
                                outgoing_edges.append(edge)
                        except:
                            continue
                    
                    if not outgoing_edges:
                        break
                    
                    # Use SUMO's findRoute to validate the connection
                    best_edge = None
                    for candidate in outgoing_edges[:10]:  # Try more candidates
                        try:
                            # Use findRoute to validate connection from current edge to candidate
                            route_result = traci.simulation.findRoute(current_edge, candidate)
                            if route_result and route_result.length > 0:
                                # Get the actual route edges (filter internal edges)
                                route_edges = [e for e in route_result.edges if not e.startswith(":")]
                                # The candidate should be in the route, or the route should end at candidate's junction
                                if candidate in route_edges:
                                    best_edge = candidate
                                    break
                                # Also check if route ends at candidate's start junction
                                elif len(route_edges) > 0:
                                    candidate_from = traci.edge.getFromJunction(candidate)
                                    last_edge = route_edges[-1]
                                    last_edge_to = traci.edge.getToJunction(last_edge)
                                    if candidate_from == last_edge_to:
                                        best_edge = candidate
                                        break
                        except Exception as e:
                            # If findRoute fails, try next candidate
                            continue
                    
                    if best_edge and best_edge != route[-1]:  # Don't add duplicate consecutive edges
                        route.append(best_edge)
                    else:
                        # No valid connection found, stop extending route
                        break
                except Exception as e:
                    break
            
            # Remove duplicate consecutive edges
            cleaned_route = []
            for edge in route:
                if not cleaned_route or edge != cleaned_route[-1]:
                    cleaned_route.append(edge)
            route = cleaned_route
            
            # Validate the entire route using findRoute
            if len(route) > 1:
                try:
                    # Check if we can actually traverse from first to last edge
                    route_result = traci.simulation.findRoute(route[0], route[-1])
                    if route_result and route_result.length > 0:
                        # Get the validated route edges
                        validated_edges = [e for e in route_result.edges if not e.startswith(":")]
                        # Remove duplicates from validated route
                        cleaned_validated = []
                        for edge in validated_edges:
                            if not cleaned_validated or edge != cleaned_validated[-1]:
                                cleaned_validated.append(edge)
                        # If validated route matches our route (or is shorter), use it
                        if len(cleaned_validated) > 0 and len(cleaned_validated) <= len(route):
                            route = cleaned_validated
                except:
                    pass
            
            # Try to make route loop by finding path back to start
            if len(route) > 0:
                try:
                    start_edge = route[0]
                    end_edge = route[-1]
                    # Try to find route back to start to create a loop
                    if end_edge != start_edge:
                        loop_result = traci.simulation.findRoute(end_edge, start_edge)
                        if loop_result and loop_result.length > 0:
                            loop_edges = [e for e in loop_result.edges if not e.startswith(":")]
                            # Remove duplicates and ensure loop doesn't start with same edge as route ends
                            cleaned_loop = []
                            for edge in loop_edges:
                                if edge != end_edge and (not cleaned_loop or edge != cleaned_loop[-1]):
                                    cleaned_loop.append(edge)
                            if cleaned_loop:
                                # Return route + loop back (creates continuous loop)
                                return route + cleaned_loop
                except:
                    pass
            
            return route
        
        # Create routes for vehicles using connected edge sequences
        if len(road_edges) >= 3:
            # Vehicle 1: Use first edge and find connected route
            try:
                route1_edges = find_connected_route(road_edges[0], max_length=5)
                if len(route1_edges) < 2:
                    # If route is too short, just use the edge
                    route1_edges = [road_edges[0]]
                print(f"  Route1: {route1_edges}")
                self.add_vehicle("vehicle1", route1_edges, current_time + 1, (255, 0, 0))
            except Exception as e:
                print(f"  Failed to add vehicle1: {e}")
                self.add_vehicle("vehicle1", [road_edges[0]], current_time + 1, (255, 0, 0))
            
            # Vehicle 2: Use second edge and find connected route
            try:
                if len(road_edges) > 1:
                    route2_edges = find_connected_route(road_edges[1], max_length=5)
                    if len(route2_edges) < 2:
                        route2_edges = [road_edges[1]]
                    print(f"  Route2: {route2_edges}")
                    self.add_vehicle("vehicle2", route2_edges, current_time + 3, (0, 255, 0))
                else:
                    self.add_vehicle("vehicle2", [road_edges[0]], current_time + 3, (0, 255, 0))
            except Exception as e:
                print(f"  Failed to add vehicle2: {e}")
                self.add_vehicle("vehicle2", [road_edges[min(1, len(road_edges)-1)]], current_time + 3, (0, 255, 0))
            
            # Vehicle 3: Use a different edge (try edge 3, 4, or 5 to avoid conflicts)
            print(f"  Attempting to add vehicle3 (blue)...")
            vehicle3_added = False
            try:
                # Try edges 2, 3, 4, 5... until we find one that works
                for idx in range(2, min(len(road_edges), 8)):
                    try:
                        test_edge = road_edges[idx]
                        print(f"    Trying edge {idx}: {test_edge}")
                        # Try to create a simple route with this edge
                        route3_edges = find_connected_route(test_edge, max_length=3)
                        if len(route3_edges) < 1:
                            route3_edges = [test_edge]
                        print(f"  Route3: {route3_edges} (using edge {idx})")
                        self.add_vehicle("vehicle3", route3_edges, current_time + 5, (0, 0, 255))
                        vehicle3_added = True
                        print(f"  [OK] Vehicle3 added successfully")
                        break  # Success, exit loop
                    except Exception as e:
                        print(f"    [ERROR] Failed with edge {idx}: {e}")
                        continue
                
                # If all attempts failed, try with simple single edge
                if not vehicle3_added:
                    print(f"  All route attempts failed, trying simple single edge for vehicle3")
                    for idx in range(2, min(len(road_edges), 8)):
                        try:
                            self.add_vehicle("vehicle3", [road_edges[idx]], current_time + 5, (0, 0, 255))
                            vehicle3_added = True
                            print(f"  [OK] Vehicle3 added with single edge {idx}: {road_edges[idx]}")
                            break
                        except Exception as e:
                            print(f"    [ERROR] Failed with single edge {idx}: {e}")
                            continue
            except Exception as e:
                print(f"  [ERROR] Failed to add vehicle3: {e}")
                import traceback
                traceback.print_exc()
            
            if not vehicle3_added:
                print(f"  [WARN]  WARNING: Could not add vehicle3 after all attempts!")
            
            # Vehicle 4: Purple vehicle
            print(f"  Attempting to add vehicle4 (purple)...")
            vehicle4_added = False
            try:
                # Try edges 3, 4, 5... until we find one that works
                for idx in range(3, min(len(road_edges), 10)):
                    try:
                        test_edge = road_edges[idx]
                        print(f"    Trying edge {idx}: {test_edge}")
                        # Try to create a simple route with this edge
                        route4_edges = find_connected_route(test_edge, max_length=20)
                        if len(route4_edges) < 1:
                            route4_edges = [test_edge]
                        print(f"  Route4: {route4_edges} (using edge {idx})")
                        # Purple color: (128, 0, 128)
                        self.add_vehicle("vehicle4", route4_edges, current_time + 7, (128, 0, 128))
                        vehicle4_added = True
                        print(f"  [OK] Vehicle4 added successfully")
                        self.mitm_attacker = MITMAttacker("vehicle4", use_quantum_attack=True)
                        break  # Success, exit loop
                    except Exception as e:
                        print(f"    [ERROR] Failed with edge {idx}: {e}")
                        continue
                
                # If all attempts failed, try with simple single edge
                if not vehicle4_added:
                    print(f"  All route attempts failed, trying simple single edge for vehicle4")
                    for idx in range(3, min(len(road_edges), 10)):
                        try:
                            self.add_vehicle("vehicle4", [road_edges[idx]], current_time + 7, (128, 0, 128))
                            vehicle4_added = True
                            print(f"  [OK] Vehicle4 added with single edge {idx}: {road_edges[idx]}")
                            self.mitm_attacker = MITMAttacker("vehicle4", use_quantum_attack=True)
                            break
                        except Exception as e:
                            print(f"    [ERROR] Failed with single edge {idx}: {e}")
                            continue
            except Exception as e:
                print(f"  [ERROR] Failed to add vehicle4: {e}")
            
            if not vehicle4_added:
                print(f"  [WARN]  WARNING: Could not add vehicle4 after all attempts!")
            
            # Add additional vehicles (5-12)
            additional_vehicles = [
                ("vehicle5", (0, 128, 0), 10),  # Dark Green Truck
                ("vehicle6", (255, 128, 0), 15),  # Orange Car
                ("vehicle7", (0, 128, 255), 18),  # Cyan Car
                ("vehicle8", (128, 0, 128), 22),  # Purple Truck
                ("vehicle9", (128, 128, 0), 25),  # Olive Car
                ("vehicle10", (128, 0, 0), 30),  # Maroon Car
                ("vehicle11", (0, 128, 128), 35),  # Teal Truck
                ("vehicle12", (128, 128, 128), 40)  # Grey Car
            ]
            
            for veh_id, color, offset in additional_vehicles:
                try:
                    edge_idx = (int(veh_id.replace("vehicle", "")) - 1) % len(road_edges)
                    test_edge = road_edges[edge_idx]
                    route_edges = find_connected_route(test_edge, max_length=3)
                    if len(route_edges) < 1:
                        route_edges = [test_edge]
                    self.add_vehicle(veh_id, route_edges, current_time + offset, color)
                    print(f"  [OK] {self.vehicle_names.get(veh_id, veh_id)} added successfully")
                except Exception as e:
                    try:
                        edge_idx = (int(veh_id.replace("vehicle", "")) - 1) % len(road_edges)
                        self.add_vehicle(veh_id, [road_edges[edge_idx]], current_time + offset, color)
                        print(f"  [OK] {self.vehicle_names.get(veh_id, veh_id)} added with single edge")
                    except Exception as e2:
                        print(f"  [WARN] Failed to add {self.vehicle_names.get(veh_id, veh_id)}: {e2}")
        else:
            # Fallback: use single edges
            print("  Not enough junctions, using single edges...")
            self.add_vehicle("vehicle1", [road_edges[0]], current_time + 1, (255, 0, 0))
            if len(road_edges) > 1:
                self.add_vehicle("vehicle2", [road_edges[1]], current_time + 3, (0, 255, 0))
            if len(road_edges) > 2:
                self.add_vehicle("vehicle3", [road_edges[2]], current_time + 5, (0, 0, 255))
            if len(road_edges) > 3:
                self.add_vehicle("vehicle4", [road_edges[3]], current_time + 7, (128, 0, 128))
            
            # Add additional vehicles in fallback mode too
            additional_vehicles = [
                ("vehicle5", (0, 128, 0), 10),
                ("vehicle6", (255, 128, 0), 15),
                ("vehicle7", (0, 128, 255), 18),
                ("vehicle8", (128, 0, 128), 22),
                ("vehicle9", (128, 128, 0), 25),
                ("vehicle10", (128, 0, 0), 30),
                ("vehicle11", (0, 128, 128), 35),
                ("vehicle12", (128, 128, 128), 40)
            ]
            
            for veh_id, color, offset in additional_vehicles:
                try:
                    edge_idx = (int(veh_id.replace("vehicle", "")) - 1) % len(road_edges)
                    self.add_vehicle(veh_id, [road_edges[edge_idx]], current_time + offset, color)
                    print(f"  [OK] {self.vehicle_names.get(veh_id, veh_id)} added successfully")
                except Exception as e:
                    print(f"  [WARN] Failed to add {self.vehicle_names.get(veh_id, veh_id)}: {e}")
        
        # Wait a moment for vehicles to be processed by SUMO
        time.sleep(0.5)
        
        # Advance simulation a few steps to let vehicles spawn
        for _ in range(5):
            try:
                traci.simulationStep()
            except:
                break
        
        # Continue with simulation
        self._continue_simulation(road_edges)
    
    def _are_edges_connected(self, edge1: str, edge2: str) -> bool:
        """Check if two edges are connected (edge1's end connects to edge2's start)"""
        try:
            # Get edge information
            to_junction1 = traci.edge.getToJunction(edge1)
            from_junction2 = traci.edge.getFromJunction(edge2)
            return to_junction1 == from_junction2
        except:
            return False
    
    def _find_connected_route(self, edges: List[str], start_idx: int = 0, max_length: int = 5) -> List[str]:
        """Find a valid connected route starting from a given edge using SUMO's route finder"""
        if start_idx >= len(edges) or not edges:
            return [edges[0]] if edges else []
        
        start_edge = edges[start_idx]
        
        try:
            # Get junctions from the start edge
            from_junction = traci.edge.getFromJunction(start_edge)
            to_junction = traci.edge.getToJunction(start_edge)
            
            # Try to find a route that goes from the end of this edge to another junction
            # Get all junctions
            all_junctions = traci.junction.getIDList()
            
            # Try to find a route to a different junction
            for target_junction in all_junctions[:10]:  # Try first 10 junctions
                if target_junction != from_junction and target_junction != to_junction:
                    try:
                        # Use SUMO's findRoute
                        route_result = traci.simulation.findRoute(to_junction, target_junction)
                        if route_result and len(route_result.edges) > 0:
                            # Filter out internal edges
                            route_edges = [e for e in route_result.edges if not e.startswith(":")]
                            if route_edges:
                                # Prepend the start edge (if it's not internal)
                                if not start_edge.startswith(":"):
                                    full_route = [start_edge] + route_edges
                                else:
                                    full_route = route_edges
                                if len(full_route) <= max_length:
                                    return full_route
                    except:
                        continue
            
            # If no route found, try to find a route back to start (loop)
            try:
                route_result = traci.simulation.findRoute(to_junction, from_junction)
                if route_result and len(route_result.edges) > 0:
                    # Filter out internal edges
                    route_edges = [e for e in route_result.edges if not e.startswith(":")]
                    if route_edges:
                        if not start_edge.startswith(":"):
                            full_route = [start_edge] + route_edges
                        else:
                            full_route = route_edges
                    if len(full_route) <= max_length:
                        return full_route
            except:
                pass
            
            # Fallback: just return the single edge
            return [start_edge]
        except:
            # If anything fails, return single edge
            return [start_edge]
    
    def _create_loop_route(self, edges: List[str], start_edge: str, max_edges: int = 10) -> List[str]:
        """Create a looping route by finding connected edges"""
        route = [start_edge]
        current_edge = start_edge
        visited = {start_edge}
        
        # Try to build a route that loops back
        for _ in range(max_edges - 1):
            # Find next connected edge
            next_edge = None
            try:
                to_junction = traci.edge.getToJunction(current_edge)
                
                # Find an edge that starts from this junction
                for edge in edges:
                    if edge not in visited:
                        try:
                            from_junction = traci.edge.getFromJunction(edge)
                            if from_junction == to_junction:
                                next_edge = edge
                                break
                        except:
                            continue
                
                if next_edge:
                    route.append(next_edge)
                    visited.add(next_edge)
                    current_edge = next_edge
                    
                    # Try to loop back to start
                    try:
                        if traci.edge.getToJunction(current_edge) == traci.edge.getFromJunction(start_edge):
                            # We can loop back!
                            route.append(start_edge)
                            break
                    except:
                        pass
                else:
                    break
            except:
                break
        
        # If we have at least 3 edges, return the route
        if len(route) >= 3:
            return route
        elif len(route) >= 2:
            # Try to make it loop by adding the first edge again
            return route + [route[0]]
        else:
            return route
    
    def _continue_simulation(self, road_edges: List[str]):
        """Continue simulation after vehicles are added"""
        # Check if any vehicles were added
        print(f"\n[DATA] Vehicles registered: {len(self.vehicles)}")
        if len(self.vehicles) == 0:
            print("[WARN]  No vehicles were added! Check edge connectivity.")
            print(f"Available edges: {road_edges[:10]}")
            return
        
        # Run simulation
        print("\n[CAR] Starting simulation...")
        print(f"   Running for {SIMULATION_END} seconds ({SIMULATION_END//60} minutes)...")
        print(f"\n[MENU] CRYPTO SCHEDULE:")
        print(f"   [LOCK] 0-90s:     CLASSICAL (AES/RSA) - Vulnerable to quantum attacks")
        print(f"   [PQ-LOCK] 90-300s:   POST-QUANTUM (Quantum-Resistant) - Safe from quantum attacks")
        print(f"\n[CAR] VEHICLES:")
        print(f"   Vehicle1: RED")
        print(f"   Vehicle2: GREEN")
        print(f"   Vehicle3: BLUE")
        print(f"   Vehicle4: PURPLE")
        print(f"\n[MENU] CONTROLS:")
        print(f"   M - Open/Close Action Menu")
        print()
        step = 0
        
        try:
            while True:  # Run until time limit
                try:
                    # Check if connection is still alive
                    try:
                        current_time = traci.simulation.getTime()
                    except:
                        print("\n[WARN]  TraCI connection lost")
                        break
                    
                    # Check if we've reached the time limit
                    if current_time >= SIMULATION_END:
                        print(f"\n[TIME]  Reached time limit: {SIMULATION_END}s")
                        break
                    
                    # Run simulation step
                    current_time = self.run_simulation_step()
                    
                    # Check active vehicles in SUMO
                    try:
                        active_vehicles = traci.vehicle.getIDList()
                    except:
                        active_vehicles = []
                    
                    # Every 10 steps, show status
                    # if step % 10 == 0:
                    #     print(f"\n[TIME]  Time: {current_time:.1f}s / {SIMULATION_END}s | Vehicles: {len(active_vehicles)} | Messages: {len(self.communication_log)} | Crypto: {self.crypto_mode.upper()}")
                    #     if active_vehicles:
                    #         print(f"  [CAR] Active: {', '.join(active_vehicles)}")
                        
                        # Show V2V communication status
                        # for vehicle_id, vehicle in list(self.vehicles.items()):
                        #    if vehicle.neighbors:
                        #        print(f"  [MSG] {vehicle_id} <-> {', '.join(vehicle.neighbors)} (range: {COMMUNICATION_RANGE}m)")
                        #        print(f"     Position: ({vehicle.position[0]:.1f}, {vehicle.position[1]:.1f}) | Speed: {vehicle.speed:.2f} m/s")
                    
                    step += 1
                    
                    # Switch crypto mode to post-quantum at 90 seconds and stay there
                    if current_time >= 90.0 and self.crypto_mode == "classical":
                        self.crypto_mode = "postquantum"
                        print(f"\n{'='*60}")
                        print(f"[INFO] CRYPTO MODE SWITCH at {current_time:.1f}s")
                        print(f"   Changed from: [LOCK] CLASSICAL (AES/RSA)")
                        print(f"   Changed to:   [PQ-LOCK] POST-QUANTUM (Quantum-Resistant)")
                        print(f"   Will stay post-quantum for rest of simulation!")
                        print(f"   [SAFE] All attacks by Purple Car are now BLOCKED!")
                        
                        # Release all controlled vehicles
                        for vid in list(self.controlled_vehicles.keys()):
                            try:
                                # Reset speed control to let SUMO take over
                                traci.vehicle.setSpeed(vid, -1)
                                traci.vehicle.setSpeedMode(vid, 31)  # Default SUMO speed mode
                                log_line = f"[SAFE] Released control of {self.vehicle_names.get(vid, vid)} (Post-Quantum active)"
                                print(log_line)
                                if self.attacker_gui:
                                    self.attacker_gui.log(log_line)
                                if self.normal_v2x_gui:
                                    self.normal_v2x_gui.log(log_line)
                            except:
                                pass
                        # Clear controlled vehicles list
                        self.controlled_vehicles.clear()
                        
                        # Update all vehicle labels to show new crypto mode
                        for vid in list(self.vehicles.keys()):
                            self._update_vehicle_gui_label(vid)
                        print(f"{'='*60}\n")
                    
                    # Add small delay to make simulation visible (only in GUI mode)
                    # This slows down the simulation so you can see it
                    time.sleep(0.05)  # 50ms delay per step = much slower
                    
                except traci.exceptions.FatalTraCIError as e:
                    print(f"\n[WARN]  TraCI fatal error: {e}")
                    break
                except traci.exceptions.TraCIException as e:
                    print(f"\n[WARN]  TraCI error: {e}")
                    # Continue simulation, might be recoverable
                    step += 1
                except Exception as e:
                    print(f"\n[WARN]  Error in simulation step {step}: {e}")
                    import traceback
                    traceback.print_exc()
                    break
        except KeyboardInterrupt:
            print("\n[WARN]  Simulation interrupted by user")
        
        print("\n[OK] Simulation completed")
        try:
            traci.close()
        except:
            pass  # Connection might already be closed


class NormalV2XLogGUI:
    """GUI that only shows normal, non-attacker V2X communication"""
    def __init__(self, simulation):
        self.simulation = simulation
        self.root = tk.Tk()
        self.root.title("V2X Normal Communication Log")
        self.root.geometry("600x500")
        
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title label
        title_label = ttk.Label(main_frame, text="NORMAL VEHICLE-TO-VEHICLE COMMUNICATION", font=("Arial", 14, "bold"))
        title_label.pack(pady=10)
        
        # Log area
        log_frame = ttk.LabelFrame(main_frame, text="Communication Log", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.log_text = tk.Text(log_frame, height=20, state=tk.DISABLED)
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def log(self, message):
        """Add message to log"""
        try:
            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)
        except:
            pass
    
    def run(self):
        """Start GUI main loop"""
        self.root.mainloop()


class PurpleCarAttackerGUI:
    """GUI for the purple car attacker - shows only attack-related logs and has action buttons"""
    def __init__(self, simulation):
        self.simulation = simulation
        self.root = tk.Tk()
        self.root.title("Purple Car Attacker Panel")
        self.root.geometry("600x700")
        self.selected_target = tk.StringVar()
        self.last_user_selected_vid = None  # Tracks the last vehicle the user manually selected
        
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title label
        title_label = ttk.Label(main_frame, text="PURPLE CAR ATTACKER CONTROL", font=("Arial", 16, "bold"))
        title_label.pack(pady=10)
        
        # Encountered cars display
        encountered_frame = ttk.LabelFrame(main_frame, text="Encountered Vehicles (Data Retrievable)", padding="10")
        encountered_frame.pack(fill=tk.X, pady=5)
        
        self.encountered_label = ttk.Label(encountered_frame, text="No vehicles encountered yet")
        self.encountered_label.pack()
        
        # Target selection
        target_frame = ttk.LabelFrame(main_frame, text="Select Target Vehicle", padding="10")
        target_frame.pack(fill=tk.X, pady=5)
        
        self.target_combobox = ttk.Combobox(target_frame, textvariable=self.selected_target, state="readonly")
        self.target_combobox.pack(fill=tk.X, pady=5)
        self.target_combobox.bind("<<ComboboxSelected>>", self.on_target_selected)
        
        refresh_btn = ttk.Button(target_frame, text="Refresh Targets", command=self.refresh_targets)
        refresh_btn.pack(pady=5)
        
        # Action buttons frame
        actions_frame = ttk.LabelFrame(main_frame, text="Attack Actions", padding="10")
        actions_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        ttk.Button(actions_frame, text="1. Send FAKE WARNING (Make Faster - 15 m/s)", 
                   command=lambda: self.run_action('1')).pack(fill=tk.X, pady=5)
        ttk.Button(actions_frame, text="2. Send ACCIDENT AHEAD! (Make Stop - 0 m/s)", 
                   command=lambda: self.run_action('2')).pack(fill=tk.X, pady=5)
        ttk.Button(actions_frame, text="3. Send SLOW DOWN (Make Very Slow - 2 m/s)", 
                   command=lambda: self.run_action('3')).pack(fill=tk.X, pady=5)
        ttk.Button(actions_frame, text="4. Get ALL ENCOUNTERED VEHICLE DATA", 
                   command=lambda: self.run_action('4')).pack(fill=tk.X, pady=5)
        ttk.Button(actions_frame, text="5. Get SELECTED TARGET DATA ONLY", 
                   command=lambda: self.run_action('5')).pack(fill=tk.X, pady=5)
        
        # Log area
        log_frame = ttk.LabelFrame(main_frame, text="Attack Log", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.log_text = tk.Text(log_frame, height=10, state=tk.DISABLED)
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Periodically update targets and encountered list
        self.refresh_targets()
        self.update_periodically()
    
    def log(self, message):
        """Add message to log"""
        try:
            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)
        except:
            pass
    
    def on_target_selected(self, event):
        """Called when user manually selects a target from combobox"""
        # Use event.widget.get() to get the NEW selection immediately!
        selected_str = event.widget.get()
        
        # Extract the vid from this string
        selected_vid = None
        if "(" in selected_str and ")" in selected_str:
            start = selected_str.find("(") + 1
            end = selected_str.find(")")
            selected_vid = selected_str[start:end]
        
        self.last_user_selected_vid = selected_vid
    
    def refresh_targets(self):
        """Refresh target list WITHOUT OVERWRITING USER SELECTION UNLESS ABSOLUTELY NECESSARY"""
        try:

            
            # Update encountered cars display
            encountered_list = []
            try:
                if "vehicle4" in traci.vehicle.getIDList():
                    for vid in self.simulation.purple_encountered_cars:
                        name = self.simulation.vehicle_names.get(vid, vid)
                        encountered_list.append(name)
            except:
                pass
            if encountered_list:
                self.encountered_label.config(text="Encountered: " + ", ".join(encountered_list))
            else:
                self.encountered_label.config(text="No vehicles encountered yet")
            
            # Update target list
            active_vehicles = []
            active_vids = []
            try:
                if "vehicle4" in traci.vehicle.getIDList():
                    for vid in traci.vehicle.getIDList():
                        if vid == "vehicle4":
                            continue
                        active_vids.append(vid)
                        name = self.simulation.vehicle_names.get(vid, vid)
                        
                        # Check if encountered
                        encountered = vid in self.simulation.purple_encountered_cars
                        status_str = " [ENCOUNTERED]" if encountered else ""
                        active_vehicles.append(f"{name} ({vid}){status_str}")
            except:
                pass
            

            
            # Update the combobox values
            self.target_combobox['values'] = active_vehicles
            
            # Now handle selection logic:
            # 1. If we have no active vehicles, clear selection
            if not active_vehicles:
                self.selected_target.set("")

                return
            
            # 2. Get current selection state
            current_selected_vid = self.get_selected_target_id()

            
            # 3. First, check if we have a last_user_selected_vid that's still active
            if self.last_user_selected_vid and self.last_user_selected_vid in active_vids:
                # Find the updated string for this vid
                for item in active_vehicles:
                    if f"({self.last_user_selected_vid})" in item:
                        current_str = self.selected_target.get()
                        if current_str != item:

                            self.selected_target.set(item)

                        break
                return
            
            # 4. Next, check if current selected vid is still active
            if current_selected_vid and current_selected_vid in active_vids:
                # Find the updated string for this vid
                for item in active_vehicles:
                    if f"({current_selected_vid})" in item:
                        current_str = self.selected_target.get()
                        if current_str != item:

                            self.selected_target.set(item)

                        break
                return
            
            # 5. If we get here, no valid selection exists - set to first vehicle only if we haven't set anything yet
            if not current_selected_vid and not self.last_user_selected_vid:

                self.selected_target.set(active_vehicles[0])
            
        except Exception as e:
            pass
    
    def update_periodically(self):
        """Update targets and encountered list every 1000ms (1 second)"""
        self.refresh_targets()
        self.root.after(1000, self.update_periodically)
    
    def get_selected_target_id(self):
        """Get vehicle ID from selected target string"""
        selected = self.selected_target.get()
        if not selected:
            return None
        # Extract vehicle ID from string like "Red Car (vehicle1) [IN RANGE]"
        if "(" in selected and ")" in selected:
            start = selected.find("(") + 1
            end = selected.find(")")
            vid = selected[start:end]
            return vid
        return None
    
    def run_action(self, action_key):
        """Run action via simulation's handle_menu_action method"""
        try:
            selected_vid = self.get_selected_target_id()
            
            # For actions 1-3, we need a selected target
            if action_key in ['1', '2', '3']:
                if not selected_vid:
                    self.log("[WARN] Please select a target vehicle first!")
                    return
                self.simulation.selected_target = selected_vid
            
            self.simulation._handle_menu_action(action_key)
        except Exception as e:
            self.log(f"[ERROR] Could not perform action: {str(e)}")
    
    def run(self):
        """Start GUI main loop"""
        self.root.mainloop()


def main():
    """Main entry point"""
    print("=" * 60)
    print("V2X Simulation with MITM Attack & Post-Quantum Security")
    print("=" * 60)
    
    sim = V2XSimulation()
    
    # Create both GUI instances and start them in separate threads
    normal_gui = None
    attacker_gui = None
    
    def start_normal_gui():
        nonlocal normal_gui
        normal_gui = NormalV2XLogGUI(sim)
        sim.normal_v2x_gui = normal_gui
        normal_gui.run()
    
    def start_attacker_gui():
        nonlocal attacker_gui
        attacker_gui = PurpleCarAttackerGUI(sim)
        sim.attacker_gui = attacker_gui
        attacker_gui.run()
    
    # Start both GUIs
    normal_thread = threading.Thread(target=start_normal_gui, daemon=True)
    normal_thread.start()
    
    attacker_thread = threading.Thread(target=start_attacker_gui, daemon=True)
    attacker_thread.start()
    
    # Wait a little for GUIs to initialize
    time.sleep(1.5)
    
    try:
        sim.run()
    except KeyboardInterrupt:
        print("\n[WARN] Simulation interrupted by user")
        try:
            traci.close()
        except:
            pass
    except Exception as e:
        print(f"\n[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()
        try:
            traci.close()
        except:
            pass


if __name__ == "__main__":
    main()

