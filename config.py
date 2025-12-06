"""
Configuration management for AI Resource Finder
"""

import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration management for the AI Resource Finder"""
    
    def __init__(self):
        # AWS Configuration
        self.aws_region = self._get_env_var("AWS_REGION", "us-east-1")
        self.aws_access_key_id = self._get_env_var("AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key = self._get_env_var("AWS_SECRET_ACCESS_KEY")
        
        # AWS Bedrock Configuration
        self.bedrock_model_id = self._get_env_var(
            "BEDROCK_MODEL_ID", 
            "anthropic.claude-3-haiku-20240307-v1:0"  # Small, cost-effective model
        )
        
        # AWS S3 Configuration
        self.s3_bucket_name = self._get_env_var("S3_BUCKET_NAME")
        self.s3_cv_prefix = self._get_env_var("S3_CV_PREFIX", "cvs/")
        
        # AWS SES Configuration
        self.ses_region = self._get_env_var("SES_REGION", self.aws_region)
        self.ses_from_email = self._get_env_var("SES_FROM_EMAIL", "mg.ganeshguptha@gmail.com")
        self.ses_admin_email = self._get_env_var("SES_ADMIN_EMAIL", "mg.ganeshguptha@gmail.com")
        
        # Database Configuration
        self.database_url = self._get_env_var("DATABASE_URL")  # PostgreSQL connection string
        self.supabase_database_url = self._get_env_var("SUPABASE_DATABASE_URL")  # Alternative: Supabase URL
        
        # Use Supabase URL if available, otherwise use DATABASE_URL
        self.db_connection_string = self.supabase_database_url or self.database_url
        
        # Embedding Model Configuration
        self.embedding_model_name = self._get_env_var(
            "EMBEDDING_MODEL_NAME",
            "amazon.titan-embed-text-v1"  # 768-dim, free local model
        )
        
        # Matching Configuration
        self.vector_search_weight = float(self._get_env_var("VECTOR_SEARCH_WEIGHT", "0.15"))
        self.llm_score_weight = float(self._get_env_var("LLM_SCORE_WEIGHT", "0.25"))
        self.rule_score_weight = float(self._get_env_var("RULE_SCORE_WEIGHT", "0.60"))
        
        # Course Recommendation Weights
        self.course_vector_weight = float(self._get_env_var("COURSE_VECTOR_WEIGHT", "0.30"))
        self.course_llm_weight = float(self._get_env_var("COURSE_LLM_WEIGHT", "0.50"))
        self.course_rule_weight = float(self._get_env_var("COURSE_RULE_WEIGHT", "0.20"))
        
        # Search Configuration
        self.top_n_candidates = int(self._get_env_var("TOP_N_CANDIDATES", "10"))
        self.top_n_courses = int(self._get_env_var("TOP_N_COURSES", "10"))
        self.final_top_candidates = int(self._get_env_var("FINAL_TOP_CANDIDATES", "3"))
        self.final_top_courses = int(self._get_env_var("FINAL_TOP_COURSES", "3"))
        
        # Thresholds
        self.match_threshold_strong = float(self._get_env_var("MATCH_THRESHOLD_STRONG", "0.75"))
        self.match_threshold_moderate = float(self._get_env_var("MATCH_THRESHOLD_MODERATE", "0.50"))
        
        # Validate required configuration
        self._validate_config()
    
    def _get_env_var(self, var_name: str, default: Optional[str] = None) -> Optional[str]:
        """Get environment variable with optional default"""
        value = os.getenv(var_name, default)
        return value.strip() if value else None
    
    def _validate_config(self):
        """Validate that required configuration is present"""
        required_vars = {
            "AWS_ACCESS_KEY_ID": self.aws_access_key_id,
            "AWS_SECRET_ACCESS_KEY": self.aws_secret_access_key,
            "S3_BUCKET_NAME": self.s3_bucket_name,
            "DATABASE_URL or SUPABASE_DATABASE_URL": self.db_connection_string,
        }
        
        missing_vars = [var for var, value in required_vars.items() if not value]
        
        if missing_vars:
            print("⚠️ Missing required environment variables:")
            for var in missing_vars:
                print(f"   - {var}")
            print("\nPlease set these environment variables before running the application.")
        else:
            print("✅ All required environment variables are set")
    
    @property
    def is_configured(self) -> bool:
        """Check if all required configuration is present"""
        return all([
            self.aws_access_key_id,
            self.aws_secret_access_key,
            self.s3_bucket_name,
            self.db_connection_string,
        ])
    
    def get_config_status(self) -> dict:
        """Get configuration status for debugging"""
        return {
            "aws_region": self.aws_region,
            "bedrock_model_id": self.bedrock_model_id,
            "s3_bucket_name": self.s3_bucket_name,
            "database_configured": bool(self.db_connection_string),
            "fully_configured": self.is_configured
        }


