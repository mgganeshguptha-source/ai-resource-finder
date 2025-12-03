"""
Hybrid matching engine - combines vector search, LLM re-ranking, and rule-based scoring
"""

from typing import List, Dict, Any, Optional
import json
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.database import DatabaseManager
from utils.bedrock_client import BedrockClient
from ingestion.cv_embedder import CVEmbedder
from services.gap_analyzer import GapAnalyzer
from models.candidate import CandidateProfile
from utils.skill_normalizer import SkillNormalizer
from config import Config


class MatchingEngine:
    """Hybrid matching engine for candidate-resource matching"""
    
    def __init__(self, db_manager: DatabaseManager, bedrock_client: Optional[BedrockClient] = None, 
                 config: Optional[Config] = None):
        """
        Initialize matching engine
        
        Args:
            db_manager: Database manager instance
            bedrock_client: Bedrock client instance
            config: Configuration instance
        """
        self.db_manager = db_manager
        self.config = config or Config()
        self.bedrock_client = bedrock_client or BedrockClient(
            region_name=self.config.aws_region,
            model_id=self.config.bedrock_model_id
        )
        self.embedder = CVEmbedder(
            self.config.embedding_model_name,
            bedrock_client=self.bedrock_client if self.config.embedding_model_name.startswith("amazon.titan") else None
        )
    
    def vector_search(self, requirement_text: str, top_n: int = 30) -> List[Dict[str, Any]]:
        """
        Perform vector search using pgvector
        
        Args:
            requirement_text: Requirement text
            top_n: Number of candidates to return
            
        Returns:
            List of candidate dictionaries with similarity scores
        """
        # Generate embedding for requirement
        query_embedding = self.embedder.generate_embedding(requirement_text)
        
        # Query database using cosine similarity
        # Use configurable threshold from config, default to 0.2 if not set
        threshold = getattr(self.config, 'vector_search_threshold', 0.2)
        query = """
            SELECT * FROM cosine_similarity_search_candidates(
                %s::vector,
                %s,
                %s
            )
        """
        
        results = self.db_manager.execute_query(
            query,
            params=(query_embedding, threshold, top_n),
            fetch_all=True
        )
        
        results_list = results or []
        
        # Debug logging
        if not results_list:
            print(f"⚠️ Vector search returned 0 candidates with threshold={threshold}")
        else:
            similarities = [r.get("similarity", 0) for r in results_list]
            print(f"ℹ️ Vector search found {len(results_list)} candidates with similarities: {similarities[:5]}")
        
        return results_list
    
    def llm_rerank(self, candidates: List[Dict[str, Any]], requirement_text: str, 
                   parsed_requirement: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        LLM re-ranking of candidates
        
        Args:
            candidates: List of candidate dictionaries from vector search
            requirement_text: Original requirement text
            parsed_requirement: Parsed requirement structure
            
        Returns:
            List of candidates with LLM scores and analysis
        """
        if not candidates:
            return []
        
        # Batch process candidates (process in smaller batches to avoid token limits)
        batch_size = 5
        reranked_candidates = []
        
        for i in range(0, len(candidates), batch_size):
            batch = candidates[i:i + batch_size]
            batch_results = self._rerank_batch(batch, requirement_text, parsed_requirement)
            reranked_candidates.extend(batch_results)
        
        return reranked_candidates
    
    def _rerank_batch(self, candidates: List[Dict[str, Any]], requirement_text: str,
                     parsed_requirement: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Re-rank a batch of candidates"""
        # Prepare candidate summaries for LLM
        candidate_summaries = []
        for candidate in candidates:
            skills = list(candidate.get("extracted_skills", {}).keys())[:10]  # Limit skills
            summary = f"Name: {candidate.get('name', 'Unknown')}\n"
            summary += f"Skills: {', '.join(skills)}\n"
            summary += f"Years of Experience: {candidate.get('years_of_experience', {})}\n"
            summary += f"Domains: {', '.join(candidate.get('domain_tags', [])[:5])}"
            
            # Add experience summary if available
            experience_summary = candidate.get('experience_summary', '')
            if experience_summary:
                summary += f"\nExperience Summary: {experience_summary}"
            
            candidate_summaries.append(summary)
        
        prompt = f"""Evaluate and rank these candidates for the following requirement:

Requirement: {requirement_text}

Required Skills: {', '.join(parsed_requirement.get('required_skills', []))}
Preferred Skills: {', '.join(parsed_requirement.get('preferred_skills', []))}
Domain: {parsed_requirement.get('domain', '')}
Seniority: {parsed_requirement.get('seniority', 'mid')}

Candidates:
{chr(10).join([f"{i+1}. {summary}" for i, summary in enumerate(candidate_summaries)])}

For each candidate, return a JSON array with:
{{
    "candidate_index": <0-based index>,
    "relevance_score": <0-100>,
    "matched_skills": ["skill1", "skill2", ...],
    "missing_skills": ["skill1", "skill2", ...],
    "proficiency_insights": "<brief assessment>",
    "evidence_snippets": ["evidence1", "evidence2", ...]
}}

Important: Pay special attention to the Experience Summary section. Even if a skill is not explicitly listed, 
the candidate may have relevant experience described in their project descriptions. For example:
- "database migration" experience might be in project descriptions even if not in the skills list
- Client names and industries (e.g., "IQVIA" = lifescience) indicate domain experience
- Project scale and impact (e.g., "migrated 5TB database") demonstrate real-world expertise

Return ONLY a JSON array, no additional text:"""

        try:
            results = self.bedrock_client.invoke_model_json(prompt, max_tokens=4096)
            
            # Ensure results is a list
            if not isinstance(results, list):
                results = [results]
            
            # Map results back to candidates
            for result in results:
                idx = result.get("candidate_index", 0)
                if 0 <= idx < len(candidates):
                    candidates[idx]["llm_score"] = result.get("relevance_score", 0) / 100.0  # Normalize to 0-1
                    candidates[idx]["matched_skills"] = result.get("matched_skills", [])
                    candidates[idx]["missing_skills"] = result.get("missing_skills", [])
                    candidates[idx]["proficiency_insights"] = result.get("proficiency_insights", "")
                    candidates[idx]["evidence_snippets"] = result.get("evidence_snippets", [])
            
            # Set default values for candidates without LLM scores
            for candidate in candidates:
                if "llm_score" not in candidate:
                    candidate["llm_score"] = 0.0
                    candidate["matched_skills"] = []
                    candidate["missing_skills"] = []
                    candidate["proficiency_insights"] = ""
                    candidate["evidence_snippets"] = []
        
        except Exception as e:
            print(f"⚠️ Error in LLM re-ranking: {str(e)}")
            # Set default values on error
            for candidate in candidates:
                candidate["llm_score"] = 0.0
                candidate["matched_skills"] = []
                candidate["missing_skills"] = []
                candidate["proficiency_insights"] = ""
                candidate["evidence_snippets"] = []
        
        return candidates
    
    def rule_based_scoring(self, candidate: Dict[str, Any], parsed_requirement: Dict[str, Any]) -> float:
        """
        Calculate rule-based score for a candidate
        
        Args:
            candidate: Candidate dictionary
            parsed_requirement: Parsed requirement structure
            
        Returns:
            Rule-based score (0-1)
        """
        scores = []
        
        # Rule 1: Must-have skills (weight: 0.4)
        required_skills = parsed_requirement.get("required_skills", [])
        candidate_skills = set(candidate.get("extracted_skills", {}).keys())
        matched_required = sum(1 for skill in required_skills if skill in candidate_skills)
        required_score = (matched_required / len(required_skills)) if required_skills else 1.0
        scores.append(("required_skills", required_score, 0.4))
        
        # Rule 2: Preferred skills (weight: 0.2)
        preferred_skills = parsed_requirement.get("preferred_skills", [])
        matched_preferred = sum(1 for skill in preferred_skills if skill in candidate_skills)
        preferred_score = (matched_preferred / len(preferred_skills)) if preferred_skills else 1.0
        scores.append(("preferred_skills", preferred_score, 0.2))
        
        # Rule 3: Domain match (weight: 0.15)
        required_domain = parsed_requirement.get("domain", "").lower()
        candidate_domains = [d.lower() for d in candidate.get("domain_tags", [])]
        domain_score = 1.0 if (not required_domain or 
                              any(required_domain in d or d in required_domain for d in candidate_domains)) else 0.0
        scores.append(("domain", domain_score, 0.15))
        
        # Rule 4: Years of experience (weight: 0.15)
        min_years = parsed_requirement.get("min_years_per_skill", {})
        candidate_years = candidate.get("years_of_experience", {})
        years_scores = []
        for skill, min_yrs in min_years.items():
            candidate_yrs = candidate_years.get(skill, 0.0)
            if candidate_yrs >= min_yrs:
                years_scores.append(1.0)
            elif candidate_yrs > 0:
                years_scores.append(candidate_yrs / min_yrs)  # Partial credit
            else:
                years_scores.append(0.0)
        years_score = sum(years_scores) / len(years_scores) if years_scores else 1.0
        scores.append(("years", years_score, 0.15))
        
        # Rule 5: Proficiency verbs (weight: 0.1)
        # Check for strong proficiency indicators in extracted skills
        proficiency_keywords = ["expert", "advanced", "senior", "lead", "architect"]
        candidate_skills_data = candidate.get("extracted_skills", {})
        proficiency_count = sum(1 for skill_data in candidate_skills_data.values() 
                              if isinstance(skill_data, dict) and 
                              any(kw in str(skill_data.get("proficiency", "")).lower() 
                                  for kw in proficiency_keywords))
        proficiency_score = min(proficiency_count / max(len(required_skills), 1), 1.0)
        scores.append(("proficiency", proficiency_score, 0.1))
        
        # Calculate weighted sum
        total_score = sum(score * weight for _, score, weight in scores)
        return total_score
    
    def calculate_final_score(self, vector_score: float, llm_score: float, rule_score: float) -> float:
        """
        Calculate final combined score
        
        Args:
            vector_score: Vector search similarity (0-1)
            llm_score: LLM re-ranking score (0-1)
            rule_score: Rule-based score (0-1)
            
        Returns:
            Final score (0-1)
        """
        final = (
            self.config.vector_search_weight * vector_score +
            self.config.llm_score_weight * llm_score +
            self.config.rule_score_weight * rule_score
        )
        return min(max(final, 0.0), 1.0)  # Clamp to 0-1
    
    def match_candidates(self, requirement_text: str, parsed_requirement: Dict[str, Any],
                        top_n: int = 3) -> List[Dict[str, Any]]:
        """
        Complete matching pipeline: vector search → LLM re-rank → rule score → final score
        
        Args:
            requirement_text: Requirement text
            parsed_requirement: Parsed requirement structure
            top_n: Number of top candidates to return
            
        Returns:
            List of top candidates with all scores and analysis
        """
        # Step 1: Vector search
        candidates = self.vector_search(requirement_text, self.config.top_n_candidates)
        
        if not candidates:
            print("⚠️ No candidates found in vector search - check vector_search_threshold and database embeddings")
            return []
        
        print(f"ℹ️ Starting matching pipeline with {len(candidates)} candidates from vector search")
        
        # Step 2: LLM re-ranking
        candidates = self.llm_rerank(candidates, requirement_text, parsed_requirement)
        
        # Step 3: Rule-based scoring and final score calculation
        for candidate in candidates:
            # Get vector similarity score - convert to float to handle Decimal types from PostgreSQL
            vector_score = float(candidate.get("similarity", 0.0))
            
            # Get LLM score
            llm_score = float(candidate.get("llm_score", 0.0))
            
            # Calculate rule-based score
            rule_score = self.rule_based_scoring(candidate, parsed_requirement)
            candidate["rule_score"] = rule_score
            
            # Calculate final score
            final_score = self.calculate_final_score(vector_score, llm_score, rule_score)
            candidate["final_score"] = final_score
            candidate["match_percentage"] = round(final_score * 100)
            
            # Analyze gaps - filter candidate dict to only include CandidateProfile fields
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
            
            gaps = GapAnalyzer.analyze_gaps(
                CandidateProfile(**profile_data),
                parsed_requirement.get("required_skills", []),
                parsed_requirement.get("min_years_per_skill", {})
            )
            candidate["gaps"] = gaps
            
            # Normalize matched_skills and remove duplicates/variations
            matched_skills = candidate.get("matched_skills", [])
            if matched_skills:
                # Remove skills that appear in gaps (duplicates)
                gap_skill_names = {SkillNormalizer.normalize_skill(gap.get("skill", "")) for gap in gaps}
                matched_skills_filtered = [
                    skill for skill in matched_skills
                    if SkillNormalizer.normalize_skill(skill) not in gap_skill_names
                ]
                # Remove duplicate variations
                candidate["matched_skills"] = SkillNormalizer.remove_duplicate_skills(matched_skills_filtered)
            else:
                candidate["matched_skills"] = []
        
        # Sort by final score and return top N
        candidates.sort(key=lambda x: x.get("final_score", 0.0), reverse=True)
        return candidates[:top_n]


