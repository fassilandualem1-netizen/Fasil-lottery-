import os
import sys
import subprocess

print("=== Starting Yegna Bet Node Express Backend Server ===")

# Find node binary
node_path = "node"

# Check if server build exists, if not build it
if not os.path.exists("dist/server.cjs"):
    print("Building server bundle...")
    subprocess.run(["npm", "run", "build"], check=True)

# Execute Node.js server
try:
    os.execvp(node_path, [node_path, "dist/server.cjs"])
except Exception as err:
    print(f"Error launching node server: {err}")
    sys.exit(1)
