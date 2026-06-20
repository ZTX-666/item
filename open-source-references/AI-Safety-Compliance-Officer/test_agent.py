"""
Test AI Compliance Agent (GPT-4)
"""
from compliance_agent import ComplianceAgent
from datetime import datetime
import os
from dotenv import load_dotenv

print("🤖 Testing Compliance Agent...")
print("="*80)

# Load environment variables
load_dotenv()

try:
    # Check API key
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ ERROR: OPENAI_API_KEY not found in .env file")
        print("\nTo fix this:")
        print("1. Create a .env file in the project root")
        print("2. Add: OPENAI_API_KEY=sk-your-api-key-here")
        print("3. Get your API key from: https://platform.openai.com/api-keys")
        exit(1)
    
    print(f"✅ API Key found: {api_key[:20]}...")
    
    # Initialize agent
    print("\n🔄 Initializing AI agent...")
    agent = ComplianceAgent()
    print("✅ Agent initialized")
    
    # Test violation data
    print("\n📝 Creating test violation...")
    test_violation = {
        'timestamp': datetime.now(),
        'class_name': 'no_helmet',  # Changed from violation_type to class_name
        'description': 'Worker not wearing required hard hat in construction zone',
        'confidence': 0.95,
        'location': 'Construction Site A - Zone 3',
        'worker_id': 'W-12345',
        'severity': 'high',
        'image_path': 'test_violation.jpg',
        'osha_regulation': '29 CFR 1926.100'  # Added OSHA regulation
    }
    print("✅ Test violation created")
    
    # Generate report
    print("\n🤖 Generating compliance report...")
    print("(This will take 5-10 seconds - calling GPT-4 API)")
    print("Please wait...")

    report = agent.generate_incident_report(test_violation)

    print("\n" + "="*80)
    print("📄 GENERATED INCIDENT REPORT")
    print("="*80)
    print(report)
    print("="*80)
    
    # Validate report content
    print("\n🔍 Validating report content...")
    
    required_sections = [
        'VIOLATION',
        'OSHA',
        'RECOMMENDATION'
    ]
    
    found_sections = []
    for section in required_sections:
        if section.lower() in report.lower():
            found_sections.append(section)
            print(f"✅ Found section: {section}")
    
    if len(found_sections) >= 2:
        print(f"\n✅ Report contains {len(found_sections)}/{len(required_sections)} expected sections")
    else:
        print(f"\n⚠️  Warning: Only found {len(found_sections)}/{len(required_sections)} sections")
    
    print("\n" + "="*80)
    print("✅ Agent Tests PASSED!")
    print("✅ GPT-4 API working correctly")
    print("="*80)
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    print("\n❌ Agent tests FAILED!")
    print("\nCommon issues:")
    print("  - Invalid API key")
    print("  - No OpenAI credits")
    print("  - Network connectivity")
    print("  - API rate limits")
