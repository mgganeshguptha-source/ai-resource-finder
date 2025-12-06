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
from services.gap_analyzer import GapAnalyzer
from models.candidate import CandidateProfile
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
        
        # Use Bedrock embedder for AWS Titan models, otherwise use HuggingFace embedder
        embedding_model_name = self.config.embedding_model_name
        if embedding_model_name and embedding_model_name.startswith("amazon.titan"):
            # Use Bedrock-based embedder for AWS Titan models
            from utils.cv_embedder import CVEmbedder
            self.embedder = CVEmbedder(
                model_name=embedding_model_name,
                bedrock_client=self.bedrock_client
            )
        else:
            # Use HuggingFace-based embedder for other models
            from ingestion.cv_embedder import CVEmbedder
            self.embedder = CVEmbedder(embedding_model_name or "sentence-transformers/all-MiniLM-L6-v2")
    
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
        query = """
            SELECT * FROM cosine_similarity_search_candidates(
                %s::vector,
                0.3,
                %s
            )
        """
        
        results = self.db_manager.execute_query(
            query,
            params=(query_embedding, top_n),
            fetch_all=True
        )
        
        return results or []
    
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
            # Get name
            name = candidate.get('name', 'Unknown')
            
            # Get all skills
            extracted_skills = candidate.get("extracted_skills", {})
            skills = list(extracted_skills.keys())
            
            # Format years of experience as readable string
            years_of_experience = candidate.get('years_of_experience', {})
            years_formatted = []
            if isinstance(years_of_experience, dict):
                for skill, years in years_of_experience.items():
                    if years and years > 0:
                        years_formatted.append(f"{skill}: {years} years")
            years_str = ', '.join(years_formatted) if years_formatted else "Not specified"
            
            # Get all domains
            domain_tags = candidate.get('domain_tags', [])
            domains_str = ', '.join(domain_tags) if domain_tags else "Not specified"
            
            # Get experience summary
            experience_summary = candidate.get('experience_summary', '')
            if not experience_summary:
                experience_summary = "Not available"
            
            # Build comprehensive summary
            summary = f"Name: {name}\n"
            summary += f"Skills: {', '.join(skills) if skills else 'Not specified'}\n"
            summary += f"Years of Experience: {years_str}\n"
            summary += f"Domains: {domains_str}\n"
            summary += f"Experience Summary: {experience_summary}"
            candidate_summaries.append(summary)
        
        # Format seniority for prompt (show "Not specified" if empty)
        seniority = parsed_requirement.get('seniority', '')
        seniority_display = seniority if seniority else "Not specified"
        
        prompt = f"""Evaluate and rank these candidates for the following requirement:

Requirement: {requirement_text}

Required Skills: {', '.join(parsed_requirement.get('required_skills', []))}
Preferred Skills: {', '.join(parsed_requirement.get('preferred_skills', []))}
Domain: {parsed_requirement.get('domain', '') or 'Not specified'}
Seniority: {seniority_display}

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
        
        # Base weights
        BASE_REQUIRED_WEIGHT = 0.40
        BASE_PREFERRED_WEIGHT = 0.20
        BASE_DOMAIN_WEIGHT = 0.15
        BASE_YEARS_WEIGHT = 0.15
        PROFICIENCY_WEIGHT = 0.10  # Removed, weight redistributed to required skills
        
        # Start with required skills weight (includes proficiency weight since proficiency is removed)
        required_skills_weight = BASE_REQUIRED_WEIGHT + PROFICIENCY_WEIGHT  # 0.40 + 0.10 = 0.50
        
        # Rule 1: Must-have skills (mandatory)
        required_skills = parsed_requirement.get("required_skills", [])
        candidate_skills = set(candidate.get("extracted_skills", {}).keys())
        matched_required = sum(1 for skill in required_skills if skill in candidate_skills)
        required_score = (matched_required / len(required_skills)) if required_skills else 1.0
        
        # Rule 2: Preferred skills (only if JD mentions preferred skills)
        preferred_skills = parsed_requirement.get("preferred_skills", [])
        preferred_skills_weight = 0.0
        preferred_score = 0.0
        
        if preferred_skills:
            # JD mentions preferred skills, use it
            matched_preferred = sum(1 for skill in preferred_skills if skill in candidate_skills)
            preferred_score = (matched_preferred / len(preferred_skills)) if preferred_skills else 0.0
            preferred_skills_weight = BASE_PREFERRED_WEIGHT
            scores.append(("preferred_skills", preferred_score, preferred_skills_weight))
        else:
            # JD doesn't mention preferred skills, skip and redistribute weight to required skills
            required_skills_weight += BASE_PREFERRED_WEIGHT
        
        # Rule 3: Domain match (only if domain is identified)
        required_domain = parsed_requirement.get("domain", "") or ""
        required_domain = required_domain.strip() if isinstance(required_domain, str) else ""
        domain_weight = 0.0
        domain_score = 0.0
        
        if required_domain:
            # Domain is identified, perform domain match
            required_domain_lower = required_domain.lower()
            candidate_domains = [d.lower() for d in candidate.get("domain_tags", [])]
            domain_score = 1.0 if any(required_domain_lower in d or d in required_domain_lower 
                                      for d in candidate_domains) else 0.0
            domain_weight = BASE_DOMAIN_WEIGHT
            scores.append(("domain", domain_score, domain_weight))
        else:
            # Domain not identified, skip and redistribute weight to required skills
            required_skills_weight += BASE_DOMAIN_WEIGHT
        
        # Rule 4: Years of experience (only if explicitly mentioned in JD)
        min_years = parsed_requirement.get("min_years_per_skill", {})
        years_weight = 0.0
        years_score = 0.0
        
        if min_years and isinstance(min_years, dict) and len(min_years) > 0:
            # Years of experience explicitly mentioned, perform years match
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
            years_weight = BASE_YEARS_WEIGHT
            scores.append(("years", years_score, years_weight))
        else:
            # Years of experience not mentioned, skip and redistribute weight to required skills
            required_skills_weight += BASE_YEARS_WEIGHT
        
        # Add required skills score with dynamically calculated weight
        scores.append(("required_skills", required_score, required_skills_weight))
        
        # Calculate weighted sum (total should always be 1.0)
        total_score = sum(score * weight for _, score, weight in scores)
        return min(max(total_score, 0.0), 1.0)  # Clamp to 0-1
    
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
        print(f"🔍 DEBUG: MatchingEngine.vector_search called with top_n={self.config.top_n_candidates}")
        candidates = self.vector_search(requirement_text, self.config.top_n_candidates)
        print(f"🔍 DEBUG: Vector search returned {len(candidates)} candidates")
        
        if not candidates:
            print("🔍 DEBUG: No candidates from vector search, returning empty list")
            return []
        
        # Step 2: LLM re-ranking
        print(f"🔍 DEBUG: Starting LLM re-ranking for {len(candidates)} candidates")
        candidates = self.llm_rerank(candidates, requirement_text, parsed_requirement)
        print(f"🔍 DEBUG: LLM re-ranking completed")
        
        # Step 3: Rule-based scoring and final score calculation
        for candidate in candidates:
            # Get vector similarity score
            vector_score = candidate.get("similarity", 0.0)
            
            # Get LLM score
            llm_score = candidate.get("llm_score", 0.0)
            
            # Calculate rule-based score
            rule_score = self.rule_based_scoring(candidate, parsed_requirement)
            candidate["rule_score"] = rule_score
            
            # Calculate final score
            final_score = self.calculate_final_score(vector_score, llm_score, rule_score)
            candidate["final_score"] = final_score
            candidate["match_percentage"] = round(final_score * 100)
            
            # Analyze gaps
            gaps = GapAnalyzer.analyze_gaps(
                CandidateProfile(**candidate),
                parsed_requirement.get("required_skills", []),
                parsed_requirement.get("min_years_per_skill", {})
            )
            candidate["gaps"] = gaps
        
        # Sort by final score and return top N
        candidates.sort(key=lambda x: x.get("final_score", 0.0), reverse=True)
        final_candidates = candidates[:top_n]
        print(f"🔍 DEBUG: Returning {len(final_candidates)} final candidates (top_n={top_n})")
        for i, c in enumerate(final_candidates):
            print(f"🔍 DEBUG: Final candidate {i+1}: {c.get('name', 'Unknown')} - Score: {c.get('final_score', 0):.2f}, Match: {c.get('match_percentage', 0)}%")
        return final_candidates


