"""
Test script to verify AI Safety Compliance Officer components
Run this to test your setup before using the full system
"""

import sys
import os

def test_imports():
    """Test if all required packages are installed"""
    print("\n" + "="*80)
    print("Testing Package Imports...")
    print("="*80)
    
    packages = [
        ('cv2', 'opencv-python'),
        ('ultralytics', 'ultralytics'),
        ('langchain', 'langchain'),
        ('langchain_openai', 'langchain-openai'),
        ('reportlab', 'reportlab'),
        ('sqlalchemy', 'sqlalchemy'),
        ('dotenv', 'python-dotenv'),
    ]
    
    failed = []
    for package, pip_name in packages:
        try:
            __import__(package)
            print(f"✅ {pip_name}")
        except ImportError:
            print(f"❌ {pip_name} - NOT INSTALLED")
            failed.append(pip_name)
    
    if failed:
        print(f"\n⚠️  Missing packages: {', '.join(failed)}")
        print("Run: pip install -r requirements.txt")
        return False
    
    print("\n✅ All packages installed!")
    return True

def test_config():
    """Test configuration"""
    print("\n" + "="*80)
    print("Testing Configuration...")
    print("="*80)
    
    try:
        import config
        
        # Check .env file
        if not os.path.exists('.env'):
            print("⚠️  .env file not found!")
            print("Run: python setup.py")
            return False
        
        print("✅ .env file exists")
        
        # Check API key
        if not config.OPENAI_API_KEY or config.OPENAI_API_KEY == "":
            print("⚠️  OPENAI_API_KEY not configured in .env")
            return False
        else:
            print(f"✅ OpenAI API Key configured (starts with: {config.OPENAI_API_KEY[:10]}...)")
        
        # Check email config
        if config.EMAIL_ENABLED:
            if not config.EMAIL_SENDER or not config.EMAIL_PASSWORD:
                print("⚠️  Email enabled but credentials not configured")
            else:
                print(f"✅ Email configured: {config.EMAIL_SENDER}")
        
        # Check model
        if not os.path.exists(config.MODEL_PATH):
            print(f"⚠️  Model not found at: {config.MODEL_PATH}")
            print("Copy your best.onnx model to models/ folder")
            return False
        else:
            print(f"✅ Model found: {config.MODEL_PATH}")
        
        print("\n✅ Configuration OK!")
        return True
        
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return False

def test_detector():
    """Test violation detector"""
    print("\n" + "="*80)
    print("Testing Violation Detector...")
    print("="*80)
    
    try:
        from violation_detector import ViolationDetector
        import numpy as np
        
        detector = ViolationDetector()
        print("✅ Detector initialized")
        
        # Create dummy frame
        dummy_frame = np.zeros((640, 640, 3), dtype=np.uint8)
        
        # Test detection (should return empty list for blank frame)
        violations = detector.detect_violations(dummy_frame)
        print(f"✅ Detection works (found {len(violations)} violations in blank frame)")
        
        return True
        
    except Exception as e:
        print(f"❌ Detector error: {e}")
        return False

def test_agent():
    """Test AI agent"""
    print("\n" + "="*80)
    print("Testing AI Compliance Agent...")
    print("="*80)
    
    try:
        from compliance_agent import ComplianceAgent
        from datetime import datetime
        
        agent = ComplianceAgent()
        print("✅ Agent initialized")
        
        # Test with dummy violation
        test_violation = {
            'timestamp': datetime.now(),
            'class_name': 'no_helmet',
            'description': 'Worker without helmet (TEST)',
            'confidence': 0.95,
            'osha_regulation': '29 CFR 1926.100(a) - Head Protection'
        }
        
        print("Generating test report (this may take a few seconds)...")
        report = agent.generate_incident_report(test_violation)
        
        if len(report) > 100:
            print("✅ AI report generation works!")
            print(f"   Report length: {len(report)} characters")
        else:
            print("⚠️  Report seems too short")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Agent error: {e}")
        print("Check your OpenAI API key and internet connection")
        return False

def test_pdf():
    """Test PDF generation"""
    print("\n" + "="*80)
    print("Testing PDF Generator...")
    print("="*80)
    
    try:
        from pdf_generator import PDFGenerator
        from datetime import datetime
        import os
        
        generator = PDFGenerator()
        print("✅ PDF generator initialized")
        
        return True
        
    except Exception as e:
        print(f"❌ PDF generator error: {e}")
        return False

def test_database():
    """Test database"""
    print("\n" + "="*80)
    print("Testing Database...")
    print("="*80)
    
    try:
        from database import Database
        
        db = Database('test_violations.db')
        print("✅ Database initialized")
        
        stats = db.get_violation_stats()
        print(f"✅ Database queries work (Total records: {stats['total']})")
        
        db.close()
        
        # Cleanup test database
        if os.path.exists('test_violations.db'):
            os.remove('test_violations.db')
        
        return True
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

def main():
    """Run all tests"""
    print("="*80)
    print("AI Safety Compliance Officer - System Test")
    print("="*80)
    
    tests = [
        ("Imports", test_imports),
        ("Configuration", test_config),
        ("Violation Detector", test_detector),
        ("Database", test_database),
        ("PDF Generator", test_pdf),
        ("AI Agent", test_agent),
    ]
    
    results = {}
    
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"\n❌ Unexpected error in {name}: {e}")
            results[name] = False
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {name}")
    
    total = len(results)
    passed = sum(results.values())
    
    print("="*80)
    print(f"Results: {passed}/{total} tests passed")
    print("="*80)
    
    if passed == total:
        print("\n🎉 All tests passed! System ready to use.")
        print("Run: python safety_monitor.py --source 0")
    else:
        print("\n⚠️  Some tests failed. Please fix issues above.")
        print("Refer to QUICKSTART.md for help")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
