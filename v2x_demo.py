"""
Complete V2X Simulation Demo
Demonstrates:
1. V2V communication
2. MITM attack on classical crypto (successful)
3. MITM attack on post-quantum crypto (failed)
"""

import os
import sys
import traci
import time
from v2x_simulation import V2XSimulation, Vehicle
from v2x_messages import MessageHandler, BSMMessage
from crypto_classical import ClassicalCrypto
from crypto_postquantum import PostQuantumCrypto
from mitm_attacker import MITMAttacker

# SUMO configuration
SUMO_HOME = r"C:\Program Files (x86)\Eclipse\Sumo"
sys.path.append(os.path.join(SUMO_HOME, "tools"))


class V2XDemo:
    """Complete V2X demo with MITM and crypto comparison"""
    
    def __init__(self):
        self.sim = V2XSimulation()
        self.message_handler = MessageHandler()
        self.classical_crypto = ClassicalCrypto()
        self.postquantum_crypto = PostQuantumCrypto()
        self.mitm_attacker = None
        self.demo_mode = "classical"  # or "postquantum"
        
    def setup_vehicles(self):
        """Add vehicles to the simulation"""
        edges = self.sim.get_network_edges()
        road_edges = [e for e in edges if not e.startswith(":")]
        
        if len(road_edges) < 2:
            print("⚠️  Not enough edges for demo")
            return
        
        # Add regular vehicles
        self.sim.add_vehicle("vehicle1", road_edges[:2], 0, (255, 0, 0))
        self.sim.add_vehicle("vehicle2", road_edges[2:4] if len(road_edges) >= 4 else road_edges[:2], 5, (0, 255, 0))
        self.sim.add_vehicle("vehicle3", road_edges[4:6] if len(road_edges) >= 6 else road_edges[:2], 10, (0, 0, 255))
        
        # Add MITM attacker vehicle (in purple)
        self.sim.add_vehicle("mitm_attacker", road_edges[:2], 3, (128, 0, 128))
        # Create attacker and plug it into the simulation so all messages go through it
        self.mitm_attacker = MITMAttacker("mitm_attacker", use_quantum_attack=True)
        self.sim.mitm_attacker = self.mitm_attacker
        
        print("✓ Vehicles added to simulation")
    
    def demonstrate_classical_crypto(self):
        """Demonstrate classical crypto being broken by MITM"""
        print("\n" + "=" * 60)
        print("DEMO 1: Classical Cryptography (VULNERABLE)")
        print("=" * 60)
        
        self.demo_mode = "classical"
        self.sim.crypto_mode = "classical"  # Set in simulation for GUI labels
        
        # Vehicle 1 sends encrypted message to Vehicle 2
        if "vehicle1" in self.sim.vehicles and "vehicle2" in self.sim.vehicles:
            v1 = self.sim.vehicles["vehicle1"]
            v2 = self.sim.vehicles["vehicle2"]
            
            # Update vehicle states
            v1.update()
            v2.update()
            
            message_text = "Vehicle 1 (Red) → Vehicle 2 (Green): Hello!"
            print(f"\n🚗 {message_text}")
            print("   Expect MITM (Purple) to forge message under classical crypto...")
            try:
                sent = self.sim.send_v2v_message(
                    "vehicle1",
                    "vehicle2",
                    "HELLO",
                    {"content": "Hello!", "channel": "classical"},
                    use_encryption=True,
                    display_text=message_text
                )
            except Exception:
                # Fallback to manual message creation
                bsm = self.message_handler.create_bsm(
                    "vehicle1",
                    v1.position,
                    v1.speed,
                    v1.heading
                )
                
                message_dict = {
                    "sender": "vehicle1",
                    "receiver": "vehicle2",
                    "type": "HELLO",
                    "data": {"content": "Hello!", "bsm": bsm.to_dict()},
                    "encrypted": True
                }
                
                encrypted = self.classical_crypto.encrypt_message(message_dict)
                print(f"\n✓ Vehicle1 encrypted message with classical crypto")
                print(f"  Encryption type: {encrypted['crypto_type']}")
                
                # MITM intercepts
                sent = self.mitm_attacker.intercept_message(encrypted)
                # Manually update GUI label
                self.sim._update_vehicle_gui_label("vehicle1")
            
            if sent.get("forged_by_attacker"):
                print(f"\n✗ ATTACK SUCCESSFUL: Purple MITM forged the message to 'Bad Hello'")
            elif sent.get("decrypted_by_attacker"):
                print(f"\n⚠️  MITM read the message, may modify follow-ups")
            else:
                print(f"\n✓ Message stayed intact (unexpected for classical demo)")
    
    def demonstrate_postquantum_crypto(self):
        """Demonstrate post-quantum crypto resisting MITM"""
        print("\n" + "=" * 60)
        print("DEMO 2: Post-Quantum Cryptography (QUANTUM-RESISTANT)")
        print("=" * 60)
        
        self.demo_mode = "postquantum"
        self.sim.crypto_mode = "postquantum"  # Set in simulation for GUI labels
        
        # Run simulation for a few seconds to let vehicles move
        print("Running simulation for 5 seconds to demonstrate...")
        for _ in range(50):
            current_time = self.sim.run_simulation_step()
            time.sleep(0.1)  # Slow down for visibility
        
        # Vehicle 2 sends encrypted message to Vehicle 3
        if "vehicle2" in self.sim.vehicles and "vehicle3" in self.sim.vehicles:
            v2 = self.sim.vehicles["vehicle2"]
            v3 = self.sim.vehicles["vehicle3"]
            
            # Update vehicle states
            v2.update()
            v3.update()
            
            secure_text = "Vehicle 2 (Green) → Vehicle 3 (Blue): Hello!"
            print(f"\n🚗 {secure_text}")
            print("   Purple MITM should FAIL to forge post-quantum message.")
            try:
                sent = self.sim.send_v2v_message(
                    "vehicle2",
                    "vehicle3",
                    "HELLO",
                    {"content": "Hello!", "channel": "postquantum"},
                    use_encryption=True,
                    display_text=secure_text
                )
            except Exception:
                # Fallback to manual message creation
                bsm = self.message_handler.create_bsm(
                    "vehicle2",
                    v2.position,
                    v2.speed,
                    v2.heading
                )
                
                message_dict = {
                    "sender": "vehicle2",
                    "receiver": "vehicle3",
                    "type": "HELLO",
                    "data": {"content": "Hello!", "bsm": bsm.to_dict()},
                    "encrypted": True
                }
                
                encrypted = self.postquantum_crypto.encrypt_message(message_dict)
                print(f"\n✓ Vehicle2 encrypted message with post-quantum crypto")
                print(f"  Encryption type: {encrypted['crypto_type']}")
                print(f"  Algorithm: {encrypted['algorithm']}")
                print(f"  Quantum-resistant: {encrypted['quantum_resistant']}")
                
                # MITM attempts to intercept
                sent = self.mitm_attacker.intercept_message(encrypted)
                
                # Update GUI label
                self.sim._update_vehicle_gui_label("vehicle2")
            
            if not sent.get("decrypted_by_attacker", False):
                print(f"\n✓ ATTACK FAILED: Post-quantum encryption blocked MITM!")
            else:
                print(f"\n⚠️  Unexpected MITM success on PQ channel (check configuration)")
    
    def run_interactive_demo(self):
        """Run interactive simulation with V2V communication"""
        print("\n" + "=" * 60)
        print("RUNNING INTERACTIVE SIMULATION")
        print("=" * 60)
        print("Vehicles will communicate via V2V messages")
        print("MITM attacker will attempt to intercept...")
        print("💡 Messages will appear as labels on vehicles in SUMO GUI!")
        print("⏱️  Simulation will run for 60 seconds...")
        print()
        
        # Set crypto mode in simulation
        self.sim.crypto_mode = self.demo_mode
        
        # Run simulation for 60 seconds
        simulation_duration = 60  # seconds
        start_time = traci.simulation.getTime()
        
        step = 0
        last_message_time = 0
        
        # Toggle state
        current_mode = "classical"
        last_mode_switch = 0
        print("\n>>> STARTING WITH CLASSICAL CRYPTO (VULNERABLE) <<<")
        self.sim.crypto_mode = "classical"
        self.demo_mode = "classical"

        while True:
            current_time = self.sim.run_simulation_step()
            
            # Check if we've reached the time limit
            if current_time >= start_time + simulation_duration:
                print(f"\n⏱️  Reached time limit: {simulation_duration}s")
                break
            
            # Toggle mode every 15 seconds
            if current_time - last_mode_switch >= 15.0:
                if current_mode == "classical":
                    current_mode = "postquantum"
                    print("\n" + "="*50)
                    print(">>> SWITCHING TO POST-QUANTUM CRYPTO (SECURE) <<<")
                    print("="*50 + "\n")
                else:
                    current_mode = "classical"
                    print("\n" + "="*50)
                    print(">>> SWITCHING TO CLASSICAL CRYPTO (VULNERABLE) <<<")
                    print("="*50 + "\n")
                
                self.sim.crypto_mode = current_mode
                self.demo_mode = current_mode
                last_mode_switch = current_time
                
                # Force update labels to show new lock icon
                for vid in self.sim.vehicles:
                    self.sim._update_vehicle_gui_label(vid)
            
            # Send messages every 2 seconds (same as main simulation)
            if current_time - last_message_time >= 2.0:
                # Scenario 1: Car Red (vehicle1) -> Car 2 (vehicle2)
                # "Car Red Says Hello Car 2"
                if "vehicle1" in self.sim.vehicles and "vehicle2" in self.sim.vehicles:
                    neighbors_v1 = self.sim.find_neighbors("vehicle1")
                    if "vehicle2" in neighbors_v1:
                        try:
                            self.sim.send_v2v_message(
                                "vehicle1",
                                "vehicle2",
                                "HELLO",
                                {"content": "Hello"},
                                display_text="Hello"
                            )
                        except Exception:
                            pass

                # Scenario 2: Car Purple (MITM) -> Car Red (vehicle1)
                # "Car Purple says To Car Red STOP! accident ahead"
                if "mitm_attacker" in self.sim.vehicles and "vehicle1" in self.sim.vehicles:
                    neighbors_mitm = self.sim.find_neighbors("mitm_attacker")
                    if "vehicle1" in neighbors_mitm:
                        try:
                            self.sim.send_v2v_message(
                                "mitm_attacker",
                                "vehicle1",
                                "WARNING",
                                {"content": "STOP! accident ahead"},
                                display_text="STOP! accident ahead"
                            )
                        except Exception:
                            pass
                
                last_message_time = current_time
            
            # Add small delay to slow down GUI for visibility
            time.sleep(0.05)
            
            step += 1
            
            # Safety check - don't run forever
            if step > 10000:
                print("\n⚠️  Maximum steps reached, stopping simulation")
                break
        
        # Print attack summary
        if self.mitm_attacker:
            self.mitm_attacker.print_attack_summary()
    
    def run(self):
        """Run the complete demo"""
        print("=" * 60)
        print("V2X QUANTUM-SAFE SIMULATION DEMO")
        print("=" * 60)
        
        # Start simulation
        self.sim.start_simulation()
        time.sleep(1)  # Wait for SUMO to initialize
        
        # Setup vehicles
        self.setup_vehicles()
        
        # Advance simulation to let vehicles spawn
        # Need to reach at least t=6 for Green car (depart=5) and t=11 for Blue car (depart=10)
        print("⏳ Advancing simulation to spawn vehicles...")
        for _ in range(60):  # 6 seconds (0.1s step)
            self.sim.run_simulation_step()
            time.sleep(0.05)
            
        print("\n" + "=" * 60)
        print("STARTING MAIN SIMULATION LOOP")
        print("0-40s: Classical Crypto (Vulnerable)")
        print("40s+: Post-Quantum Crypto (Secure)")
        print("=" * 60 + "\n")
        
        # Main Loop
        simulation_duration = 300  # 5 minutes
        start_time = traci.simulation.getTime()
        
        self.sim.crypto_mode = "classical"
        print(">>> MODE: CLASSICAL CRYPTO (VULNERABLE) <<<")
        
        mode_switched = False
        
        try:
            while traci.simulation.getMinExpectedNumber() > 0:
                current_time = self.sim.run_simulation_step()
                
                # Check for crypto mode switch at 40 seconds
                if current_time >= 40.0 and not mode_switched:
                    self.sim.crypto_mode = "postquantum"
                    print("\n" + "="*50)
                    print(">>> SWITCHING TO POST-QUANTUM CRYPTO (SECURE) <<<")
                    print("="*50 + "\n")
                    mode_switched = True
                    
                    # Force update labels
                    for vid in self.sim.vehicles:
                        self.sim._update_vehicle_gui_label(vid)
                
                # Check and log interactions
                self.sim.check_interactions(current_time)
                
                time.sleep(0.05)  # GUI delay
                
                if current_time > simulation_duration:
                    break
                    
        except KeyboardInterrupt:
            print("\n⚠️  Demo interrupted")
        finally:
            traci.close()
            print("\n✓ Demo completed")


def main():
    """Main entry point"""
    demo = V2XDemo()
    demo.run()


if __name__ == "__main__":
    main()

