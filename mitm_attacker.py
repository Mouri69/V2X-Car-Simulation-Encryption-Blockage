"""
Man-in-the-Middle (MITM) Attacker Simulation
Intercepts, modifies, and injects V2V messages
"""

import json
import time
from typing import Dict, List, Optional
from v2x_messages import MessageHandler, BSMMessage
from crypto_classical import ClassicalCrypto, QuantumVulnerability
from crypto_postquantum import PostQuantumCrypto, QuantumResistance


class MITMAttacker:
    """
    Man-in-the-Middle attacker that:
    1. Eavesdrops on V2V communications
    2. Modifies messages
    3. Injects fake messages
    4. Attempts to break encryption
    """
    
    def __init__(self, attacker_id: str, use_quantum_attack: bool = False):
        self.attacker_id = attacker_id
        self.intercepted_messages: List[Dict] = []
        self.modified_messages: List[Dict] = []
        self.injected_messages: List[Dict] = []
        self.use_quantum_attack = use_quantum_attack
        self.attack_successful = False
        
        # Attacker has their own crypto keys
        self.classical_crypto = ClassicalCrypto()
        self.postquantum_crypto = PostQuantumCrypto()
        self.message_handler = MessageHandler()
    
    def intercept_message(self, message: Dict) -> Dict:
        """
        Intercept a V2V message
        Returns the intercepted message (may be modified)
        """
        self.intercepted_messages.append({
            "original": message.copy(),
            "timestamp": time.time(),
            "intercepted_by": self.attacker_id
        })
        
        # print(f"🔴 MITM: Intercepted message from {message.get('sender', 'unknown')}")
        
        # Try to break encryption if message is encrypted
        if message.get("encrypted"):
            message = self._attempt_decryption(message)
        
        # If attacker managed to decrypt, try forging "Hello" payloads
        if message.get("decrypted_by_attacker"):
            data = message.get("data", {})
            if isinstance(data, dict):
                sx = float(data.get("position_x", 0))
                sy = float(data.get("position_y", 0))
                spd = float(data.get("speed", 0))
                forged_x = sx + 15.0
                forged_y = sy + 15.0
                forged_speed = spd + 10.0
                forged = self.modify_message(
                    message,
                    {"position_x": forged_x, "position_y": forged_y, "speed": forged_speed, "forged": True}
                )
                forged["forged_by_attacker"] = True
                forged["display_text"] = f"Forged pos=({forged_x:.1f},{forged_y:.1f}), speed={forged_speed:.2f}"
                return forged
        
        return message
    
    def _attempt_decryption(self, encrypted_message: Dict) -> Dict:
        """Attempt to decrypt intercepted message"""
        crypto_type = encrypted_message.get("crypto_type", "unknown")
        
        if crypto_type == "classical":
            # print("   🔓 Attempting to break classical encryption...")
            
            if self.use_quantum_attack:
                # Simulate quantum attack
                attack_result = QuantumVulnerability.break_classical_crypto(
                    encrypted_message,
                    encrypted_message.get("public_key", "")
                )
                
                if attack_result.get("attack_successful"):
                    # print("   ✓ Classical encryption broken by quantum attack!")
                    self.attack_successful = True
                    # In real attack, would decrypt the message
                    return {
                        **encrypted_message,
                        "decrypted_by_attacker": True,
                        "attack_method": "quantum"
                    }
            else:
                # Try brute force (would fail in real RSA)
                # print("   ✗ Classical encryption too strong for classical attack")
                pass
        
        elif crypto_type == "post_quantum":
            # print("   🔒 Attempting to break post-quantum encryption...")
            
            if self.use_quantum_attack:
                attack_result = QuantumResistance.attempt_quantum_attack(
                    encrypted_message,
                    encrypted_message.get("public_key", "")
                )
                
                if not attack_result.get("attack_successful"):
                    # print("   ✓ Post-quantum encryption resisted quantum attack!")
                    return {
                        **encrypted_message,
                        "decrypted_by_attacker": False,
                        "attack_method": "quantum_failed"
                    }
        
        # Default: return original when attack fails
        return {**encrypted_message, "decrypted_by_attacker": False}
    
    def modify_message(self, message: Dict, modifications: Dict) -> Dict:
        """
        Modify an intercepted message
        modifications: dict of fields to change
        """
        modified = message.copy()
        
        # Modify data fields
        if "data" in modified:
            if isinstance(modified["data"], dict):
                modified["data"].update(modifications)
            else:
                modified["data"] = modifications
        
        modified["modified_by"] = self.attacker_id
        modified["modification_time"] = time.time()
        
        self.modified_messages.append({
            "original": message,
            "modified": modified,
            "timestamp": time.time()
        })
        
        # print(f"   ⚠️  MITM: Modified message from {message.get('sender', 'unknown')}")
        # print(f"      Changes: {modifications}")
        
        return modified
    
    def inject_fake_message(self, sender_id: str, receiver_id: str,
                           message_type: str, fake_data: Dict) -> Dict:
        """
        Inject a fake V2V message
        Example: Fake accident warning, fake speed data, etc.
        """
        fake_message = {
            "sender": sender_id,  # Spoofed sender
            "receiver": receiver_id,
            "type": message_type,
            "data": fake_data,
            "timestamp": time.time(),
            "injected_by": self.attacker_id,
            "is_fake": True
        }
        
        self.injected_messages.append(fake_message)
        
        # print(f"   🎭 MITM: Injected fake {message_type} message")
        # print(f"      Fake data: {fake_data}")
        
        return fake_message
    
    def create_fake_accident_warning(self, position: tuple) -> Dict:
        """Create a fake accident warning message"""
        return self.inject_fake_message(
            sender_id="spoofed_vehicle",
            receiver_id="broadcast",
            message_type="DENM",
            fake_data={
                "event_type": "accident",
                "position_x": position[0],
                "position_y": position[1],
                "severity": 5,
                "description": "Fake accident warning - MITM attack"
            }
        )
    
    def create_fake_speed_data(self, vehicle_id: str, fake_speed: float) -> Dict:
        """Create fake speed data to mislead other vehicles"""
        return self.inject_fake_message(
            sender_id=vehicle_id,  # Spoofing the vehicle
            receiver_id="broadcast",
            message_type="BSM",
            fake_data={
                "speed": fake_speed,  # False speed data
                "position_x": 0,
                "position_y": 0
            }
        )
    
    def get_attack_statistics(self) -> Dict:
        """Get statistics about the attack"""
        return {
            "attacker_id": self.attacker_id,
            "messages_intercepted": len(self.intercepted_messages),
            "messages_modified": len(self.modified_messages),
            "messages_injected": len(self.injected_messages),
            "attack_successful": self.attack_successful,
            "quantum_attack_used": self.use_quantum_attack
        }
    
    def print_attack_summary(self):
        """Print summary of attack activities"""
        stats = self.get_attack_statistics()
        
        print("\n" + "=" * 60)
        print("MITM ATTACK SUMMARY")
        print("=" * 60)
        print(f"Attacker ID: {stats['attacker_id']}")
        print(f"Messages Intercepted: {stats['messages_intercepted']}")
        print(f"Messages Modified: {stats['messages_modified']}")
        print(f"Messages Injected: {stats['messages_injected']}")
        print(f"Attack Successful: {stats['attack_successful']}")
        print(f"Quantum Attack Used: {stats['quantum_attack_used']}")
        print("=" * 60)

