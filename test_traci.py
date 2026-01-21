import os
import sys
import subprocess

SUMO_HOME = r"C:\Program Files (x86)\Eclipse\Sumo"
sys.path.append(os.path.join(SUMO_HOME, "tools"))

# Build network file from nodes and edges
netconvert_path = os.path.join(SUMO_HOME, "bin", "netconvert.exe")
sumo_test_dir = os.path.join(os.path.dirname(__file__), "sumo_test")
network_file = os.path.join(sumo_test_dir, "network.net.xml")
nodes_file = os.path.join(sumo_test_dir, "nodes.nod.xml")
edges_file = os.path.join(sumo_test_dir, "edges.edg.xml")

# Check if network file exists, if not build it
if not os.path.exists(network_file):
    print("Building network file from nodes and edges...")
    cmd = [
        netconvert_path,
        "--node-files", nodes_file,
        "--edge-files", edges_file,
        "--output-file", network_file
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error building network: {result.stderr}")
        sys.exit(1)
    print("Network file built successfully!")

import traci
print("TraCI imported successfully!")
