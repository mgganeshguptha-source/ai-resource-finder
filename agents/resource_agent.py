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
        print(f"🔍 DEBUG: ResourceAgent.find_candidates called with top_n={top_n}")
        candidates = self.matching_engine.match_candidates(
            requirement_text,
            parsed_requirement,
            top_n
        )
        print(f"🔍 DEBUG: MatchingEngine returned {len(candidates)} candidates")
        
        # Enhance with additional analysis
        for candidate in candidates:
            print(f"🔍 DEBUG: Candidate: {candidate.get('name', 'Unknown')} - {candidate.get('match_percentage', 0)}%")
            # Add domain gap analysis
            domain_gap = GapAnalyzer.analyze_domain_gap(
                CandidateProfile(**candidate),
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


