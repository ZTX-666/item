"""
Master Test Runner - Run all tests in sequence
"""
import subprocess
import sys
import time

# Define all tests
TESTS = [
    {
        'name': 'Database Operations',
        'file': 'test_database.py',
        'icon': '🗄️',
        'required': True
    },
    {
        'name': 'PDF Generator',
        'file': 'test_pdf.py',
        'icon': '📄',
        'required': True
    },
    {
        'name': 'Violation Detector',
        'file': 'test_detector.py',
        'icon': '👁️',
        'required': True
    },
    {
        'name': 'AI Compliance Agent',
        'file': 'test_agent.py',
        'icon': '🤖',
        'required': False  # Optional (needs API key)
    },
    {
        'name': 'Email Sender',
        'file': 'test_email_simple.py',
        'icon': '📧',
        'required': False  # Optional (needs email config)
    }
]

def run_test(test):
    """Run a single test"""
    print(f"\n{'='*80}")
    print(f"{test['icon']}  Running: {test['name']}")
    print(f"{'='*80}")
    
    try:
        result = subprocess.run(
            [sys.executable, test['file']],
            capture_output=False,
            text=True,
            timeout=60
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"\n⚠️  Test timed out after 60 seconds")
        return False
    except Exception as e:
        print(f"\n❌ Error running test: {e}")
        return False

def main():
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║                  🧪 AI SAFETY COMPLIANCE OFFICER                            ║
║                        Master Test Suite                                    ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)
    
    print("\nThis will run all system tests in sequence.")
    print("Some tests (AI Agent, Email) are optional and may be skipped if not configured.\n")
    
    input("Press ENTER to start testing...")
    
    results = []
    start_time = time.time()
    
    # Run each test
    for test in TESTS:
        success = run_test(test)
        results.append({
            'test': test,
            'success': success
        })
        
        if not success and test['required']:
            print(f"\n⚠️  CRITICAL: {test['name']} failed!")
            print("This is a required component. Please fix before proceeding.")
            
            response = input("\nContinue with remaining tests? (y/n): ")
            if response.lower() != 'y':
                break
        
        time.sleep(1)
    
    # Print summary
    duration = time.time() - start_time
    
    print(f"\n\n{'='*80}")
    print("📊 TEST SUMMARY")
    print(f"{'='*80}")
    
    passed = sum(1 for r in results if r['success'])
    total = len(results)
    
    for result in results:
        test = result['test']
        status = "✅ PASSED" if result['success'] else "❌ FAILED"
        required = "REQUIRED" if test['required'] else "OPTIONAL"
        print(f"{test['icon']}  {test['name']:<30} {status:<15} [{required}]")
    
    print(f"\n{'='*80}")
    print(f"Results: {passed}/{total} tests passed")
    print(f"Duration: {duration:.1f} seconds")
    print(f"{'='*80}")
    
    # Check critical failures
    critical_failures = [
        r for r in results 
        if not r['success'] and r['test']['required']
    ]
    
    if critical_failures:
        print(f"\n⚠️  {len(critical_failures)} CRITICAL TEST(S) FAILED")
        print("Please fix these issues before proceeding to production.")
        return 1
    else:
        print("\n✅ All critical tests passed!")
        print("Your system is ready for the next phase.")
        
        # Next steps
        print(f"\n{'='*80}")
        print("📋 NEXT STEPS")
        print(f"{'='*80}")
        print("1. Review test results above")
        print("2. Fix any optional tests if needed")
        print("3. Run full system test: python test_full_system.py")
        print("4. Check dashboard: http://localhost:5000")
        print("5. Proceed to CI/CD setup or AWS deployment")
        
        return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Testing interrupted by user")
        sys.exit(1)
