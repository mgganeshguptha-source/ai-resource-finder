"""
CV embedding generation utilities
"""

from typing import List, Optional
from sentence_transformers import SentenceTransformer
import numpy as np


class CVEmbedder:
    """Generate embeddings for CV text"""
    
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        """
        Initialize embedding model
        
        Args:
            model_name: Sentence transformer model name
        """
        print(f"🔄 Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name, device='cpu')
        print("✅ Embedding model loaded")
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text
        
        Args:
            text: Input text
            
        Returns:
            768-dimensional embedding vector
        """
        try:
            embedding = self.model.encode(
                [text],
                convert_to_numpy=True,
                show_progress_bar=False
            )
            return embedding[0].tolist()
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
            embeddings = self.model.encode(
                texts,
                convert_to_numpy=True,
                show_progress_bar=True,
                batch_size=32
            )
            return embeddings.tolist()
        except Exception as e:
            raise ValueError(f"Failed to generate batch embeddings: {str(e)}")


