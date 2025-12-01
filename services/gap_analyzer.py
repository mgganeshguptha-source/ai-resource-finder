"""
Skill gap analysis service
"""

from typing import Dict, Any, List, Set
from models.candidate import CandidateProfile
from typing import Optional
from utils.skill_normalizer import SkillNormalizer


class GapAnalyzer:
    """Analyze skill gaps for candidates"""
    
    @staticmethod
    def analyze_gaps(candidate: CandidateProfile, required_skills: List[str], 
                     min_years_per_skill: Dict[str, float]) -> List[Dict[str, Any]]:
        """
        Analyze skill gaps for a candidate (with skill normalization and dependencies)
        
        Args:
            candidate: Candidate profile
            required_skills: List of required skills
            min_years_per_skill: Minimum years required per skill
            
        Returns:
            List of gap dictionaries with skill, gap_type, severity
        """
        gaps = []
        candidate_skills_dict = candidate.extracted_skills
        candidate_years = candidate.years_of_experience
        
        # Normalize candidate skills and create a set for fast lookup
        candidate_skills_normalized = {
            SkillNormalizer.normalize_skill(skill): skill 
            for skill in candidate_skills_dict.keys()
        }
        candidate_skills_set = set(candidate_skills_normalized.keys())
        
        # Also add implied skills (e.g., Spring Boot -> Java)
        implied_skills = set()
        for skill in candidate_skills_set:
            implied = SkillNormalizer.get_implied_skills(skill)
            implied_skills.update(implied)
        candidate_skills_set.update(implied_skills)
        
        for required_skill in required_skills:
            gap_info = {
                "skill": required_skill,
                "gap_type": None,
                "severity": None
            }
            
            normalized_required = SkillNormalizer.normalize_skill(required_skill)
            
            # Check if candidate has this skill (direct match, variation, or implied)
            has_skill = SkillNormalizer.has_skill_or_equivalent(
                candidate_skills_set, 
                required_skill
            )
            
            if not has_skill:
                gap_info["gap_type"] = "missing"
                gap_info["severity"] = "high"
                gaps.append(gap_info)
                continue
            
            # Find the actual skill key in candidate's skills (might be a variation)
            actual_skill_key = None
            for candidate_skill_normalized, original_skill in candidate_skills_normalized.items():
                if SkillNormalizer.skills_match(candidate_skill_normalized, normalized_required):
                    actual_skill_key = original_skill
                    break
            
            # If not found directly, check implied skills
            if not actual_skill_key:
                # Check if it's an implied skill (e.g., Java from Spring Boot)
                for candidate_skill_normalized in candidate_skills_set:
                    implied = SkillNormalizer.get_implied_skills(candidate_skill_normalized)
                    if normalized_required in implied:
                        # This is an implied skill, no gap
                        continue
            
            # If we found the actual skill, check proficiency
            if actual_skill_key and actual_skill_key in candidate_skills_dict:
                skill_data = candidate_skills_dict.get(actual_skill_key, {})
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
                if actual_skill_key in min_years_per_skill:
                    required_years = min_years_per_skill[actual_skill_key]
                    candidate_years_for_skill = candidate_years.get(actual_skill_key, 0.0)
                    
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


