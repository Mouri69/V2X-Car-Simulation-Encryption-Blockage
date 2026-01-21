"""
Classical Cryptography Implementation
Demonstrates RSA/ECC encryption (vulnerable to quantum attacks)
"""

import hashlib
import hmac
from typing import Tuple, Optional
import json


class ClassicalCrypto:
    """
    Classical cryptography using RSA/ECC principles
    Simplified for demonstration - shows vulnerability to quantum attacks
    """
    
    def __init__(self, key_size: int = 2048):
        """
        Initialize with key size
        Note: This is a simplified implementation for demonstration
        """
        self.key_size = key_size
        # In real implementation, these would be proper RSA/ECC keys
        self.public_key = None
        self.private_key = None
        self._generate_keys()
    
    def _generate_keys(self):
        """Generate public/private key pair (simplified)"""
        # Simplified: In real RSA, this would use prime number generation
        # For demo, we use hash-based "keys"
        seed = f"classical_key_{self.key_size}"
        self.private_key = hashlib.sha256(seed.encode()).hexdigest()
        self.public_key = hashlib.sha256(self.private_key.encode()).hexdigest()
    
    def encrypt(self, message: str, recipient_public_key: Optional[str] = None) -> str:
        """
        Encrypt message using classical cryptography
        Simplified: Uses XOR cipher for demonstration
        """
        if recipient_public_key is None:
            recipient_public_key = self.public_key
        
        # Simplified encryption (XOR cipher)
        key = hashlib.sha256(recipient_public_key.encode()).digest()
        encrypted = bytearray()
        
        for i, byte in enumerate(message.encode()):
            encrypted.append(byte ^ key[i % len(key)])
        
        return encrypted.hex()
    
    def decrypt(self, encrypted_message: str) -> str:
        """Decrypt message using private key"""
        encrypted_bytes = bytes.fromhex(encrypted_message)
        key = hashlib.sha256(self.private_key.encode()).digest()
        
        decrypted = bytearray()
        for i, byte in enumerate(encrypted_bytes):
            decrypted.append(byte ^ key[i % len(key)])
        
        return decrypted.decode()
    
    def sign(self, message: str) -> str:
        """Create digital signature (simplified HMAC)"""
        signature = hmac.new(
            self.private_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def verify_signature(self, message: str, signature: str, 
                        signer_public_key: str) -> bool:
        """Verify digital signature"""
        # Simplified verification
        expected = hmac.new(
            signer_public_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
    
    def encrypt_message(self, message_dict: dict) -> dict:
        """Encrypt a V2X message"""
        message_json = json.dumps(message_dict)
        encrypted_data = self.encrypt(message_json)
        
        return {
            "encrypted": True,
            "crypto_type": "classical",
            "data": encrypted_data,
            "public_key": self.public_key
        }
    
    def decrypt_message(self, encrypted_message: dict) -> dict:
        """Decrypt a V2X message"""
        if not encrypted_message.get("encrypted"):
            return encrypted_message
        
        encrypted_data = encrypted_message["data"]
        decrypted_json = self.decrypt(encrypted_data)
        return json.loads(decrypted_json)


class QuantumVulnerability:
    """
    Simulates quantum attack on classical cryptography
    Shows how quantum computers can break RSA/ECC
    """
    
    @staticmethod
    def break_classical_crypto(encrypted_message: dict, 
                              public_key: str) -> dict:
        """
        Simulate quantum attack breaking classical encryption
        In reality, quantum computers use Shor's algorithm
        """
        # Simplified: Simulates successful quantum attack
        # In real quantum attack, Shor's algorithm factors large numbers
        print("⚠️  QUANTUM ATTACK: Breaking classical encryption...")
        print("   Using Shor's algorithm to factor key...")
        print("   ✓ Key factored successfully!")
        print("   ✓ Encryption broken!")
        
        # For demo: Return "decrypted" message (simulated)
        # In real attack, this would actually decrypt the message
        return {
            "attack_successful": True,
            "method": "Shor's algorithm (quantum)",
            "original_encryption": "classical",
            "vulnerability": "RSA/ECC can be broken by quantum computers"
        }

