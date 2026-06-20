"""
Test PDF Generator
"""
from pdf_generator import PDFGenerator
from datetime import datetime
import os

print("📄 Testing PDF Generator...")
print("="*80)

try:
    # Initialize generator
    print("\n🔄 Initializing PDF generator...")
    generator = PDFGenerator()
    print("✅ Generator initialized")
    
    # Test data
    print("\n📝 Creating test violations...")
    violations = [
        {
            'timestamp': datetime.now(),
            'class_name': 'no_helmet',
            'description': 'Worker not wearing required hard hat',
            'confidence': 0.95,
            'osha_regulation': '29 CFR 1926.100'
        },
        {
            'timestamp': datetime.now(),
            'class_name': 'no_vest',
            'description': 'High visibility vest not worn',
            'confidence': 0.88,
            'osha_regulation': '29 CFR 1926.201'
        },
        {
            'timestamp': datetime.now(),
            'class_name': 'no_gloves',
            'description': 'Hand protection not used',
            'confidence': 0.82,
            'osha_regulation': '29 CFR 1926.95'
        }
    ]
    print(f"✅ Created {len(violations)} test violations")
    
    compliance_report = """
TEST COMPLIANCE REPORT
======================

OSHA Violations Detected:
- Hard hat requirement violated (29 CFR 1926.100)
- High visibility vest required (29 CFR 1926.201)
- Hand protection required (29 CFR 1926.95)

Severity Assessment:
- HIGH: Immediate risk to worker safety
- MEDIUM: Potential safety hazard
- LOW: Minor compliance issue

Recommendations:
1. Immediate corrective action required for high-severity violations
2. Worker safety training recommended for all personnel
3. Site supervisor notification and follow-up
4. Update safety signage and reminders
5. Conduct safety audit within 24 hours

OSHA Regulation References:
- 29 CFR 1926.100: Head protection
- 29 CFR 1926.201: Signaling and high-visibility clothing
- 29 CFR 1926.95: Criteria for personal protective equipment

Next Steps:
- Document corrective actions taken
- Schedule safety meeting with affected workers
- Review site safety protocols
- Submit incident report to safety manager
"""
    
    # Test 1: Single incident report
    print("\n📋 Test 1: Generating incident report...")
    output_path = generator.generate_pdf(
        violations[0],
        compliance_report,
        None  # No image path
    )
    
    if os.path.exists(output_path):
        file_size = os.path.getsize(output_path)
        print(f"✅ PDF generated: {output_path}")
        print(f"✅ File size: {file_size:,} bytes")
    else:
        print(f"❌ ERROR: File not created")
    
    # Test 2: Summary report
    print("\n📊 Test 2: Generating summary report...")
    summary_path = generator.generate_summary_report(violations)
    
    if os.path.exists(summary_path):
        file_size = os.path.getsize(summary_path)
        print(f"✅ Summary PDF generated: {summary_path}")
        print(f"✅ File size: {file_size:,} bytes")
    else:
        print(f"❌ ERROR: File not created")
    
    # Test 3: Check reports folder
    print("\n📁 Test 3: Checking reports folder...")
    if os.path.exists('reports'):
        report_files = [f for f in os.listdir('reports') if f.endswith('.pdf')]
        print(f"✅ Found {len(report_files)} PDF files in reports/")
        
        if report_files:
            print("\nRecent reports:")
            for i, filename in enumerate(sorted(report_files, reverse=True)[:5], 1):
                filepath = os.path.join('reports', filename)
                size = os.path.getsize(filepath)
                print(f"  {i}. {filename} ({size:,} bytes)")
    else:
        print("⚠️  reports/ folder not found")
    
    print("\n" + "="*80)
    print("✅ PDF Tests PASSED!")
    print(f"✅ Generated reports are in: {os.path.abspath('reports')}")
    print("="*80)
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    print("\n❌ PDF tests FAILED!")
