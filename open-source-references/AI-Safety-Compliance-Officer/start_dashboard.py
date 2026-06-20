"""
Quick Start Script for Camera Management Dashboard
Purpose: Launch dashboard locally for testing
"""

import subprocess
import sys
import os
import time
import webbrowser

def check_dependencies():
    """Check if required packages are installed"""
    required = ['flask', 'flask_cors', 'boto3', 'sqlalchemy']
    missing = []
    
    for package in required:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"❌ Missing dependencies: {', '.join(missing)}")
        print(f"Installing...")
        subprocess.run([sys.executable, '-m', 'pip', 'install'] + missing)
        return False
    
    return True

def check_config_files():
    """Check if required configuration files exist"""
    if not os.path.exists('cameras.json'):
        print("⚠️  cameras.json not found!")
        print("Creating default configuration...")
        
        default_config = '''{
  "cameras": [
    {
      "id": "demo_camera_1",
      "name": "Demo Camera 1",
      "source": "0",
      "enabled": true,
      "location": "Test Location",
      "description": "Demo camera for testing"
    }
  ],
  "settings": {
    "auto_refresh_interval": 30,
    "alerts_enabled": true
  }
}'''
        with open('cameras.json', 'w') as f:
            f.write(default_config)
        
        print("✅ Created cameras.json")
    
    if not os.path.exists('.env'):
        print("⚠️  .env file not found!")
        print("Please create .env file with required configuration.")
        print("See .env.examples for templates.")
        return False
    
    return True

def start_dashboard():
    """Start the dashboard server"""
    print("\n" + "="*80)
    print("🚀 Starting Camera Management Dashboard")
    print("="*80)
    print("")
    
    port = 5000
    url = f"http://localhost:{port}"
    
    print(f"📡 Dashboard URL: {url}")
    print(f"📊 API Endpoints: {url}/api/")
    print(f"🔧 Press Ctrl+C to stop")
    print("")
    print("="*80)
    
    # Wait a moment then open browser
    time.sleep(2)
    print(f"\n🌐 Opening dashboard in browser...")
    webbrowser.open(url)
    
    # Start Flask app
    os.environ['FLASK_ENV'] = 'development'
    os.environ['FLASK_DEBUG'] = 'true'
    subprocess.run([sys.executable, 'dashboard.py'])

def main():
    """Main execution"""
    print("="*80)
    print("🎛️  Camera Management Dashboard - Quick Start")
    print("="*80)
    print("")
    
    # Step 1: Check dependencies
    print("📦 Checking dependencies...")
    if not check_dependencies():
        print("✅ Dependencies installed")
    else:
        print("✅ All dependencies satisfied")
    
    # Step 2: Check configuration
    print("\n⚙️  Checking configuration...")
    if not check_config_files():
        print("\n❌ Please configure .env file before starting")
        sys.exit(1)
    
    print("✅ Configuration ready")
    
    # Step 3: Create required directories
    print("\n📁 Creating directories...")
    os.makedirs('reports', exist_ok=True)
    os.makedirs('violations', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    print("✅ Directories created")
    
    # Step 4: Start dashboard
    try:
        start_dashboard()
    except KeyboardInterrupt:
        print("\n\n🛑 Dashboard stopped by user")
        print("="*80)
        print("Thank you for using Camera Management Dashboard!")
        print("="*80)

if __name__ == "__main__":
    main()
