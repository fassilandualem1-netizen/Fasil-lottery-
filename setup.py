import os
import subprocess
from setuptools import setup
from setuptools.command.install import install
from setuptools.command.develop import develop

def build_node_app():
    print("=== Yegna Bet: Building Node.js frontend & backend ===")
    try:
        subprocess.run(["npm", "install"], check=True)
        subprocess.run(["npm", "run", "build"], check=True)
        print("=== Yegna Bet build complete ===")
    except Exception as e:
        print(f"Build step notice: {e}")

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
