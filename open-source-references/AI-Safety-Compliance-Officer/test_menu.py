"""
Quick Test Launcher
Interactive menu to run specific tests
"""
import subprocess
import sys
import os

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_menu():
    clear_screen()
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║               🧪 AI SAFETY COMPLIANCE OFFICER - TEST MENU                   ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

Select a test to run:

CORE COMPONENT TESTS:
  1. 🗄️  Database Operations Test
  2. 👁️  Violation Detector Test (Webcam)
  3. 🤖 AI Compliance Agent Test (GPT-4)
  4. 📄 PDF Generator Test
  5. 📧 Email Sender Test

SYSTEM TESTS:
  6. 🎯 Full System Test (30 seconds)
  7. 🎛️  Dashboard Test (Browser)

COMPREHENSIVE:
  8. 🚀 Run ALL Tests (Automated)

UTILITIES:
  9. 📊 Check Current Status
  0. ❌ Exit

══════════════════════════════════════════════════════════════════════════════
    """)

def run_command(cmd, description):
    print(f"\n{'='*80}")
    print(f"▶️  {description}")
    print(f"{'='*80}\n")
    
    try:
        result = subprocess.run(cmd, shell=True)
        return result.returncode == 0
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted")
        return False

def check_status():
    """Check system status"""
    print(f"\n{'='*80}")
    print("📊 SYSTEM STATUS CHECK")
    print(f"{'='*80}\n")
    
    checks = [
        ("Python Version", "python --version"),
        ("Model File", "python -c \"import os; print('✅ Found' if os.path.exists('models/best.onnx') else '❌ Missing')\""),
        ("Database", "python -c \"import os; print('✅ Found' if os.path.exists('violations.db') else '⚠️  Will be created')\""),
        ("Packages", "python -c \"import ultralytics, langchain, flask; print('✅ Installed')\""),
    ]
    
    for name, cmd in checks:
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            output = result.stdout.strip() if result.stdout else result.stderr.strip()
            print(f"{name}: {output}")
        except:
            print(f"{name}: ❌ Error")
    
    print(f"\n{'='*80}")
    input("\nPress ENTER to continue...")

def main():
    tests = {
        '1': ('python test_database.py', 'Testing Database Operations'),
        '2': ('python test_detector.py', 'Testing Violation Detector (Webcam)'),
        '3': ('python test_agent.py', 'Testing AI Compliance Agent (GPT-4)'),
        '4': ('python test_pdf.py', 'Testing PDF Generator'),
        '5': ('python test_email_simple.py', 'Testing Email Sender'),
        '6': ('python test_full_system.py', 'Running Full System Test'),
        '7': ('start http://localhost:5000', 'Opening Dashboard in Browser'),
        '8': ('python run_all_tests.py', 'Running ALL Tests'),
        '9': (check_status, 'Checking System Status'),
    }
    
    while True:
        print_menu()
        choice = input("Enter your choice (0-9): ").strip()
        
        if choice == '0':
            print("\n👋 Goodbye!")
            break
        
        if choice in tests:
            if callable(tests[choice][0]):
                tests[choice][0]()
            else:
                cmd, desc = tests[choice]
                run_command(cmd, desc)
            
            if choice != '9':
                input("\n\nPress ENTER to return to menu...")
        else:
            print("\n❌ Invalid choice. Please try again.")
            input("Press ENTER to continue...")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
        sys.exit(0)
