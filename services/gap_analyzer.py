"""
Skill gap analysis service
"""

from typing import Dict, Any, List
from models.candidate import CandidateProfile
from typing import Optional


class GapAnalyzer:
    """Analyze skill gaps for candidates"""
    
    @staticmethod
    def analyze_gaps(candidate: CandidateProfile, required_skills: List[str], 
                     min_years_per_skill: Dict[str, float]) -> List[Dict[str, Any]]:
        """
        Analyze skill gaps for a candidate
        
        Args:
            candidate: Candidate profile
            required_skills: List of required skills
            min_years_per_skill: Minimum years required per skill
            
        Returns:
            List of gap dictionaries with skill, gap_type, severity
        """
        gaps = []
        candidate_skills = candidate.extracted_skills
        candidate_years = candidate.years_of_experience
        
        for skill in required_skills:
            gap_info = {
                "skill": skill,
                "gap_type": None,
                "severity": None
            }
            
            # Check if skill is missing
            if skill not in candidate_skills:
                gap_info["gap_type"] = "missing"
                gap_info["severity"] = "high"
                gaps.append(gap_info)
                continue
            
            # Check proficiency level
            skill_data = candidate_skills.get(skill, {})
            proficiency = skill_data.get("proficiency", "").lower()
            
            # Map proficiency to score
            proficiency_scores = {
                "expert": 1.0,
                "advanced": 0.75,
                "intermediate": 0.5,
                "beginner": 0.25
            }
            proficiency_score = proficiency_scores.get(proficiency, 0.0)
            
            # Check if proficiency is insufficient
            if proficiency_score < 0.5:
                gap_info["gap_type"] = "insufficient"
                gap_info["severity"] = "high" if proficiency_score < 0.25 else "medium"
                gaps.append(gap_info)
                continue
            
            # Check years of experience
            if skill in min_years_per_skill:
                required_years = min_years_per_skill[skill]
                candidate_years_for_skill = candidate_years.get(skill, 0.0)
                
                if candidate_years_for_skill < required_years:
                    gap_info["gap_type"] = "insufficient_experience"
                    gap_info["severity"] = "high" if (required_years - candidate_years_for_skill) > 2 else "medium"
                    gap_info["required_years"] = required_years
                    gap_info["candidate_years"] = candidate_years_for_skill
                    gaps.append(gap_info)
                    continue
        
        return gaps
    
    @staticmethod
    def analyze_domain_gap(candidate: CandidateProfile, required_domain: str) -> Optional[Dict[str, Any]]:
        """
        Analyze domain gap
        
        Args:
            candidate: Candidate profile
            required_domain: Required domain/category
            
        Returns:
            Gap dictionary if domain mismatch, None otherwise
        """
        if not required_domain:
            return None
        
        candidate_domains = [d.lower() for d in (candidate.domain_tags or [])]
        required_domain_lower = required_domain.lower()
        
        # Check if candidate has matching domain
        if not any(required_domain_lower in domain or domain in required_domain_lower 
                   for domain in candidate_domains):
            return {
                "skill": required_domain,
                "gap_type": "domain",
                "severity": "medium"
            }
        
        return None


