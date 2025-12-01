"""
AWS SES email service for allocation notifications
"""

import boto3
from typing import Dict, Any, List, Optional
from botocore.exceptions import ClientError
from config import Config


class EmailService:
    """Send emails via AWS SES"""
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize email service
        
        Args:
            config: Configuration instance
        """
        self.config = config or Config()
        self.ses_client = boto3.client(
            'ses',
            region_name=self.ses_region
        )
    
    @property
    def ses_region(self) -> str:
        """Get SES region"""
        return self.config.ses_region
    
    def send_allocation_email_to_admin(self, allocation_request: Dict[str, Any], 
                                       candidate: Dict[str, Any]) -> bool:
        """
        Send allocation request email to admin (Ganesh)
        
        Args:
            allocation_request: Allocation request details
            candidate: Candidate profile
            
        Returns:
            True if email sent successfully
        """
        user_details = allocation_request.get("user_details", {})
        
        subject = f"New Resource Allocation Request - {user_details.get('emp_name', 'Unknown')}"
        
        body_text = f"""
New Resource Allocation Request

Candidate Details:
- Name: {candidate.get('name', 'Unknown')}
- Email: {candidate.get('email', 'Unknown')}
- Match Score: {allocation_request.get('match_score', 0)}%

Allocation Details:
- Employee Code: {user_details.get('emp_code', 'N/A')}
- Employee Name: {user_details.get('emp_name', 'N/A')}
- Client Name: {user_details.get('client_name', 'N/A')}
- Project Name: {user_details.get('project_name', 'N/A')}
- Project ID: {user_details.get('project_id', 'N/A')}
- SOW/CR ID: {user_details.get('sow_cr_id', 'N/A')}
- Role: {user_details.get('role', 'N/A')}
- Rate: ${user_details.get('rate', 0)}
- Allocation Category: {user_details.get('allocation_category', 'N/A')}
- Allocation %: {user_details.get('allocation_percentage', 0)}%
- Start Date: {user_details.get('start_date', 'N/A')}
- End Date: {user_details.get('end_date', 'N/A')}
- RR ID: {user_details.get('rr_id', 'N/A')}

Requirement:
{allocation_request.get('requirement_text', 'N/A')}

Please review and approve this allocation request.
"""
        
        body_html = f"""
<html>
<head></head>
<body>
  <h2>New Resource Allocation Request</h2>
  
  <h3>Candidate Details</h3>
  <ul>
    <li><strong>Name:</strong> {candidate.get('name', 'Unknown')}</li>
    <li><strong>Email:</strong> {candidate.get('email', 'Unknown')}</li>
    <li><strong>Match Score:</strong> {allocation_request.get('match_score', 0)}%</li>
  </ul>
  
  <h3>Allocation Details</h3>
  <table border="1" cellpadding="5" cellspacing="0">
    <tr><td><strong>Employee Code</strong></td><td>{user_details.get('emp_code', 'N/A')}</td></tr>
    <tr><td><strong>Employee Name</strong></td><td>{user_details.get('emp_name', 'N/A')}</td></tr>
    <tr><td><strong>Client Name</strong></td><td>{user_details.get('client_name', 'N/A')}</td></tr>
    <tr><td><strong>Project Name</strong></td><td>{user_details.get('project_name', 'N/A')}</td></tr>
    <tr><td><strong>Project ID</strong></td><td>{user_details.get('project_id', 'N/A')}</td></tr>
    <tr><td><strong>SOW/CR ID</strong></td><td>{user_details.get('sow_cr_id', 'N/A')}</td></tr>
    <tr><td><strong>Role</strong></td><td>{user_details.get('role', 'N/A')}</td></tr>
    <tr><td><strong>Rate</strong></td><td>${user_details.get('rate', 0)}</td></tr>
    <tr><td><strong>Allocation Category</strong></td><td>{user_details.get('allocation_category', 'N/A')}</td></tr>
    <tr><td><strong>Allocation %</strong></td><td>{user_details.get('allocation_percentage', 0)}%</td></tr>
    <tr><td><strong>Start Date</strong></td><td>{user_details.get('start_date', 'N/A')}</td></tr>
    <tr><td><strong>End Date</strong></td><td>{user_details.get('end_date', 'N/A')}</td></tr>
    <tr><td><strong>RR ID</strong></td><td>{user_details.get('rr_id', 'N/A')}</td></tr>
  </table>
  
  <h3>Requirement</h3>
  <p>{allocation_request.get('requirement_text', 'N/A')}</p>
  
  <p>Please review and approve this allocation request.</p>
