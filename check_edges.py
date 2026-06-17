
import os
import sys
import traci

# Set SUMO_HOME (if not already set)
if "SUMO_HOME" not in os.environ:
    import platform
    if platform.system() == "Windows":
        # Common SUMO install paths on Windows
        possible_paths = [
            "C:\\Program Files (x86)\\Eclipse\\Sumo",
            "C:\\Program Files\\Eclipse\\Sumo",
            os.path.expanduser("~\\Sumo")
        ]
        for path in possible_paths:
            if os.path.exists(path):
                os.environ["SUMO_HOME"] = path
                break

SUMO_HOME = os.environ.get("SUMO_HOME")
sumo_binary = os.path.join(SUMO_HOME, "bin", "sumo.exe") if SUMO_HOME else None
sumo_cfg = "sumo_test/sim.sumocfg"

try:
    # Start SUMO in headless mode
    traci.start([sumo_binary, "-c", sumo_cfg, "--start"])
    
    # Get all edge IDs
    all_edges = traci.edge.getIDList()
    print("All edge IDs in network:")
    print("=" * 80)
    for edge_id in all_edges:
        if not edge_id.startswith(":"):  # Skip internal edges
            from_junc = traci.edge.getFromJunction(edge_id)
            to_junc = traci.edge.getToJunction(edge_id)
            print(f"Edge: {edge_id:15} | From: {from_junc:5} | To: {to_junc:5}")
    
    print("\n" + "=" * 80)
    print("\nAll junction IDs and positions:")
    print("=" * 80)
    for junc_id in traci.junction.getIDList():
        pos = traci.junction.getPosition(junc_id)
        print(f"Junction: {junc_id:5} | Position: ({pos[0]:.1f}, {pos[1]:.1f})")
    
    traci.close()
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

