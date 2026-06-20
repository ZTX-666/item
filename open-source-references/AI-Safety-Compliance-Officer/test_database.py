"""
Test Database Operations
"""
from database import Database
from datetime import datetime

print("🗄️  Testing Database...")
print("="*80)

try:
    db = Database()
    
    # Test 1: Get stats
    print("\n📊 Test 1: Get Statistics")
    stats = db.get_violation_stats()
    print(f"✅ Total violations: {stats['total']}")
    print(f"✅ By type: {stats['by_type']}")
    
    # Test 2: Log test violation
    print("\n➕ Test 2: Log Violation")
    test_violation = {
        'timestamp': datetime.now(),
        'class_name': 'no_helmet',
        'description': 'Worker not wearing required hard hat',
        'confidence': 0.95,
        'osha_regulation': '29 CFR 1926.100'
    }
    
    violation_record = db.log_violation(
        test_violation, 
        image_path='test.jpg',
        pdf_path='test_report.pdf',
        email_sent=False
    )
    print(f"✅ Logged test violation: ID {violation_record.id}")
    
    # Test 3: Retrieve violations
    print("\n📋 Test 3: Retrieve Recent Violations")
    recent = db.get_recent_violations(limit=5)
    print(f"✅ Retrieved {len(recent)} recent violations")
    
    if recent:
        print("\nMost recent violation:")
        latest = recent[0]
        print(f"  - Type: {latest.class_name}")
        print(f"  - Description: {latest.description}")
        print(f"  - Time: {latest.timestamp}")
        print(f"  - Confidence: {latest.confidence}")
        print(f"  - OSHA: {latest.osha_regulation}")
    
    # Test 4: Get total violations
    print("\n🔢 Test 4: Get Total Count")
    total = db.get_total_violations()
    print(f"✅ Total violations in database: {total}")
    
    print("\n" + "="*80)
    print("✅ All Database Tests PASSED!")
    print("="*80)
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    print("\n❌ Database tests FAILED!")
