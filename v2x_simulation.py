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
from typing import Dict, List, Tuple

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
SIMULATION_END = 1000  # seconds (increased to allow long running)


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
        
        # State tracking for interaction spam control
        # Set of tuples: (id1, id2, has_mitm)
        self.active_interactions = set()
        
        # Friendly names for logging
        self.vehicle_names = {
            "vehicle1": "Red Car",
            "vehicle2": "Green Car",
            "vehicle3": "Blue Car",
            "mitm_attacker": "Purple Car",
            "vehicle4": "Purple Car"
        }
        
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
        sumo_cmd = [sumo_binary, "-c", SIM_CONFIG, "--start", "--step-length", "0.1", "--delay", "100", "--end", "1000"]
        
        traci.start(sumo_cmd)
        print("✓ SUMO GUI simulation started")
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
                    print(f"⚠️  Edge '{edge}' not found in network, skipping")
            
            if not valid_edges:
                print(f"✗ No valid edges for vehicle {vehicle_id}")
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
                            print(f"  ✓ Validated route for {vehicle_id}: {valid_edges}")
                        # If validated route is single edge but original had multiple, keep original
                        elif len(validated_route) == 1 and len(valid_edges) > 1:
                            print(f"  ⚠️  Validation reduced route to single edge, keeping original: {valid_edges}")
                except Exception as validate_error:
                    # If validation fails, keep original route
                    print(f"  ⚠️  Route validation failed for {vehicle_id}, using original route: {validate_error}")
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
                print(f"✗ Error creating route for {vehicle_id}: {route_error}")
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
                    print(f"⚠️  Could not create vehicle type 'car': {type_error}")
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
                print(f"⚠️  Could not add vehicle with type 'car', using default: {add_error}")
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
            print(f"✓ Added vehicle: {vehicle_id} on route: {valid_edges}")
            
        except Exception as e:
            print(f"✗ Error adding vehicle {vehicle_id}: {e}")
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
        crypto_status = "⚠️ UNENCRYPTED"
        if use_encryption:
            if crypto_type == 'classical':
                crypto_status = "🔒 CLASSICAL (AES/RSA)"
            elif crypto_type in ('post_quantum', 'postquantum'):
                crypto_status = "🔐 POST-QUANTUM"
            else:
                crypto_status = f"🔒 {crypto_type}"
        
        mitm_status = ""
        if self.mitm_attacker:
            if log_entry.get("forged"):
                mitm_status = " ⚠️ [MITM ATTACK SUCCESSFUL - MESSAGE FORGED]"
            elif log_entry.get("mitm_intercepted"):
                if crypto_type in ('post_quantum', 'postquantum'):
                    mitm_status = " 🛡️ [MITM BLOCKED - ENCRYPTION SECURE]"
                else:
                    mitm_status = " ⚠️ [MITM INTERCEPTED]"
        
        text_part = message.get("display_text") or f"{sender_id} → {receiver_id}"
        print(f"📡 {text_part} | {message_type} | {crypto_status}{mitm_status}")
        
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
                label_parts.append("🔐 PQ")
            else:
                label_parts.append("🔒 CL")
            
            # Add neighbor count
            if vehicle.neighbors:
                label_parts.append(f"👥{len(vehicle.neighbors)}")
            
            # Add last message info if available
            if recent:
                last_msg = recent[-1]
                msg_short = last_msg["type"][:3]  # BSM -> BSM
                label_parts.append(f"→{last_msg['to'][-1]}")  # vehicle2 -> 2
                if last_msg.get("text"):
                    # Shorten text for label
                    snippet = last_msg["text"]
                    if len(snippet) > 22:
                        snippet = snippet[:22] + "…"
                    if last_msg.get("forged"):
                        snippet = f"⚠️ {snippet}"
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
        if mitm_active:
            mitm_neighbors = neighbors_map.get(mitm_id, [])
            for victim_id in mitm_neighbors:
                if victim_id == mitm_id: continue
                
                # Check if victim has other neighbors (excluding MITM)
                victim_neighbors = neighbors_map.get(victim_id, [])
                real_friends = [n for n in victim_neighbors if n != mitm_id and n != victim_id]
                
                if not real_friends:
                    # Condition: Purple in range with only 1 car
                    interaction_key = tuple(sorted([mitm_id, victim_id]) + ["fake_alert"])
                    current_interactions.add(interaction_key)
                    
                    if interaction_key not in self.active_interactions:
                        self.send_v2v_message(
                            mitm_id,
                            victim_id,
                            "WARNING",
                            {"content": "STOP! accident ahead", "is_fake": True},
                            use_encryption=True,
                            display_text=f"{get_name(mitm_id)} -> {get_name(victim_id)}: Fake Alert STOP! accident ahead",
                            intercepted=False
                        )
                        self.active_interactions.add(interaction_key)
        
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

    def run_simulation_step(self):
        """Run one simulation step"""
        traci.simulationStep()
        current_time = traci.simulation.getTime()
        
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
                    #    print(f"🛑 {vehicle_id} STOPPED at time {current_time:.1f}s")
                    
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
                                                print(f"  🔄 {vehicle_id} route extended ({len(extended_route)} edges)")
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
            print("✗ No edges found in network!")
            return
        
        # Filter out internal edges (those starting with ":")
        road_edges = [e for e in edges if not e.startswith(":")]
        
        if not road_edges:
            print("✗ No road edges found!")
            print(f"All edges: {edges[:10]}...")  # Show first 10 edges for debugging
            return
        
        print(f"✓ Found {len(road_edges)} road edges")
        print(f"Sample edges: {road_edges[:5]}")  # Debug: show first 5 edges
        
        # Try to find valid routes using SUMO's route finding
        # Get junctions to find start/end points
        junctions = traci.junction.getIDList()
        print(f"✓ Found {len(junctions)} junctions")
        
        # Use a simpler approach: find connected edge sequences directly
        print("\n🔍 Attempting to add vehicles...")
        current_time = traci.simulation.getTime()
        
        def find_connected_route(start_edge: str, max_length: int = 5) -> List[str]:
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
                        print(f"  ✓ Vehicle3 added successfully")
                        break  # Success, exit loop
                    except Exception as e:
                        print(f"    ✗ Failed with edge {idx}: {e}")
                        continue
                
                # If all attempts failed, try with simple single edge
                if not vehicle3_added:
                    print(f"  All route attempts failed, trying simple single edge for vehicle3")
                    for idx in range(2, min(len(road_edges), 8)):
                        try:
                            self.add_vehicle("vehicle3", [road_edges[idx]], current_time + 5, (0, 0, 255))
                            vehicle3_added = True
                            print(f"  ✓ Vehicle3 added with single edge {idx}: {road_edges[idx]}")
                            break
                        except Exception as e:
                            print(f"    ✗ Failed with single edge {idx}: {e}")
                            continue
            except Exception as e:
                print(f"  ✗ Failed to add vehicle3: {e}")
                import traceback
                traceback.print_exc()
            
            if not vehicle3_added:
                print(f"  ⚠️  WARNING: Could not add vehicle3 after all attempts!")
            
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
                        route4_edges = find_connected_route(test_edge, max_length=3)
                        if len(route4_edges) < 1:
                            route4_edges = [test_edge]
                        print(f"  Route4: {route4_edges} (using edge {idx})")
                        # Purple color: (128, 0, 128)
                        self.add_vehicle("vehicle4", route4_edges, current_time + 7, (128, 0, 128))
                        vehicle4_added = True
                        print(f"  ✓ Vehicle4 added successfully")
                        self.mitm_attacker = MITMAttacker("vehicle4", use_quantum_attack=True)
                        break  # Success, exit loop
                    except Exception as e:
                        print(f"    ✗ Failed with edge {idx}: {e}")
                        continue
                
                # If all attempts failed, try with simple single edge
                if not vehicle4_added:
                    print(f"  All route attempts failed, trying simple single edge for vehicle4")
                    for idx in range(3, min(len(road_edges), 10)):
                        try:
                            self.add_vehicle("vehicle4", [road_edges[idx]], current_time + 7, (128, 0, 128))
                            vehicle4_added = True
                            print(f"  ✓ Vehicle4 added with single edge {idx}: {road_edges[idx]}")
                            self.mitm_attacker = MITMAttacker("vehicle4", use_quantum_attack=True)
                            break
                        except Exception as e:
                            print(f"    ✗ Failed with single edge {idx}: {e}")
                            continue
            except Exception as e:
                print(f"  ✗ Failed to add vehicle4: {e}")
            
            if not vehicle4_added:
                print(f"  ⚠️  WARNING: Could not add vehicle4 after all attempts!")
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
        print(f"\n📊 Vehicles registered: {len(self.vehicles)}")
        if len(self.vehicles) == 0:
            print("⚠️  No vehicles were added! Check edge connectivity.")
            print(f"Available edges: {road_edges[:10]}")
            return
        
        # Run simulation
        print("\n🚗 Starting simulation...")
        print(f"   Running for {SIMULATION_END} seconds ({SIMULATION_END//60} minutes)...")
        print(f"\n📋 CRYPTO SCHEDULE:")
        print(f"   🔒 0-60s:     CLASSICAL (AES/RSA) - Vulnerable to quantum attacks")
        print(f"   🔐 60-120s:   POST-QUANTUM (Quantum-Resistant) - Safe from quantum attacks")
        print(f"   🔒 120-180s:  CLASSICAL (AES/RSA) - Vulnerable to quantum attacks")
        print(f"   🔐 180-240s:  POST-QUANTUM (Quantum-Resistant) - Safe from quantum attacks")
        print(f"   🔒 240-300s:  CLASSICAL (AES/RSA) - Vulnerable to quantum attacks")
        print(f"\n🚗 VEHICLES:")
        print(f"   🔴 Vehicle1: RED")
        print(f"   🟢 Vehicle2: GREEN")
        print(f"   🔵 Vehicle3: BLUE")
        print(f"   🟣 Vehicle4: PURPLE")
        print()
        step = 0
        
        try:
            while True:  # Run until time limit
                try:
                    # Check if connection is still alive
                    try:
                        current_time = traci.simulation.getTime()
                    except:
                        print("\n⚠️  TraCI connection lost")
                        break
                    
                    # Check if we've reached the time limit
                    if current_time >= SIMULATION_END:
                        print(f"\n⏱️  Reached time limit: {SIMULATION_END}s")
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
                    #     print(f"\n⏱️  Time: {current_time:.1f}s / {SIMULATION_END}s | Vehicles: {len(active_vehicles)} | Messages: {len(self.communication_log)} | Crypto: {self.crypto_mode.upper()}")
                    #     if active_vehicles:
                    #         print(f"  🚗 Active: {', '.join(active_vehicles)}")
                        
                        # Show V2V communication status
                        # for vehicle_id, vehicle in list(self.vehicles.items()):
                        #    if vehicle.neighbors:
                        #        print(f"  📡 {vehicle_id} ↔ {', '.join(vehicle.neighbors)} (range: {COMMUNICATION_RANGE}m)")
                        #        print(f"     Position: ({vehicle.position[0]:.1f}, {vehicle.position[1]:.1f}) | Speed: {vehicle.speed:.2f} m/s")
                    
                    step += 1
                    
                    # Switch crypto mode at 60 seconds
                    if current_time >= 60.0 and self.crypto_mode == "classical":
                        self.crypto_mode = "postquantum"
                        print(f"\n{'='*60}")
                        print(f"🔄 CRYPTO MODE SWITCH at {current_time:.1f}s")
                        print(f"   Changed from: 🔒 CLASSICAL (AES/RSA)")
                        print(f"   Changed to:   🔐 POST-QUANTUM (Quantum-Resistant)")
                        
                        # Update all vehicle labels to show new crypto mode
                        for vid in list(self.vehicles.keys()):
                            self._update_vehicle_gui_label(vid)
                        print(f"{'='*60}\n")
                    
                    # Add small delay to make simulation visible (only in GUI mode)
                    # This slows down the simulation so you can see it
                    time.sleep(0.05)  # 50ms delay per step = slower, more visible simulation
                    
                except traci.exceptions.FatalTraCIError as e:
                    print(f"\n⚠️  TraCI fatal error: {e}")
                    break
                except traci.exceptions.TraCIException as e:
                    print(f"\n⚠️  TraCI error: {e}")
                    # Continue simulation, might be recoverable
                    step += 1
                except Exception as e:
                    print(f"\n⚠️  Error in simulation step {step}: {e}")
                    import traceback
                    traceback.print_exc()
                    break
        except KeyboardInterrupt:
            print("\n⚠️  Simulation interrupted by user")
        
        print("\n✓ Simulation completed")
        try:
            traci.close()
        except:
            pass  # Connection might already be closed


def main():
    """Main entry point"""
    print("=" * 60)
    print("V2X Simulation with MITM Attack & Post-Quantum Security")
    print("=" * 60)
    
    sim = V2XSimulation()
    
    try:
        sim.run()
    except KeyboardInterrupt:
        print("\n⚠ Simulation interrupted by user")
        traci.close()
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        traci.close()


if __name__ == "__main__":
    main()

