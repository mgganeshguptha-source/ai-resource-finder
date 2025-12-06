"""
AWS Bedrock client wrapper for LLM operations
"""

import json
import boto3
from typing import Dict, Any, Optional, List
from botocore.exceptions import ClientError


class BedrockClient:
    """
    Wrapper for AWS Bedrock API calls
    """
    
    def __init__(self, region_name: str = "us-east-1", model_id: str = "anthropic.claude-3-haiku-20240307-v1:0"):
        """
        Initialize Bedrock client
        
        Args:
            region_name: AWS region
            model_id: Bedrock model identifier
        """
        self.region_name = region_name
        self.model_id = model_id
        self.bedrock_runtime = boto3.client(
            'bedrock-runtime',
            region_name=region_name
        )
    
    def invoke_model(self, prompt: str, max_tokens: int = 4096, temperature: float = 0.0) -> str:
        """
        Invoke Bedrock model with a prompt
        
        Args:
            prompt: Input prompt text
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0 for deterministic)
            
        Returns:
            Model response text
        """
        try:
            # Prepare request body based on model type
            if "claude" in self.model_id.lower():
                body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                }
            elif "titan" in self.model_id.lower():
                body = {
                    "inputText": prompt,
                    "textGenerationConfig": {
                        "maxTokenCount": max_tokens,
                        "temperature": temperature
                    }
                }
            else:
                # Default format
                body = {
                    "prompt": prompt,
                    "max_tokens": max_tokens,
                    "temperature": temperature
                }
            
            response = self.bedrock_runtime.invoke_model(
                modelId=self.model_id,
                body=json.dumps(body)
            )
            
            response_body = json.loads(response['body'].read())
            
            # Extract text based on model type
            if "claude" in self.model_id.lower():
                return response_body['content'][0]['text']
            elif "titan" in self.model_id.lower():
                return response_body['results'][0]['outputText']
            else:
                return response_body.get('text', str(response_body))
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            raise Exception(f"Bedrock API error ({error_code}): {error_message}")
    
    def invoke_model_json(self, prompt: str, max_tokens: int = 4096, temperature: float = 0.0) -> Dict[str, Any]:
        """
        Invoke Bedrock model and parse JSON response
        
        Args:
            prompt: Input prompt text
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            
        Returns:
            Parsed JSON response as dict
        """
        response_text = self.invoke_model(prompt, max_tokens, temperature)
        
        # Try to extract JSON from response
        try:
            # Look for JSON code blocks
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                json_text = response_text[json_start:json_end].strip()
            else:
                json_text = response_text.strip()
            
            return json.loads(json_text)
        except json.JSONDecodeError:
            # If JSON parsing fails, try to extract JSON object from text
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            raise ValueError(f"Could not parse JSON from response: {response_text[:200]}")
    
    def batch_invoke(self, prompts: List[str], max_tokens: int = 4096) -> List[str]:
        """
        Batch invoke model for multiple prompts (sequential for now)
        
        Args:
            prompts: List of prompt texts
            max_tokens: Maximum tokens per response
            
        Returns:
            List of response texts
        """
        responses = []
        for prompt in prompts:
            response = self.invoke_model(prompt, max_tokens)
            responses.append(response)
        return responses
    
    def get_embedding(self, text: str, embedding_model_id: Optional[str] = None) -> List[float]:
        """
        Generate embedding for text using AWS Bedrock embedding models
        
        Args:
            text: Input text to embed
            embedding_model_id: Optional embedding model ID (defaults to instance model_id)
            
        Returns:
            List of floats representing the embedding vector
        """
        try:
            model_id = embedding_model_id or self.model_id
            
            # Prepare request body for embedding models
            if "titan-embed" in model_id.lower():
                # Amazon Titan Embeddings format
                body = {
                    "inputText": text
                }
            elif "embed" in model_id.lower():
                # Generic embedding model format
                body = {
                    "inputText": text
                }
            else:
                # Default format for embedding models
                body = {
                    "inputText": text
                }
            
            # Invoke the embedding model
            response = self.bedrock_runtime.invoke_model(
                modelId=model_id,
                body=json.dumps(body)
            )
            
            response_body = json.loads(response['body'].read())
            
            # Extract embedding vector from response
            if "titan-embed" in model_id.lower():
                # Amazon Titan Embeddings response format
                embedding = response_body.get('embedding', [])
            elif "embedding" in response_body:
                embedding = response_body['embedding']
            else:
                # Try to find embedding in response
                embedding = response_body.get('embedding', response_body.get('vector', []))
            
            if not embedding:
                raise ValueError(f"Could not extract embedding from response: {response_body}")
            
            return list(embedding)
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            raise Exception(f"Bedrock embedding API error ({error_code}): {error_message}")
        except Exception as e:
            raise Exception(f"Failed to generate embedding: {str(e)}")


