"""
Requirement parsing service - converts requirement text to structured JSON
"""

import json
from typing import Dict, Any, Optional
import sys
import os

# Add project root to Python path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

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
- Extract domain/category (e.g., "Cloud Computing", "Data Science")
- Estimate minimum years of experience per skill if mentioned
- Determine seniority level from context
- Note any skills/technologies to exclude
- Return ONLY valid JSON, no additional text

Return the JSON object:"""

        try:
            result = self.bedrock_client.invoke_model_json(prompt, max_tokens=2048)
            
            # Validate and set defaults
            parsed = {
                "required_skills": result.get("required_skills", []),
                "preferred_skills": result.get("preferred_skills", []),
                "domain": result.get("domain", ""),
                "min_years_per_skill": result.get("min_years_per_skill", {}),
                "seniority": result.get("seniority", "mid"),
                "exclusions": result.get("exclusions", [])
            }
            
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
                "seniority": "mid",
                "exclusions": []
            }


