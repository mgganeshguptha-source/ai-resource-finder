"""
Requirement parsing service - converts requirement text to structured JSON
"""

import json
from typing import Dict, Any, Optional
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.bedrock_client import BedrockClient
from config import Config


class RequirementParser:
    """Parse resource requirements into structured format"""
    
    def __init__(self, bedrock_client: Optional[BedrockClient] = None, config: Optional[Config] = None):
        """
        Initialize requirement parser
        
        Args:
            bedrock_client: Bedrock client instance
            config: Configuration instance
        """
        self.config = config or Config()
        self.bedrock_client = bedrock_client or BedrockClient(
            region_name=self.config.aws_region,
            model_id=self.config.bedrock_model_id
        )
    
    def parse(self, requirement_text: str) -> Dict[str, Any]:
        """
        Parse requirement text into structured format
        
        Args:
            requirement_text: Raw requirement text
            
        Returns:
            Dictionary with required_skills, preferred_skills, domain, min_years_per_skill, seniority, exclusions
        """
        prompt = f"""Parse the following resource requirement into structured JSON:

Requirement Text:
{requirement_text}

Please extract and return a JSON object with the following structure:
{{
    "required_skills": ["Skill1", "Skill2", ...],
    "preferred_skills": ["Skill1", "Skill2", ...],
    "domain": "<domain/category>",
    "customer_name": "<customer/client name if mentioned>",
    "min_years_per_skill": {{
        "Skill1": <minimum years>,
        "Skill2": <minimum years>
    }},
    "seniority": "<junior|mid|senior|lead|architect>",
    "exclusions": ["Skill1", "Skill2", ...]
}}

Guidelines:
- Identify must-have skills (required_skills)
- Identify nice-to-have skills (preferred_skills)
- Extract domain/category ONLY if explicitly mentioned (e.g., "Cloud Computing", "Data Science")
- Extract customer/client name if mentioned in the requirement
- Extract minimum years of experience per skill ONLY if explicitly mentioned in the requirement
- Extract seniority level ONLY if explicitly mentioned (junior|mid|senior|lead|architect)
- Note any skills/technologies to exclude
- If domain, experience, or seniority are NOT mentioned, set them to null or empty string
- Return ONLY valid JSON, no additional text

Return the JSON object:"""

        try:
            result = self.bedrock_client.invoke_model_json(prompt, max_tokens=2048)
            
            # Extract customer name
            customer_name = result.get("customer_name", "")
            
            # Get domain from result
            domain = result.get("domain", "")
            
            # If domain is not mentioned but customer name is, identify domain from customer name
            if not domain and customer_name:
                domain = self._identify_domain_from_customer(customer_name)
            
            # Validate and set values (skip defaults for experience and seniority if not mentioned)
            parsed = {
                "required_skills": result.get("required_skills", []),
                "preferred_skills": result.get("preferred_skills", []),
                "domain": domain,
                "min_years_per_skill": result.get("min_years_per_skill", {}),
                "seniority": result.get("seniority", ""),  # Empty string if not mentioned
                "exclusions": result.get("exclusions", [])
            }
            
            # Remove empty min_years_per_skill if not mentioned
            if not parsed["min_years_per_skill"] or parsed["min_years_per_skill"] == {}:
                parsed["min_years_per_skill"] = {}
            
            # Ensure lists are lists
            if not isinstance(parsed["required_skills"], list):
                parsed["required_skills"] = [parsed["required_skills"]] if parsed["required_skills"] else []
            if not isinstance(parsed["preferred_skills"], list):
                parsed["preferred_skills"] = [parsed["preferred_skills"]] if parsed["preferred_skills"] else []
            if not isinstance(parsed["exclusions"], list):
                parsed["exclusions"] = [parsed["exclusions"]] if parsed["exclusions"] else []
            
            return parsed
        except Exception as e:
            print(f"⚠️ Error parsing requirement: {str(e)}")
            # Return default structure on error
            return {
                "required_skills": [],
                "preferred_skills": [],
                "domain": "",
                "min_years_per_skill": {},
                "seniority": "",
                "exclusions": []
            }
    
    def _identify_domain_from_customer(self, customer_name: str) -> str:
        """
        Identify domain from customer name using LLM
        
        Args:
            customer_name: Name of the customer/client
            
        Returns:
            Domain/category identified from customer name
        """
        prompt = f"""Based on the customer/client name, identify the most likely business domain or industry category.

Customer/Client Name: {customer_name}

Please identify the domain/category this customer typically operates in. Examples:
- "Cloud Computing" for AWS, Azure, GCP
- "Banking" for financial institutions
- "Healthcare" for medical/health companies
- "Retail" for e-commerce/retail companies
- "Manufacturing" for industrial companies
- "Telecommunications" for telecom companies
- "Data Science" for analytics/data companies

Return ONLY a JSON object with this structure:
{{
    "domain": "<identified domain/category>"
}}

If you cannot determine the domain, return an empty string for domain.

Return ONLY valid JSON, no additional text:"""

        try:
            result = self.bedrock_client.invoke_model_json(prompt, max_tokens=512)
            domain = result.get("domain", "")
            return domain if domain else ""
        except Exception as e:
            print(f"⚠️ Error identifying domain from customer name: {str(e)}")
            return ""


