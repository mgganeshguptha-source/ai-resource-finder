"""
ResourceAgent - Finds and ranks associates for resource requirements
"""

from typing import List, Dict, Any
from utils.database import DatabaseManager
from utils.bedrock_client import BedrockClient
from services.matching_engine import MatchingEngine
from services.gap_analyzer import GapAnalyzer
from models.candidate import CandidateProfile
from config import Config


class ResourceAgent:
    """Finds and ranks candidates for resource requirements"""
    
    def __init__(self, db_manager: DatabaseManager, bedrock_client: BedrockClient, config: Config):
        """
        Initialize ResourceAgent
        
        Args:
            db_manager: Database manager instance
            bedrock_client: Bedrock client instance
            config: Configuration instance
        """
        self.db_manager = db_manager
        self.bedrock_client = bedrock_client
        self.config = config
        self.matching_engine = MatchingEngine(db_manager, bedrock_client, config)
    
    def find_candidates(self, requirement_text: str, parsed_requirement: Dict[str, Any],
                       top_n: int = 3) -> List[Dict[str, Any]]:
        """
        Find and rank top candidates for a requirement
        
        Args:
            requirement_text: Requirement text
            parsed_requirement: Parsed requirement structure
            top_n: Number of top candidates to return
            
        Returns:
            List of top candidates with match scores, skills, gaps, and evidence
        """
        # Use matching engine to find candidates
        candidates = self.matching_engine.match_candidates(
            requirement_text,
            parsed_requirement,
            top_n
        )
        
        # Enhance with additional analysis
        for candidate in candidates:
            # Add domain gap analysis - filter candidate dict to only include CandidateProfile fields
            # and provide defaults for missing fields
            profile_fields = {
                "name", "email", "raw_text", "extracted_skills", "years_of_experience",
                "domain_tags", "embedding", "cv_s3_key", "cv_s3_url", "id",
                "created_at", "updated_at"
            }
            profile_data = {k: v for k, v in candidate.items() if k in profile_fields}
            
            # Ensure required fields have defaults if missing (vector search doesn't return all fields)
            if "raw_text" not in profile_data or not profile_data.get("raw_text"):
                profile_data["raw_text"] = ""  # Default empty string for raw_text
            if "extracted_skills" not in profile_data:
                profile_data["extracted_skills"] = {}
            if "years_of_experience" not in profile_data:
                profile_data["years_of_experience"] = {}
            if "domain_tags" not in profile_data:
                profile_data["domain_tags"] = []
            
            domain_gap = GapAnalyzer.analyze_domain_gap(
                CandidateProfile(**profile_data),
                parsed_requirement.get("domain", "")
            )
            if domain_gap:
                candidate["gaps"].append(domain_gap)
            
            # Format match percentage with threshold classification
            match_pct = candidate.get("match_percentage", 0)
            if match_pct >= self.config.match_threshold_strong * 100:
                candidate["match_quality"] = "strong"
            elif match_pct >= self.config.match_threshold_moderate * 100:
                candidate["match_quality"] = "moderate"
            else:
                candidate["match_quality"] = "weak"
        
        return candidates


