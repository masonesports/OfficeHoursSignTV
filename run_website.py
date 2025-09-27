#!/usr/bin/env python3
"""
Simple script to run the Flask website without test code.
"""

from app import app

if __name__ == "__main__":
    print("🌐 Starting GMU Esports Office Hours Website...")
    print("📍 Website will be available at: http://localhost:5000")
    print("🔄 Press Ctrl+C to stop the server")
    
    try:
        app.run(host="0.0.0.0", port=5000, debug=False)
    except KeyboardInterrupt:
        print("\n👋 Website server stopped.")
