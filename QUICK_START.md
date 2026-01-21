# 🚀 Quick Start Guide - V2X Simulation

## Prerequisites
- ✅ SUMO installed at: `C:\Program Files (x86)\Eclipse\Sumo`
- ✅ Python 3.x installed
- ✅ Network file exists: `sumo_test/network.net.xml`

## How to Run

### Option 1: Basic Simulation (GUI)
```powershell
py v2x_simulation.py
```
- Opens SUMO GUI
- Shows 3 vehicles moving on the network
- Displays V2V communication in console

**Note**: Make sure line 64 in `v2x_simulation.py` uses `sumo-gui.exe`:
```python
sumo_binary = os.path.join(SUMO_HOME, "bin", "sumo-gui.exe")
```

### Option 2: Full Demo with MITM Attack
```powershell
py v2x_demo.py
```
- Complete demonstration
- Shows classical crypto being broken
- Shows post-quantum crypto resisting attacks
- Includes MITM attacker simulation

### Option 3: Headless (No GUI)
Edit `v2x_simulation.py` line 64:
```python
sumo_binary = os.path.join(SUMO_HOME, "bin", "sumo.exe")  # Use sumo.exe for headless
```

## Troubleshooting

### Error: "No edges found"
- The network file might be missing
- Run: The script will auto-build it

### Error: "TraCI connection failed"
- Make sure SUMO is installed correctly
- Check SUMO_HOME path in the script

### Vehicles not visible
- Wait a few seconds for vehicles to spawn
- Check that routes are valid
- Use GUI version to see vehicles

## What You'll See

1. **Console Output**: 
   - Vehicle status
   - V2V communication
   - Neighbor detection

2. **SUMO GUI** (if using sumo-gui.exe):
   - Road network
   - Moving vehicles (colored)
   - Real-time simulation

3. **Demo Output** (v2x_demo.py):
   - Classical crypto attack demonstration
   - Post-quantum crypto resistance
   - MITM attack statistics

## Next Steps

1. Run `python v2x_simulation.py` to see basic simulation
2. Run `python v2x_demo.py` for full security demonstration
3. Modify vehicles, routes, or crypto in the code
4. Add your own attack scenarios

