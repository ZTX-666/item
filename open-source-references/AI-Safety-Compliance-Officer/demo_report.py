"""
Demo script to generate a sample violation report
This will create a PDF report without running the full monitoring system
"""

from datetime import datetime
from compliance_agent import ComplianceAgent
from pdf_generator import PDFGenerator
import config

def generate_demo_report():
    """Generate a sample violation report for demonstration"""
    
    print("="*80)
    print("Generating Demo Safety Violation Report")
    print("="*80)
    
    # Create a sample violation
    sample_violation = {
        'timestamp': datetime.now(),
        'class_name': 'no_helmet',
        'description': 'Worker without hard hat/helmet',
        'confidence': 0.945,
        'osha_regulation': '29 CFR 1926.100(a) - Head Protection',
        'bbox': (100, 150, 400, 500)
    }
    
    print("\n📋 Sample Violation Details:")
    print(f"   Type: {sample_violation['description']}")
    print(f"   Confidence: {sample_violation['confidence']*100:.1f}%")
    print(f"   OSHA Regulation: {sample_violation['osha_regulation']}")
    print(f"   Timestamp: {sample_violation['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Generate AI report
    print("\n🤖 Generating AI incident report...")
    try:
        agent = ComplianceAgent()
        report_text = agent.generate_incident_report(sample_violation)
        print("✅ AI report generated successfully!")
        print(f"   Report length: {len(report_text)} characters")
        
        # Save report as text file
        text_filename = f"reports/demo_report_{sample_violation['timestamp'].strftime('%Y%m%d_%H%M%S')}.txt"
        with open(text_filename, 'w') as f:
            f.write(report_text)
        print(f"   Text report saved: {text_filename}")
        
        # Generate PDF (without image since this is a demo)
        print("\n📄 Generating PDF report...")
        pdf_gen = PDFGenerator()
        
        # Create a dummy image path (will skip if doesn't exist)
        dummy_image = "violations/demo_image.jpg"
        
        pdf_path = pdf_gen.generate_pdf(sample_violation, report_text, dummy_image)
        print(f"✅ PDF report generated: {pdf_path}")
        
        print("\n" + "="*80)
        print("Demo Report Generated Successfully!")
        print("="*80)
        print(f"\nCheck these files:")
        print(f"  📄 Text: {text_filename}")
        print(f"  📄 PDF:  {pdf_path}")
        print("\nYou can open the PDF to see the professional format!")
        print("="*80)
        
        return pdf_path
        
    except Exception as e:
        print(f"❌ Error generating report: {e}")
        print("\nMake sure you have:")
        print("  1. Created .env file with OPENAI_API_KEY")
        print("  2. Run: python setup.py")
        return None

if __name__ == "__main__":
    generate_demo_report()
