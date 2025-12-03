"""
Orchestrator Agent - Coordinates the complete workflow
"""

import sys
import os

# Add project root to Python path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from typing import Dict, Any, List
from utils.database import DatabaseManager
from utils.bedrock_client import BedrockClient
from services.requirement_parser import RequirementParser
from agents.resource_agent import ResourceAgent
from agents.course_agent import CourseAgent
from config import Config


class orchestrator:
    """Main orchestrator agent that coordinates the workflow"""
    
    def __init__(self, db_manager: DatabaseManager, bedrock_client: BedrockClient, config: Config):
        """
        Initialize orchestrator
        
        Args:
            db_manager: Database manager instance
            bedrock_client: Bedrock client instance
            config: Configuration instance
        """
        self.db_manager = db_manager
        self.bedrock_client = bedrock_client
        self.config = config
        
        # Initialize sub-agents
        self.requirement_parser = RequirementParser(bedrock_client, config)
        self.resource_agent = ResourceAgent(db_manager, bedrock_client, config)
        self.course_agent = CourseAgent(db_manager, bedrock_client, config)
    
    def process_requirement(self, requirement_text: str, user_metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Process a resource requirement and return complete result bundle
        
        Args:
            requirement_text: Requirement text from user
            user_metadata: Optional user metadata
            
        Returns:
            Result bundle with parsed requirement, top candidates, and course recommendations
        """
        # Step 1: Parse requirement
        parsed_requirement = self.requirement_parser.parse(requirement_text)
        
        # Step 2: Find top candidates using ResourceAgent
        # Get more candidates initially to see what scores we're getting
        candidates = self.resource_agent.find_candidates(
            requirement_text,
            parsed_requirement,
            top_n=10  # Get more candidates to see scores before filtering
        )
        
        # Step 2.5: Filter candidates by minimum match percentage BEFORE recommending courses
        # This avoids wasting time recommending courses for candidates that won't be displayed
        min_match = self.config.min_match_percentage
        candidates_before_filter = len(candidates)
        
        # Debug logging before filtering
        if candidates_before_filter > 0:
            match_scores = [c.get("match_percentage", 0) for c in candidates]
            print(f"ℹ️ Found {candidates_before_filter} candidates with match scores: {match_scores[:5]}")
        
        candidates = [c for c in candidates if c.get("match_percentage", 0) > min_match]
        candidates_after_filter = len(candidates)
        
        # Debug logging after filtering
        if candidates_before_filter > 0 and candidates_after_filter == 0:
            print(f"⚠️ Warning: {candidates_before_filter} candidates found but all filtered out by min_match_percentage={min_match}%")
            print(f"   Consider lowering MIN_MATCH_PERCENTAGE or VECTOR_SEARCH_THRESHOLD")
        elif candidates_after_filter < candidates_before_filter:
            print(f"ℹ️ Filtered {candidates_before_filter - candidates_after_filter} candidates below {min_match}% threshold")
        
        # Limit to final_top_candidates after filtering
        candidates = candidates[:self.config.final_top_candidates]
        
        # Step 3: Get course recommendations ONLY for candidates that will be displayed
        for candidate in candidates:
            gaps = candidate.get("gaps", [])
            if gaps:
                try:
                    course_recommendations = self.course_agent.recommend_courses(
                        gaps,
                        candidate
                    )
                    candidate["recommended_courses"] = [
                        {
                            "title": rec.course.title,
                            "description": rec.course.description,
                            "level": rec.course.level,
                            "url": rec.course.url or "",
                            "score": rec.score,
                            "rationale": rec.rationale,
                            "gaps_addressed": rec.gaps_addressed
                        }
                        for rec in course_recommendations
                    ]
                    print(f"✅ Recommended {len(course_recommendations)} courses for {candidate.get('name', 'Unknown')}")
                except Exception as e:
                    print(f"⚠️ Error recommending courses for {candidate.get('name', 'Unknown')}: {str(e)}")
                    candidate["recommended_courses"] = []
            else:
                # Even if no gaps, try to recommend general courses based on candidate skills
                try:
                    # Create a general gap query based on candidate's existing skills
                    candidate_skills = list(candidate.get("extracted_skills", {}).keys())[:5]
                    if candidate_skills:
                        general_gaps = [{"skill": skill, "gap_type": "enhancement", "severity": "low"} for skill in candidate_skills]
                        course_recommendations = self.course_agent.recommend_courses(
                            general_gaps,
                            candidate
                        )
                        candidate["recommended_courses"] = [
                            {
                                "title": rec.course.title,
                                "description": rec.course.description,
                                "level": rec.course.level,
                                "url": rec.course.url or "",
                                "score": rec.score,
                                "rationale": rec.rationale,
                                "gaps_addressed": rec.gaps_addressed
                            }
                            for rec in course_recommendations[:min(2, self.config.final_top_courses)]  # Limit to max 2 courses
                        ]
                        print(f"✅ Recommended {len(candidate['recommended_courses'])} general courses for {candidate.get('name', 'Unknown')}")
                    else:
                        candidate["recommended_courses"] = []
                except Exception as e:
                    print(f"⚠️ Error recommending general courses for {candidate.get('name', 'Unknown')}: {str(e)}")
                    candidate["recommended_courses"] = []
        
        # Step 4: Build result bundle
        result_bundle = {
            "requirement_text": requirement_text,
            "parsed_requirement": parsed_requirement,
            "candidates": candidates,
            "user_metadata": user_metadata or {},
            "timestamp": None  # Will be set by caller if needed
        }
        
        return result_bundle


