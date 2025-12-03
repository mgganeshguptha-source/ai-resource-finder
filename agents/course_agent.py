"""
CourseAgent - Recommends training courses for skill gaps
"""

from typing import List, Dict, Any
from utils.database import DatabaseManager
from utils.bedrock_client import BedrockClient
from ingestion.cv_embedder import CVEmbedder
from models.course import TrainingCourse, CourseRecommendation
from config import Config


class CourseAgent:
    """Recommends training courses to address skill gaps"""
    
    def __init__(self, db_manager: DatabaseManager, bedrock_client: BedrockClient, config: Config):
        """
        Initialize CourseAgent
        
        Args:
            db_manager: Database manager instance
            bedrock_client: Bedrock client instance
            config: Configuration instance
        """
        self.db_manager = db_manager
        self.bedrock_client = bedrock_client
        self.config = config
        self.embedder = CVEmbedder(
            config.embedding_model_name,
            bedrock_client=bedrock_client if config.embedding_model_name.startswith("amazon.titan") else None
        )
    
    def recommend_courses(self, gaps: List[Dict[str, Any]], candidate_profile: Dict[str, Any]) -> List[CourseRecommendation]:
        """
        Recommend courses for skill gaps
        
        Args:
            gaps: List of gap dictionaries
            candidate_profile: Candidate profile dictionary
            
        Returns:
            List of top 3 course recommendations
        """
        if not gaps:
            return []
        
        # Build gap query
        gap_descriptions = []
        for gap in gaps:
            skill = gap.get("skill", "")
            gap_type = gap.get("gap_type", "")
            severity = gap.get("severity", "medium")
            gap_descriptions.append(f"{skill} ({gap_type}, {severity} severity)")
        
        gap_query = f"Gap: {', '.join(gap_descriptions[:5])}, intermediate level"
        
        # Step 1: Vector search courses
        courses = self._vector_search_courses(gap_query, self.config.top_n_courses)
        
        if not courses:
            print(f"⚠️ No courses found from vector search for gaps: {[g.get('skill', '') for g in gaps[:3]]}")
            return []
        
        # Step 2: LLM re-ranking
        courses = self._llm_rerank_courses(courses, gaps, candidate_profile)
        
        # Step 3: Rule-based filtering and scoring
        for course in courses:
            rule_score = self._rule_based_course_score(course, gaps, candidate_profile)
            course["rule_score"] = rule_score
            
            # Calculate final course score
            # Convert to float to handle Decimal types from PostgreSQL
            vector_score = float(course.get("similarity", 0.0))
            llm_score = float(course.get("llm_score", 0.0))
            final_score = (
                self.config.course_vector_weight * vector_score +
                self.config.course_llm_weight * llm_score +
                self.config.course_rule_weight * rule_score
            )
            course["final_score"] = final_score
        
        # Sort and get top courses (configurable, default 2)
        courses.sort(key=lambda x: x.get("final_score", 0.0), reverse=True)
        max_courses = min(self.config.final_top_courses, 2)  # Limit to max 2 courses
        top_courses = courses[:max_courses]
        
        # Convert to CourseRecommendation objects
        recommendations = []
        for course in top_courses:
            # Extract gaps addressed
            gaps_addressed = [gap.get("skill") for gap in gaps[:3]]  # Top 3 gaps
            
            recommendation = CourseRecommendation(
                course=TrainingCourse(
                    id=course.get("id"),
                    title=course.get("title", ""),
                    description=course.get("description", ""),
                    level=course.get("level"),
                    prerequisites=course.get("prerequisites", []),
                    url=course.get("url"),
                    metadata=course.get("metadata", {})
                ),
                score=course.get("final_score", 0.0),
                rationale=course.get("rationale", ""),
                gaps_addressed=gaps_addressed
            )
            recommendations.append(recommendation)
        
        return recommendations
    
    def _vector_search_courses(self, gap_query: str, top_n: int) -> List[Dict[str, Any]]:
        """Vector search for courses with multi-threshold fallback"""
        query_embedding = self.embedder.generate_embedding(gap_query)
        
        # Try with multiple thresholds (0.1, then 0.0) to ensure we get results
        thresholds = [0.1, 0.0]
        results = []
        for threshold in thresholds:
            query = """
                SELECT id, title, description, level, prerequisites, url, metadata, 1 - (embedding <=> %s::vector) as similarity
                FROM training_courses
                WHERE 1 - (embedding <=> %s::vector) > %s
                ORDER BY similarity DESC
                LIMIT %s
            """
            results = self.db_manager.execute_query(
                query,
                params=(query_embedding, query_embedding, threshold, top_n),
                fetch_all=True
            )
            if results:
                print(f"📊 Found {len(results)} courses from vector search with threshold {threshold}")
                return results
        
        # Fallback: if vector search still yields no results, get all courses
        print("⚠️ Vector search returned no results even with low threshold. Falling back to all courses.")
        all_courses_query = """
            SELECT id, title, description, level, prerequisites, url, metadata, 0.0 as similarity
            FROM training_courses
            LIMIT %s
        """
        results = self.db_manager.execute_query(
            all_courses_query,
            params=(top_n,),
            fetch_all=True
        )
        print(f"📊 Found {len(results)} courses from fallback (all courses)")
        return results or []
    
    def _llm_rerank_courses(self, courses: List[Dict[str, Any]], gaps: List[Dict[str, Any]],
                           candidate_profile: Dict[str, Any]) -> List[Dict[str, Any]]:
        """LLM re-ranking of courses"""
        gap_skills = [gap.get("skill", "") for gap in gaps[:5]]
        candidate_skills = list(candidate_profile.get("extracted_skills", {}).keys())[:10]
        
        course_summaries = []
        for course in courses:
            summary = f"Title: {course.get('title', '')}\n"
            summary += f"Description: {course.get('description', '')[:200]}\n"
            summary += f"Level: {course.get('level', '')}\n"
            summary += f"Prerequisites: {', '.join(course.get('prerequisites', [])[:3])}"
            course_summaries.append(summary)
        
        prompt = f"""Evaluate and rank these training courses for addressing skill gaps:

Skill Gaps: {', '.join(gap_skills)}
Candidate Current Skills: {', '.join(candidate_skills[:10])}

Courses:
{chr(10).join([f"{i+1}. {summary}" for i, summary in enumerate(course_summaries)])}

For each course, return a JSON array with:
{{
    "course_index": <0-based index>,
    "relevance_score": <0-100>,
    "rationale": "<why this course addresses the gaps>",
    "gaps_addressed": ["gap1", "gap2", ...]
}}

Return ONLY a JSON array, no additional text:"""

        try:
            results = self.bedrock_client.invoke_model_json(prompt, max_tokens=4096)
            
            if not isinstance(results, list):
                results = [results]
            
            for result in results:
                idx = result.get("course_index", 0)
                if 0 <= idx < len(courses):
                    courses[idx]["llm_score"] = result.get("relevance_score", 0) / 100.0
                    courses[idx]["rationale"] = result.get("rationale", "")
                    courses[idx]["gaps_addressed"] = result.get("gaps_addressed", [])
        
        except Exception as e:
            print(f"⚠️ Error in LLM re-ranking courses: {str(e)}")
            for course in courses:
                course["llm_score"] = 0.0
                course["rationale"] = ""
                course["gaps_addressed"] = []
        
        return courses
    
    def _rule_based_course_score(self, course: Dict[str, Any], gaps: List[Dict[str, Any]],
                                 candidate_profile: Dict[str, Any]) -> float:
        """Rule-based scoring for courses"""
        scores = []
        
        # Rule 1: Difficulty match (weight: 0.4)
        gap_severities = [gap.get("severity", "medium") for gap in gaps]
        has_high_severity = "high" in gap_severities
        course_level = course.get("level", "").lower()
        
        if has_high_severity and course_level in ["advanced", "expert"]:
            difficulty_score = 1.0
        elif not has_high_severity and course_level in ["beginner", "intermediate"]:
            difficulty_score = 1.0
        else:
            difficulty_score = 0.5
        
        scores.append(("difficulty", difficulty_score, 0.4))
        
        # Rule 2: Prerequisites match (weight: 0.3)
        prerequisites = course.get("prerequisites", [])
        candidate_skills = set(candidate_profile.get("extracted_skills", {}).keys())
        matched_prereqs = sum(1 for prereq in prerequisites if prereq.lower() in 
                             [s.lower() for s in candidate_skills])
        prereq_score = (matched_prereqs / len(prerequisites)) if prerequisites else 1.0
        scores.append(("prerequisites", prereq_score, 0.3))
        
        # Rule 3: Practicality (weight: 0.3)
        # Check if course description mentions practical/hands-on content
        description = course.get("description", "").lower()
        practicality_keywords = ["hands-on", "practical", "project", "real-world", "workshop", "lab"]
        has_practical = any(kw in description for kw in practicality_keywords)
        practicality_score = 1.0 if has_practical else 0.7
        scores.append(("practicality", practicality_score, 0.3))
        
        # Calculate weighted sum
        total_score = sum(score * weight for _, score, weight in scores)
        return total_score


