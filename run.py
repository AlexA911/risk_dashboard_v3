"""
run.py — starts both backend and frontend
Run with: python run.py
"""
import subprocess
import sys
import os
import time
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))

def main():
    print("🚀 Starting Risk Dashboard v2...")

    backend = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--port", "8002"],
        cwd=ROOT
    )
    print("✅ Backend starting on http://localhost:8000")

    frontend = subprocess.Popen(
        ["npm", "run", "dev", "--", "--port", "3001"],
        cwd=os.path.join(ROOT, "frontend"),
        shell=True
    )
    print("✅ Frontend starting...")

    time.sleep(4)
    webbrowser.open("http://localhost:3001")
    print("\n   Press Ctrl+C to stop.\n")

    try:
        backend.wait()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        backend.terminate()
        frontend.terminate()
        print("✅ Stopped.")

if __name__ == "__main__":
    main()
