"""
Skill normalization utilities - handles skill variations and dependencies
"""

from typing import Dict, List, Set
import re


class SkillNormalizer:
    """Normalize and match skills with variations and dependencies"""
    
    # Skill variations mapping (normalized -> variations)
    SKILL_VARIATIONS = {
        "rest api": ["rest api", "rest apis", "restful api", "restful apis", "rest", "restful"],
        "spring boot": ["spring boot", "springboot", "spring-boot"],
        "spring framework": ["spring framework", "spring", "spring core"],
        "react.js": ["react.js", "reactjs", "react", "react js"],
        "node.js": ["node.js", "nodejs", "node js", "node"],
        "mysql": ["mysql", "my sql"],
        "javascript": ["javascript", "js", "ecmascript"],
        "typescript": ["typescript", "ts"],
        "python": ["python", "py"],
        "java": ["java", "java programming", "java development"],
    }
    
    # Skill dependencies (if you know X, you implicitly know Y)
    SKILL_DEPENDENCIES = {
        "spring boot": ["java", "spring framework"],
        "spring framework": ["java"],
        "react.js": ["javascript"],
        "node.js": ["javascript"],
        "typescript": ["javascript"],
        "angular": ["typescript", "javascript"],
        "vue.js": ["javascript"],
    }
    
    @staticmethod
    def normalize_skill(skill: str) -> str:
        """
        Normalize a skill name to a standard form
        
        Args:
            skill: Raw skill name
            
        Returns:
            Normalized skill name
        """
        if not skill:
            return ""
        
        # Convert to lowercase and strip
        normalized = skill.lower().strip()
        
        # Remove common suffixes/prefixes
        normalized = re.sub(r'\s+', ' ', normalized)  # Multiple spaces to single
        normalized = normalized.replace(".", "").replace("-", " ").replace("_", " ")
        
        # Check against known variations
        for standard, variations in SkillNormalizer.SKILL_VARIATIONS.items():
            if normalized in variations or any(v in normalized for v in variations):
                return standard
        
        # Return original if no match found (but normalized)
        return normalized
    
    @staticmethod
    def skills_match(skill1: str, skill2: str) -> bool:
        """
        Check if two skills are the same (considering variations)
        
        Args:
            skill1: First skill
            skill2: Second skill
            
        Returns:
            True if skills match
        """
        norm1 = SkillNormalizer.normalize_skill(skill1)
        norm2 = SkillNormalizer.normalize_skill(skill2)
        
        # Direct match
        if norm1 == norm2:
            return True
        
        # Check if one is a variation of the other
        for standard, variations in SkillNormalizer.SKILL_VARIATIONS.items():
            if norm1 in variations and norm2 in variations:
                return True
            if norm1 == standard and norm2 in variations:
                return True
            if norm2 == standard and norm1 in variations:
                return True
        
        return False
    
    @staticmethod
    def get_implied_skills(skill: str) -> List[str]:
        """
        Get skills that are implied by knowing this skill
        
        Args:
            skill: Skill name
            
        Returns:
            List of implied skills
        """
        normalized = SkillNormalizer.normalize_skill(skill)
        return SkillNormalizer.SKILL_DEPENDENCIES.get(normalized, [])
    
    @staticmethod
    def has_skill_or_equivalent(candidate_skills: Set[str], required_skill: str) -> bool:
        """
        Check if candidate has the required skill or an equivalent variation
        
        Args:
            candidate_skills: Set of candidate's skills (normalized)
            required_skill: Required skill name
            
        Returns:
            True if candidate has the skill or equivalent
        """
        normalized_required = SkillNormalizer.normalize_skill(required_skill)
        
        # Direct match
        if normalized_required in candidate_skills:
            return True
        
        # Check variations
        for candidate_skill in candidate_skills:
            if SkillNormalizer.skills_match(candidate_skill, normalized_required):
                return True
        
        # Check if candidate has a skill that implies the required skill
        for candidate_skill in candidate_skills:
            implied = SkillNormalizer.get_implied_skills(candidate_skill)
            if normalized_required in implied:
                return True
        
        return False
    
    @staticmethod
    def normalize_skill_list(skills: List[str]) -> List[str]:
        """
        Normalize a list of skills
        
        Args:
            skills: List of skill names
            
        Returns:
            List of normalized skill names
        """
        normalized = [SkillNormalizer.normalize_skill(s) for s in skills if s]
        # Remove duplicates while preserving order
        seen = set()
        result = []
        for skill in normalized:
            if skill and skill not in seen:
                seen.add(skill)
                result.append(skill)
        return result
    
    @staticmethod
    def remove_duplicate_skills(skills: List[str]) -> List[str]:
        """
        Remove duplicate skills considering variations
        
        Args:
            skills: List of skill names
            
        Returns:
            List of unique skills (no duplicates or variations)
        """
        if not skills:
            return []
        
        normalized_skills = SkillNormalizer.normalize_skill_list(skills)
        seen = set()
        result = []
        
        for skill in normalized_skills:
            # Check if we've already seen this skill or a variation
            is_duplicate = False
            for seen_skill in seen:
                if SkillNormalizer.skills_match(skill, seen_skill):
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                seen.add(skill)
                result.append(skill)
        
        return result

