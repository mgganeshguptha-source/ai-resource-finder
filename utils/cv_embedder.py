"""
CV embedding generation utilities using AWS Bedrock
"""

from typing import List, Optional
import os

# Import at top level to avoid import issues in Lambda
# Delay import to avoid circular dependency issues
# Will import BedrockClient when needed


class CVEmbedder:
    """Generate embeddings for CV text using AWS Bedrock"""
    
    def __init__(self, model_name: str = None, bedrock_client: Optional['BedrockClient'] = None):
        """
        Initialize embedding model using AWS Bedrock
        
        Args:
            model_name: Bedrock embedding model ID (e.g., "amazon.titan-embed-text-v1")
            bedrock_client: Optional BedrockClient instance (will create if not provided)
        """
        # Import here to avoid import-time issues
        from utils.bedrock_client import BedrockClient as BC
        self.embedding_model_id = model_name or os.getenv("BEDROCK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v1")
        self.bedrock_client = bedrock_client or BC(
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
            model_id=self.embedding_model_id
        )
        print(f"🔄 Using AWS Bedrock for embeddings: {self.embedding_model_id}")
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text using Bedrock
        
        Args:
            text: Input text
            
        Returns:
            768-dimensional embedding vector (truncated from Bedrock's output if needed)
        """
        try:
            embedding = self.bedrock_client.get_embedding(text, self.embedding_model_id)
            # Database expects 768 dimensions, truncate if Bedrock returns more
            # Bedrock models can return 1024 or 1536 dimensions depending on model
            if len(embedding) > 768:
                print(f"Truncating embedding from {len(embedding)} to 768 dimensions")
                embedding = embedding[:768]
            elif len(embedding) < 768:
                # Pad with zeros if smaller (shouldn't happen with Bedrock)
                print(f"Warning: Embedding has {len(embedding)} dimensions, padding to 768")
                embedding = list(embedding) + [0.0] * (768 - len(embedding))
            return embedding
        except Exception as e:
            raise ValueError(f"Failed to generate embedding: {str(e)}")
    
    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts (batch processing)
        
        Args:
            texts: List of input texts
            
        Returns:
            List of embedding vectors
        """
        try:
            embeddings = []
            for text in texts:
                embedding = self.generate_embedding(text)
                embeddings.append(embedding)
            return embeddings
        except Exception as e:
            raise ValueError(f"Failed to generate batch embeddings: {str(e)}")


