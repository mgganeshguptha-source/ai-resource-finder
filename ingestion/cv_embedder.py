"""
CV embedding generation utilities
"""

from typing import List, Optional
import numpy as np


class CVEmbedder:
    """Generate embeddings for CV text"""
    
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2", bedrock_client=None):
        """
        Initialize embedding model
        
        Args:
            model_name: Model name (Hugging Face SentenceTransformer or Bedrock model ID)
            bedrock_client: Optional BedrockClient instance for Bedrock embeddings
        """
        self.model_name = model_name
        self.bedrock_client = bedrock_client
        self.use_bedrock = False
        self.model = None
        
        # Check if this is a Bedrock model
        if model_name.startswith("amazon.titan") or (bedrock_client and "titan" in model_name.lower()):
            self.use_bedrock = True
            if not bedrock_client:
                # Try to create BedrockClient if not provided
                try:
                    from utils.bedrock_client import BedrockClient
                    from config import Config
                    config = Config()
                    self.bedrock_client = BedrockClient(
                        region_name=config.aws_region,
                        model_id=config.bedrock_model_id
                    )
                    print(f"🔄 Using Bedrock embedding model: {model_name}")
                except Exception as e:
                    raise ValueError(f"Bedrock model specified but BedrockClient initialization failed: {str(e)}")
            else:
                print(f"🔄 Using Bedrock embedding model: {model_name}")
        else:
            # Use Hugging Face SentenceTransformer
            try:
                from sentence_transformers import SentenceTransformer
                print(f"🔄 Loading Hugging Face embedding model: {model_name}")
                self.model = SentenceTransformer(model_name, device='cpu')
                print("✅ Embedding model loaded")
            except ImportError:
                raise ImportError("sentence-transformers package is required for Hugging Face models. Install with: pip install sentence-transformers")
    
    def generate_embedding(self, text: str, target_dimension: int = 768) -> List[float]:
        """
        Generate embedding for text
        
        Args:
            text: Input text
            target_dimension: Target dimension for embedding (default: 768 to match database)
            
        Returns:
            Embedding vector (truncated/padded to target_dimension)
        """
        try:
            if self.use_bedrock:
                if not self.bedrock_client:
                    raise ValueError("BedrockClient is required for Bedrock embeddings")
                embedding = self.bedrock_client.get_embedding(text, self.model_name)
                # Bedrock Titan Embed v1 returns 1536 dimensions, but database expects 768
                # Truncate to match database schema
                if len(embedding) > target_dimension:
                    print(f"⚠️ Truncating Bedrock embedding from {len(embedding)} to {target_dimension} dimensions")
                    return embedding[:target_dimension]
                elif len(embedding) < target_dimension:
                    # Pad with zeros if smaller (shouldn't happen with Bedrock)
                    print(f"⚠️ Padding embedding from {len(embedding)} to {target_dimension} dimensions")
                    return list(embedding) + [0.0] * (target_dimension - len(embedding))
                return embedding
            else:
                if not self.model:
                    raise ValueError("Model not initialized")
                embedding = self.model.encode(
                    [text],
                    convert_to_numpy=True,
                    show_progress_bar=False
                )
                embedding_list = embedding[0].tolist()
                # Hugging Face models typically return 384 or 768 dimensions
                # Ensure it matches target dimension
                if len(embedding_list) > target_dimension:
                    return embedding_list[:target_dimension]
                elif len(embedding_list) < target_dimension:
                    return list(embedding_list) + [0.0] * (target_dimension - len(embedding_list))
                return embedding_list
        except Exception as e:
            raise ValueError(f"Failed to generate embedding: {str(e)}")
    
    def generate_embeddings_batch(self, texts: List[str], target_dimension: int = 768) -> List[List[float]]:
        """
        Generate embeddings for multiple texts (batch processing)
        
        Args:
            texts: List of input texts
            target_dimension: Target dimension for embeddings (default: 768 to match database)
            
        Returns:
            List of embedding vectors (all truncated/padded to target_dimension)
        """
        try:
            if self.use_bedrock:
                if not self.bedrock_client:
                    raise ValueError("BedrockClient is required for Bedrock embeddings")
                # Bedrock doesn't support true batch, so process sequentially
                embeddings = []
                for text in texts:
                    embedding = self.generate_embedding(text, target_dimension)
                    embeddings.append(embedding)
                return embeddings
            else:
                if not self.model:
                    raise ValueError("Model not initialized")
                embeddings = self.model.encode(
                    texts,
                    convert_to_numpy=True,
                    show_progress_bar=True,
                    batch_size=32
                )
                # Ensure all embeddings match target dimension
                result = []
                for emb in embeddings.tolist():
                    if len(emb) > target_dimension:
                        result.append(emb[:target_dimension])
                    elif len(emb) < target_dimension:
                        result.append(list(emb) + [0.0] * (target_dimension - len(emb)))
                    else:
                        result.append(emb)
                return result
        except Exception as e:
            raise ValueError(f"Failed to generate batch embeddings: {str(e)}")