</body>
</html>
"""
        
        return self._send_email(
            to_email=self.config.ses_admin_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html
        )
    
    def send_training_email_to_associate(self, candidate_email: str, candidate_name: str,
                                        recommended_courses: List[Dict[str, Any]]) -> bool:
        """
        Send training recommendations email to associate
        
        Args:
            candidate_email: Candidate email address
            candidate_name: Candidate name
            recommended_courses: List of recommended courses
            
        Returns:
            True if email sent successfully
        """
        subject = "Recommended Training Courses for Skill Development"
        
        courses_list = "\n".join([
            f"{i+1}. {course.get('title', 'Unknown Course')} ({course.get('level', 'N/A')} level)\n"
            f"   - {course.get('rationale', 'No description')}\n"
            f"   - Addresses: {', '.join(course.get('gaps_addressed', []))}"
            for i, course in enumerate(recommended_courses)
        ])
        
        body_text = f"""
Dear {candidate_name},

Based on your profile and recent resource requirements, we recommend the following training courses to enhance your skills:

{courses_list}

These courses are designed to address skill gaps and help you excel in future opportunities.

Best regards,
AI Resource Finder Team
"""
        
        courses_html = "".join([
            f"""
            <div style="margin-bottom: 20px; padding: 10px; border: 1px solid #ddd; border-radius: 5px;">
              <h4>{i+1}. {course.get('title', 'Unknown Course')} <span style="color: #666;">({course.get('level', 'N/A')} level)</span></h4>
              <p><strong>Why this course:</strong> {course.get('rationale', 'No description')}</p>
              <p><strong>Addresses:</strong> {', '.join(course.get('gaps_addressed', []))}</p>
            </div>
            """
            for i, course in enumerate(recommended_courses)
        ])
        
        body_html = f"""
<html>
<head></head>
<body>
  <h2>Recommended Training Courses</h2>
  <p>Dear {candidate_name},</p>
  <p>Based on your profile and recent resource requirements, we recommend the following training courses to enhance your skills:</p>
  
  {courses_html}
  
  <p>These courses are designed to address skill gaps and help you excel in future opportunities.</p>
  
  <p>Best regards,<br>AI Resource Finder Team</p>
</body>
</html>
"""
        
        return self._send_email(
            to_email=candidate_email,
            subject=subject,
            body_text=body_text,
            body_html=body_html
        )
    
    def _send_email(self, to_email: str, subject: str, body_text: str, body_html: str) -> bool:
        """
        Send email via SES
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            body_text: Plain text body
            body_html: HTML body
            
        Returns:
            True if email sent successfully
        """
        try:
            response = self.ses_client.send_email(
                Source=self.config.ses_from_email,
                Destination={
                    'ToAddresses': [to_email]
                },
                Message={
                    'Subject': {
                        'Data': subject,
                        'Charset': 'UTF-8'
                    },
                    'Body': {
                        'Text': {
                            'Data': body_text,
                            'Charset': 'UTF-8'
                        },
                        'Html': {
                            'Data': body_html,
                            'Charset': 'UTF-8'
                        }
                    }
                }
            )
            print(f"✅ Email sent successfully to {to_email}. MessageId: {response['MessageId']}")
            return True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            print(f"❌ Failed to send email to {to_email}: {error_code} - {error_message}")
            return False

