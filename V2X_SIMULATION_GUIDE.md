# V2X Quantum-Safe Simulation Guide
## SUMO + Python TraCI for Post-Quantum Security Demonstration

---

## 📋 Table of Contents
1. [Overview](#overview)
2. [Step 1: Road Network Design](#step-1-road-network-design)
3. [Step 2: Python TraCI Setup](#step-2-python-traci-setup)
4. [Step 3: V2V Message Exchange](#step-3-v2v-message-exchange)
5. [Step 4: MITM Attacker Simulation](#step-4-mitm-attacker-simulation)
6. [Step 5: Classical vs Post-Quantum Crypto](#step-5-classical-vs-post-quantum-crypto)

---

## Overview

This project simulates Vehicle-to-Everything (V2X) communication with:
- **SUMO**: Traffic simulation
- **Python TraCI**: Vehicle control and communication
- **MITM Attack**: Intercepting and modifying messages
- **Post-Quantum Cryptography**: Demonstrating quantum-resistant security

---

## Step 1: Road Network Design ✅

**Current Status**: Grid network created (4x3 grid, 200m segments)

**Files Created**:
- `sumo_test/network.net.xml` - Road network (auto-generated)
- `sumo_test/sim.sumocfg` - SUMO configuration
- `sumo_test/routes.rou.xml` - Vehicle routes (optional, we'll use Python)

**Network Features**:
- 4 columns × 3 rows = 12 intersections
- 200m road segments
- Speed limit: 13.89 m/s (50 km/h)
- Perfect for V2X: vehicles can meet at intersections

---

## Step 2: Python TraCI Setup

**Next**: Create Python scripts to:
1. Connect to SUMO via TraCI
2. Add vehicles dynamically
3. Control vehicle movement
4. Get vehicle positions and neighbors

**Key TraCI Functions**:
- `traci.start()` - Connect to SUMO
- `traci.vehicle.add()` - Add vehicle
- `traci.vehicle.getPosition()` - Get position
- `traci.vehicle.getNeighbors()` - Find nearby vehicles
- `traci.simulation.getTime()` - Current simulation time

---

## Step 3: V2V Message Exchange

**Message Types**:
- **BSM (Basic Safety Message)**: Position, speed, heading
- **CAM (Cooperative Awareness Message)**: Vehicle status
- **DENM (Decentralized Environmental Notification)**: Road hazards

**Communication Range**: ~300m (typical V2X range)

---

## Step 4: MITM Attacker Simulation

**Attack Scenarios**:
1. **Eavesdropping**: Intercept messages
2. **Message Modification**: Alter speed/position data
3. **Replay Attack**: Re-transmit old messages
4. **Fake Messages**: Inject false information

**Implementation**: Attacker vehicle that intercepts all V2V messages

---

## Step 5: Classical vs Post-Quantum Crypto

**Classical Cryptography** (Vulnerable to Quantum):
- RSA, ECC (Elliptic Curve)
- Can be broken by quantum computers

**Post-Quantum Cryptography** (Quantum-Resistant):
- CRYSTALS-Kyber (Key Exchange)
- CRYSTALS-Dilithium (Digital Signatures)
- SPHINCS+ (Hash-based signatures)

**Demonstration**:
- Show MITM breaking classical crypto
- Show post-quantum crypto resisting attack

---

## 🚀 Next Steps

1. **Create `v2x_simulation.py`** - Main simulation script
2. **Create `v2x_messages.py`** - Message handling
3. **Create `crypto_classical.py`** - Classical encryption
4. **Create `crypto_postquantum.py`** - Post-quantum encryption
5. **Create `mitm_attacker.py`** - Attacker simulation

---

## 📚 Resources

- SUMO Documentation: https://sumo.dlr.de/docs/
- TraCI Python API: https://sumo.dlr.de/docs/TraCI/Interfacing_TraCI_from_Python.html
- Post-Quantum Crypto: https://csrc.nist.gov/Projects/post-quantum-cryptography

