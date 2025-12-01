"""
AWS Lambda handler for S3-triggered CV ingestion
"""

import json
import boto3
import sys
import os
from typing import Dict, Any

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingestion.pdf_extractor import PDFExtractor
from ingestion.cv_embedder import CVEmbedder
from services.cv_processor import CVProcessor
from utils.database import DatabaseManager
from utils.bedrock_client import BedrockClient
from config import Config


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for processing CVs uploaded to S3
    
    Args:
        event: Lambda event containing S3 trigger information
        context: Lambda context
        
    Returns:
        Response dictionary
    """
    config = Config()
    s3_client = boto3.client('s3', region_name=config.aws_region)
    
    try:
        # Parse S3 event
        for record in event.get('Records', []):
            bucket_name = record['s3']['bucket']['name']
            object_key = record['s3']['object']['key']
            
            # Only process files in CV prefix
            if not object_key.startswith(config.s3_cv_prefix):
                continue
            
            print(f"Processing CV: s3://{bucket_name}/{object_key}")
            
            # Download PDF from S3
            response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
            pdf_bytes = response['Body'].read()
            
            # Extract text from PDF
            pdf_extractor = PDFExtractor()
            cv_text = pdf_extractor.extract_text(pdf_bytes)
            
            # Extract name and email from CV (simple extraction)
            # In production, you might want more sophisticated extraction
            name = _extract_name_from_cv(cv_text)
            email = _extract_email_from_cv(cv_text)
            
            if not email:
                print(f"⚠️ Could not extract email from CV: {object_key}")
                continue
            
            # Process CV with Bedrock
            bedrock_client = BedrockClient(
                region_name=config.aws_region,
                model_id=config.bedrock_model_id
            )
            cv_processor = CVProcessor(bedrock_client, config)
            candidate_profile = cv_processor.process_cv(
                cv_text=cv_text,
                name=name,
                email=email,
                cv_s3_key=object_key,
                cv_s3_url=f"s3://{bucket_name}/{object_key}"
            )
            
            # Generate embedding
            embedder = CVEmbedder(
                config.embedding_model_name,
                bedrock_client=bedrock_client if config.embedding_model_name.startswith("amazon.titan") else None
            )
            embedding = embedder.generate_embedding(cv_text)
            candidate_profile.embedding = embedding
            
            # Store in database
            db_manager = DatabaseManager(config.db_connection_string)
            _store_candidate_profile(db_manager, candidate_profile)
            
            print(f"✅ Successfully processed CV for {candidate_profile.email}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'CV processed successfully'})
        }
    
    except Exception as e:
        print(f"❌ Error processing CV: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


def _extract_name_from_cv(cv_text: str) -> str:
    """Extract candidate name from CV text (simple heuristic)"""
    lines = cv_text.split('\n')[:10]  # Check first 10 lines
    for line in lines:
        line = line.strip()
        if len(line) > 3 and len(line) < 50 and not line.lower().startswith(('email', 'phone', 'address')):
            # Likely a name if it's a reasonable length and not a label
            return line
    return "Unknown"


def _extract_email_from_cv(cv_text: str) -> str:
    """Extract email from CV text"""
    import re
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    matches = re.findall(email_pattern, cv_text)
    return matches[0] if matches else ""


def _store_candidate_profile(db_manager: DatabaseManager, profile) -> None:
    """Store candidate profile in database"""
    import json
    
    query = """
        INSERT INTO candidate_profiles 
            (name, email, raw_text, extracted_skills, years_of_experience, 
             domain_tags, embedding, cv_s3_key, cv_s3_url)
        VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s)
        ON CONFLICT (email) 
        DO UPDATE SET
            name = EXCLUDED.name,
            raw_text = EXCLUDED.raw_text,
            extracted_skills = EXCLUDED.extracted_skills,
            years_of_experience = EXCLUDED.years_of_experience,
            domain_tags = EXCLUDED.domain_tags,
            embedding = EXCLUDED.embedding,
            cv_s3_key = EXCLUDED.cv_s3_key,
            cv_s3_url = EXCLUDED.cv_s3_url,
            updated_at = NOW()
    """
    
    params = (
        profile.name,
        profile.email,
        profile.raw_text,
        json.dumps(profile.extracted_skills),
        json.dumps(profile.years_of_experience),
        profile.domain_tags,
        profile.embedding,
        profile.cv_s3_key,
        profile.cv_s3_url
    )
    
    db_manager.execute_update(query, params)


