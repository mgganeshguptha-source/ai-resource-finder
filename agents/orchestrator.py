"""
Orchestrator Agent - Coordinates the complete workflow
"""

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
        print(f"🔍 DEBUG: Finding candidates for requirement...")
        candidates = self.resource_agent.find_candidates(
            requirement_text,
            parsed_requirement,
            self.config.final_top_candidates
        )
        print(f"🔍 DEBUG: Found {len(candidates)} candidates from ResourceAgent")
        
        # Step 3: Get course recommendations for each candidate's gaps
        for candidate in candidates:
            gaps = candidate.get("gaps", [])
            if gaps:
                course_recommendations = self.course_agent.recommend_courses(
                    gaps,
                    candidate
                )
                if course_recommendations:
                    candidate["recommended_courses"] = [
                        {
                            "title": rec.course.title,
                            "description": rec.course.description,
                            "level": rec.course.level,
                            "score": rec.score,
                            "rationale": rec.rationale,
                            "gaps_addressed": rec.gaps_addressed
                        }
                        for rec in course_recommendations
                    ]
                else:
                    # If no courses recommended but gaps exist, create a generic recommendation
                    gap_skills = [gap.get("skill", "") for gap in gaps[:2]]
                    candidate["recommended_courses"] = [
                        {
                            "title": f"Training for {', '.join(gap_skills) if gap_skills else 'Skill Development'}",
                            "description": f"Recommended training to address gaps in {', '.join(gap_skills) if gap_skills else 'required skills'}. Please check available training courses in the learning management system.",
                            "level": "intermediate",
                            "score": 0.5,
                            "rationale": f"This training will help address the skill gaps in {', '.join(gap_skills) if gap_skills else 'the required areas'}.",
                            "gaps_addressed": gap_skills
                        }
                    ]
            else:
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


