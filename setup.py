import os
import subprocess
from setuptools import setup
from setuptools.command.install import install
from setuptools.command.develop import develop

def build_node_app():
    print("=== Yegna Bet: Setting up Node.js environment inside Python runtime ===")
    try:
        # Install Node.js inside python venv if node is not found
        subprocess.run(["nodeenv", "-p"], check=True)
        print("=== Node.js installed into environment successfully ===")
    except Exception as e:
        print(f"Notice during nodeenv execution: {e}")

    # Ensure npm install & npm run build are executed
    try:
        subprocess.run(["npm", "install"], check=True)
        subprocess.run(["npm", "run", "build"], check=True)
        print("=== Yegna Bet Node.js frontend & backend built successfully ===")
    except Exception as e:
        print(f"Build error: {e}")

class CustomInstallCommand(install):
    def run(self):
        install.run(self)
        build_node_app()

class CustomDevelopCommand(develop):
    def run(self):
        develop.run(self)
        build_node_app()

setup(
    name="yegna-bet-runner",
    version="1.0.0",
    cmdclass={
        'install': CustomInstallCommand,
        'develop': CustomDevelopCommand,
    },
)
