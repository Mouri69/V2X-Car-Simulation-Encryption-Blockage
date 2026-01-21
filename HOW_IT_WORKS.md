# 🚗 V2X Simulation - How It Works

## 📋 Overview

This simulation demonstrates **Vehicle-to-Vehicle (V2V) communication** with:
- **Classical Cryptography** (AES/RSA) - vulnerable to quantum attacks
- **Post-Quantum Cryptography** - quantum-resistant
- **MITM (Man-in-the-Middle) Attack** - intercepts and attempts to break encryption

---

## ⏱️ Simulation Time

**Duration: 2 minutes (120 seconds)**
- The simulation runs for 120 seconds
- You can see it in real-time in the SUMO GUI
- Console shows all communication events

---

## 🔐 How Encryption Works

### 1. **Classical Cryptography (AES/RSA)**
- Used from 0-30s, 60-90s
- **AES**: Symmetric encryption (fast, but key exchange vulnerable)
- **RSA**: Asymmetric encryption (vulnerable to quantum computers)
- **Vulnerability**: Quantum computers can break RSA using Shor's algorithm

### 2. **Post-Quantum Cryptography**
- Used from 30-60s, 90-120s
- **CRYSTALS-Kyber**: Key exchange algorithm
- **CRYSTALS-Dilithium**: Digital signatures
- **Resistance**: No known quantum algorithm can break it efficiently

### 3. **Automatic Switching**
- Every 30 seconds, the crypto mode switches
- Watch for: `🔄 Switched to POST-QUANTUM encryption` or `🔄 Switched to CLASSICAL encryption`

---

## 📡 How V2V Communication Works

### Step-by-Step Process:

1. **Neighbor Detection** (Every simulation step)
   - Each vehicle checks for other vehicles within **300 meters**
   - Uses distance calculation: `√((x₁-x₂)² + (y₁-y₂)²)`

2. **Message Creation** (Every 2 seconds)
   - Vehicle creates a **BSM (Basic Safety Message)**
   - Contains: position, speed, heading, acceleration
   - Example: `vehicle1 → vehicle2: BSM [AES/RSA (Classical)]`

3. **Encryption**
   - Message is encrypted using current crypto mode
   - Classical: AES/RSA encryption
   - Post-Quantum: Lattice-based encryption

4. **MITM Interception**
   - Purple vehicle (mitm_attacker) intercepts all messages
   - Attempts to break encryption
   - **Classical**: Can be broken (simulated)
   - **Post-Quantum**: Resists attack

5. **Message Logging**
   - All messages logged to console
   - Statistics shown at end

---

## 🛑 How to See When Cars Stop

### Detection Method:
- System monitors vehicle speed every step
- If speed drops from >0.1 m/s to <0.1 m/s → **STOP detected**
- Console shows: `🛑 vehicle1 STOPPED at time 45.2s`

### What You'll See:
- In SUMO GUI: Vehicle stops moving
- In Console: Stop event logged
- Position and speed shown every 10 seconds

---

## 📊 Console Output Explained

### Status Updates (Every 10 seconds):
```
⏱️  Time: 25.0s | Vehicles: 3 | Messages: 12 | Crypto: CLASSICAL
  🚗 Active: vehicle1, vehicle2, vehicle3
  📡 vehicle1 ↔ vehicle2, vehicle3 (range: 300m)
     Position: (150.5, 200.3) | Speed: 12.50 m/s
```

### Message Transmission:
```
📡 vehicle1 → vehicle2: BSM [AES/RSA (Classical)]
📡 vehicle2 → vehicle3: BSM [Post-Quantum]
🛑 vehicle1 STOPPED at time 45.2s
🔄 Switched to POST-QUANTUM encryption at 30.0s
```

### End Statistics:
```
📊 Communication Statistics:
   Total messages sent: 45
   Classical crypto (AES/RSA): 22
   Post-quantum crypto: 23
   MITM intercepted: 45
```

---

## 🎮 How to Use

### Run the Simulation:
```powershell
py v2x_simulation.py
```

### What to Watch:

1. **SUMO GUI Window**:
   - Red, Green, Blue vehicles (normal)
   - Purple vehicle (MITM attacker)
   - Vehicles moving on grid network

2. **Console Output**:
   - 📡 = Message sent
   - 🛑 = Vehicle stopped
   - 🔄 = Crypto mode switched
   - ⏱️ = Status update

3. **Communication Events**:
   - Messages appear every 2 seconds
   - Shows encryption type
   - Shows MITM interception

---

## 🔍 Checking Communication

### Real-Time Monitoring:
- Watch console for `📡` messages
- Check encryption type: `[AES/RSA (Classical)]` or `[Post-Quantum]`
- See MITM interception attempts

### End-of-Simulation Report:
- Total messages sent
- Breakdown by crypto type
- MITM attack statistics
- Success/failure of attacks

---

## 🛠️ Customization

### Change Simulation Time:
Edit `v2x_simulation.py` line 21:
```python
SIMULATION_END = 120  # Change to any value (in seconds)
```

### Change Communication Range:
Edit line 20:
```python
COMMUNICATION_RANGE = 300  # Change range in meters
```

### Change Message Frequency:
Edit `_send_periodic_messages` function:
```python
if int(current_time) % 2 == 0:  # Change 2 to any number (seconds)
```

---

## 📚 Key Concepts

### V2V Communication:
- **BSM**: Basic Safety Message (position, speed, heading)
- **Range**: 300m typical V2X range
- **Frequency**: Every 2 seconds

### Cryptography:
- **Classical**: Fast, but vulnerable to quantum
- **Post-Quantum**: Slower, but quantum-resistant
- **MITM**: Intercepts and attempts to break encryption

### Security:
- **Quantum Threat**: Future quantum computers can break RSA
- **Solution**: Post-quantum cryptography
- **Demonstration**: Shows why we need quantum-resistant crypto

---

## 🎯 What This Demonstrates

1. ✅ **V2V Communication**: Vehicles exchange safety messages
2. ✅ **Encryption**: Messages are encrypted for security
3. ✅ **MITM Attack**: Attacker intercepts messages
4. ✅ **Quantum Vulnerability**: Classical crypto can be broken
5. ✅ **Post-Quantum Solution**: Quantum-resistant crypto works
6. ✅ **Real-Time Monitoring**: See all events as they happen

---

## 💡 Tips

- **Watch the console** for detailed communication logs
- **Look for color changes** in SUMO GUI (vehicles are colored)
- **Check stop events** when vehicles slow down
- **Observe crypto switching** every 30 seconds
- **Review statistics** at the end for full picture

---

Enjoy exploring V2X communication and post-quantum security! 🚀

