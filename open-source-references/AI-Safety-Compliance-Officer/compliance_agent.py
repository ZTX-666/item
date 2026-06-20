from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from datetime import datetime
import config

class ComplianceAgent:
    """AI Agent for generating OSHA-compliant incident reports"""
    
    def __init__(self):
        """Initialize the LangChain agent with OpenAI"""
        if not config.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not found. Please set it in .env file")
        
        # Initialize LLM with LangSmith metadata
        self.llm = ChatOpenAI(
            model=config.OPENAI_MODEL,
            temperature=0.3,  # Lower temperature for more consistent, formal output
            openai_api_key=config.OPENAI_API_KEY,
            model_kwargs={
                "metadata": {
                    "application": "AI Safety Compliance Officer",
                    "version": "1.0",
                    "agent_type": "compliance_report_generator"
                }
            }
        )
        
        # Track usage statistics
        self.total_reports = 0
        self.total_tokens = 0
        
        # Create prompt template
        self.prompt_template = PromptTemplate(
            input_variables=[
                "date", "time", "location", "site_name", "company_name",
                "violation_type", "violation_description", "confidence",
                "osha_regulation"
            ],
            template="""
You are a professional safety compliance officer writing an official OSHA incident report.

Generate a formal, detailed safety incident report based on the following information:

Date: {date}
Time: {time}
Location: {location}
Site: {site_name}
Company: {company_name}

VIOLATION DETECTED:
Type: {violation_type}
Description: {violation_description}
Detection Confidence: {confidence}%
OSHA Regulation: {osha_regulation}

Write a comprehensive incident report that includes:
1. A formal incident description in professional language
2. Reference to the specific OSHA regulation violated
3. Potential safety hazards and risks
4. Recommended corrective actions (minimum 3-4 actions)
5. Follow-up requirements

The report should be suitable for official safety records and OSHA compliance documentation.
Use formal, professional language throughout. Be specific and actionable.

Format the report with clear sections and professional formatting.
"""
        )
    
    def generate_incident_report(self, violation):
        """
        Generate a formal incident report using AI
        
        Args:
            violation: Dictionary containing violation details
            
        Returns:
            String containing the formatted incident report
        """
        # Prepare input data
        timestamp = violation['timestamp']
        
        input_data = {
            "date": timestamp.strftime("%B %d, %Y"),
            "time": timestamp.strftime("%H:%M:%S"),
            "location": config.SITE_LOCATION,
            "site_name": config.SITE_NAME,
            "company_name": config.COMPANY_NAME,
            "violation_type": violation['class_name'].replace('_', ' ').title(),
            "violation_description": violation['description'],
            "confidence": f"{violation['confidence'] * 100:.1f}",
            "osha_regulation": violation['osha_regulation']
        }
        
        print("Generating incident report with AI...")
        
        try:
            # Generate report using LLM with new API and LangSmith tracing
            prompt = self.prompt_template.format(**input_data)
            
            # Add LangSmith metadata for this specific run
            response = self.llm.invoke(
                prompt,
                config={
                    "metadata": {
                        "violation_type": violation['class_name'],
                        "confidence": violation['confidence'],
                        "osha_regulation": violation['osha_regulation'],
                        "site": config.SITE_NAME,
                        "timestamp": timestamp.isoformat()
                    },
                    "tags": ["safety-report", "osha-compliance", violation['class_name']]
                }
            )
            report = response.content if hasattr(response, 'content') else str(response)
            
            # Track usage
            self.total_reports += 1
            if hasattr(response, 'response_metadata'):
                token_usage = response.response_metadata.get('token_usage', {})
                self.total_tokens += token_usage.get('total_tokens', 0)
            
            # Add header and footer
            formatted_report = self._format_report(report, violation)
            
            return formatted_report
            
        except Exception as e:
            print(f"Error generating report: {e}")
            # Fallback to basic report if AI fails
            return self._generate_fallback_report(violation)
    
    def _format_report(self, ai_report, violation):
        """Add professional formatting to the AI-generated report"""
        timestamp = violation['timestamp']
        
        header = f"""
{'='*80}
AUTOMATED SAFETY INCIDENT REPORT
{'='*80}

Report ID: {timestamp.strftime('%Y%m%d-%H%M%S')}
Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}
System: AI Safety Compliance Officer v1.0

{'='*80}
"""
        
        footer = f"""
{'='*80}
VIOLATION EVIDENCE

Detection Method: Automated CCTV Monitoring with AI
Detection Confidence: {violation['confidence']*100:.1f}%
Image Evidence: Attached (see violation screenshot)

{'='*80}

This report was automatically generated by the AI Safety Compliance System.
A human safety officer should review and verify the incident details.

For questions regarding this report, contact: {config.EMAIL_SENDER}
{'='*80}
"""
        
        return header + ai_report + footer
    
    def _generate_fallback_report(self, violation):
        """Generate a basic report if AI is unavailable"""
        timestamp = violation['timestamp']
        
        report = f"""
{'='*80}
SAFETY INCIDENT REPORT (BASIC MODE)
{'='*80}

Report ID: {timestamp.strftime('%Y%m%d-%H%M%S')}
Date: {timestamp.strftime('%B %d, %Y')}
Time: {timestamp.strftime('%H:%M:%S')}
Location: {config.SITE_LOCATION}
Site: {config.SITE_NAME}

INCIDENT DESCRIPTION:
At {timestamp.strftime('%I:%M %p')}, automated surveillance detected a safety violation.
A worker was observed {violation['description'].lower()} in the construction area.

OSHA REGULATION VIOLATED:
{violation['osha_regulation']}

DETECTION DETAILS:
Confidence Level: {violation['confidence']*100:.1f}%
Detection Method: Automated AI Vision System

RECOMMENDED ACTIONS:
1. Immediate notification to site supervisor
2. Safety briefing for affected worker
3. Review of PPE compliance procedures
4. Additional monitoring of the area

This is an automated basic report. AI report generation was unavailable.
{'='*80}
"""
        return report
    
    def generate_email_body(self, violation, report_path):
        """
        Generate email body for notification
        
        Args:
            violation: Violation dictionary
            report_path: Path to PDF report
            
        Returns:
            Email body string
        """
        timestamp = violation['timestamp']
        
        email_body = f"""
URGENT: Safety Violation Detected

A safety compliance violation has been detected at {config.SITE_NAME}.

VIOLATION SUMMARY:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Date/Time: {timestamp.strftime('%B %d, %Y at %I:%M %p')}
Location: {config.SITE_LOCATION}
Violation: {violation['description']}
Confidence: {violation['confidence']*100:.1f}%
OSHA Regulation: {violation['osha_regulation']}

IMMEDIATE ACTION REQUIRED:
This violation requires immediate attention to ensure worker safety and OSHA compliance.

A detailed incident report has been generated and is attached to this email as a PDF.

Please review the report and take appropriate corrective actions.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This is an automated notification from the AI Safety Compliance Officer system.
For technical support or questions, please contact: {config.EMAIL_SENDER}

Report ID: {timestamp.strftime('%Y%m%d-%H%M%S')}
Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}
"""
        return email_body
    
    def get_usage_stats(self):
        """
        Get AI agent usage statistics
        
        Returns:
            Dictionary with usage metrics
        """
        return {
            'total_reports': self.total_reports,
            'total_tokens': self.total_tokens,
            'avg_tokens_per_report': self.total_tokens / self.total_reports if self.total_reports > 0 else 0,
            'langsmith_enabled': config.LANGCHAIN_TRACING_V2
        }
