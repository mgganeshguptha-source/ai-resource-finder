"""
CV processing service - extracts skills, experience, and evidence from CVs
"""

import json
from typing import Dict, Any, List, Optional
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.bedrock_client import BedrockClient
from models.candidate import CandidateProfile, SkillExtraction
from config import Config


class CVProcessor:
    """Process CVs to extract structured information"""
    
    def __init__(self, bedrock_client: Optional[BedrockClient] = None, config: Optional[Config] = None):
        """
        Initialize CV processor
        
        Args:
            bedrock_client: Bedrock client instance
            config: Configuration instance
        """
        self.config = config or Config()
        self.bedrock_client = bedrock_client or BedrockClient(
            region_name=self.config.aws_region,
            model_id=self.config.bedrock_model_id
        )
    
    def extract_cv_info(self, cv_text: str) -> Dict[str, Any]:
        """
        Extract skills, experience, and evidence from CV text
        
        Args:
            cv_text: Raw CV text content
            
        Returns:
            Dictionary with extracted_skills, years_of_experience, domain_tags
        """
        prompt = f"""Extract the following information from this CV/resume:

CV Text:
{cv_text[:8000]}  # Limit to avoid token limits

Please extract and return a JSON object with the following structure:
{{
    "extracted_skills": {{
        "SkillName1": {{
            "proficiency": "beginner|intermediate|advanced|expert",
            "years": <number of years>,
            "evidence": "<specific evidence from CV>",
            "domain": "<domain/category>"
        }},
        "SkillName2": {{ ... }}
    }},
    "years_of_experience": {{
        "SkillName1": <years>,
        "SkillName2": <years>
    }},
    "domain_tags": ["Domain1", "Domain2", ...]
}}

Guidelines:
- Extract all technical skills, tools, technologies mentioned
- Estimate years of experience for each skill based on job history
- Provide specific evidence snippets from the CV
- Assign proficiency levels based on years and context
- Identify domain tags (e.g., "Cloud Computing", "Data Science", "Web Development")
- Return ONLY valid JSON, no additional text

Return the JSON object:"""

        try:
            result = self.bedrock_client.invoke_model_json(prompt, max_tokens=4096)
            
            # Validate and clean the result
            extracted_skills = result.get("extracted_skills", {})
            years_of_experience = result.get("years_of_experience", {})
            domain_tags = result.get("domain_tags", [])
            
            # Ensure domain_tags is a list
            if not isinstance(domain_tags, list):
                domain_tags = [domain_tags] if domain_tags else []
            
            return {
                "extracted_skills": extracted_skills,
                "years_of_experience": years_of_experience,
                "domain_tags": domain_tags
            }
        except Exception as e:
            print(f"⚠️ Error extracting CV info: {str(e)}")
            # Return empty structure on error
            return {
                "extracted_skills": {},
                "years_of_experience": {},
                "domain_tags": []
            }
    
    def extract_experience_summary(self, cv_text: str) -> str:
        """
        Extract a compact experience summary highlighting key projects and relevant experience
        
        Args:
            cv_text: Raw CV text content
            
        Returns:
            Compact summary string (1-3 paragraphs or bullet points)
        """
        prompt = f"""Extract a compact, focused experience summary from this CV/resume:

CV Text:
{cv_text[:8000]}  # Limit to avoid token limits

Create a concise experience summary (1-3 short paragraphs or 3-5 bullet points) that highlights:
- Key projects and their outcomes
- Client names and industries (if mentioned)
- Technical achievements and implementations
- Domain-specific experience (e.g., lifescience, finance, cloud migration)
- Scale and impact (e.g., "migrated 5TB database", "served 1M users")

Focus on concrete, specific examples that demonstrate real-world experience.
Keep it concise but informative - aim for 150-300 words total.

Return ONLY the summary text, no additional formatting or labels:"""

        try:
            result = self.bedrock_client.invoke_model(prompt, max_tokens=512)
            # invoke_model returns a string directly
            summary = result.strip() if result else ""
            
            # Clean up the summary - remove any markdown code blocks if present
            if summary.startswith("```"):
                # Extract text from code block
                lines = summary.split("\n")
                summary = "\n".join([line for line in lines if not line.strip().startswith("```")])
            
            return summary
        except Exception as e:
            print(f"⚠️ Error extracting experience summary: {str(e)}")
            return ""
    
    def process_cv(self, cv_text: str, name: str, email: str, 
                   cv_s3_key: Optional[str] = None, 
                   cv_s3_url: Optional[str] = None) -> CandidateProfile:
        """
        Process a complete CV and return CandidateProfile
        
        Args:
            cv_text: Raw CV text
            name: Candidate name
            email: Candidate email
            cv_s3_key: S3 key for CV file
            cv_s3_url: S3 URL for CV file
            
        Returns:
            CandidateProfile object
        """
        extracted_info = self.extract_cv_info(cv_text)
        experience_summary = self.extract_experience_summary(cv_text)
        
        return CandidateProfile(
            name=name,
            email=email,
            raw_text=cv_text,
            extracted_skills=extracted_info["extracted_skills"],
            years_of_experience=extracted_info["years_of_experience"],
            domain_tags=extracted_info["domain_tags"],
            experience_summary=experience_summary,
            cv_s3_key=cv_s3_key,
            cv_s3_url=cv_s3_url
        )


