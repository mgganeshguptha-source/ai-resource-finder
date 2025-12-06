"""
AWS Lambda handler for S3-triggered CV ingestion
"""

import json
import boto3
from botocore.exceptions import ClientError
import sys
import os
import urllib.parse
import re
import hashlib
from typing import Dict, Any, Optional

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
            # Extract bucket name and object key from S3 event
            # S3 event structure can vary, handle both formats
            if 's3' in record:
                bucket_name = record['s3']['bucket']['name']
                # Object key may be URL-encoded in S3 events, decode it
                object_key = urllib.parse.unquote_plus(record['s3']['object']['key'])
            else:
                # Alternative event format
                bucket_name = record.get('bucket', {}).get('name')
                object_key = urllib.parse.unquote_plus(record.get('object', {}).get('key', ''))
            
            if not bucket_name or not object_key:
                print(f"⚠️ Invalid S3 event record: {json.dumps(record)}")
                continue
            
            # Only process files in CV prefix
            if not object_key.startswith(config.s3_cv_prefix):
                print(f"⚠️ Skipping file (not in CV prefix): {object_key}")
                continue
            
            print(f"Processing CV: s3://{bucket_name}/{object_key}")
            
            # Download PDF from S3
            try:
                response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
                pdf_bytes = response['Body'].read()
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                if error_code == 'NoSuchKey':
                    print(f"❌ S3 object not found: s3://{bucket_name}/{object_key}")
                    print(f"   Event record: {json.dumps(record, default=str)}")
                    print(f"   Error: {str(e)}")
                else:
                    print(f"❌ S3 error ({error_code}): {str(e)}")
                    print(f"   Bucket: {bucket_name}, Key: {object_key}")
                continue
            except Exception as e:
                print(f"❌ Error downloading from S3: {str(e)}")
                print(f"   Bucket: {bucket_name}, Key: {object_key}")
                print(f"   Event record: {json.dumps(record, default=str)}")
                continue
            
            # Extract text from PDF
            pdf_extractor = PDFExtractor()
            cv_text = pdf_extractor.extract_text(pdf_bytes)
            
            # Clean text: remove null bytes and other problematic characters
            cv_text = _clean_cv_text(cv_text)
            
            # Extract email first (needed for name extraction fallback)
            email = _extract_email_from_cv(cv_text)
            
            # If email not found, create a unique identifier based on S3 key
            # This ensures we can still process CVs without emails while maintaining DB uniqueness
            if not email:
                print(f"⚠️ Could not extract email from CV: {object_key}")
                # Create unique identifier: "unknown-{hash_of_s3_key}@example.com"
                # Using example.com as it's a reserved domain that passes email validation
                key_hash = hashlib.md5(object_key.encode()).hexdigest()[:8]
                email = f"unknown-{key_hash}@example.com"
                print(f"   Using placeholder email: {email}")
            
            # Extract name using 3-step approach (with email for fallback)
            name = _extract_name_from_cv(cv_text, email)
            
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


def _clean_cv_text(cv_text: str) -> str:
    """
    Clean CV text by removing problematic characters that cause database errors
    
    Args:
        cv_text: Raw CV text content
        
    Returns:
        Cleaned CV text
    """
    if not cv_text:
        return ""
    
    # Remove null bytes (0x00) - PostgreSQL doesn't allow these
    cv_text = cv_text.replace('\x00', '')
    
    # Remove other control characters except newlines, tabs, and carriage returns
    # Keep: \n (0x0A), \t (0x09), \r (0x0D)
    # Remove/replace: other control characters (0x01-0x1F except 0x09, 0x0A, 0x0D)
    cleaned = []
    for char in cv_text:
        code = ord(char)
        # Keep printable characters
        if char.isprintable():
            cleaned.append(char)
        # Keep newlines, tabs, and carriage returns
        elif code in (0x09, 0x0A, 0x0D):
            cleaned.append(char)
        # Replace other control characters (0x01-0x1F) with space
        elif 0x01 <= code <= 0x1F:
            cleaned.append(' ')
        # Keep everything else (extended ASCII, Unicode, etc.)
        else:
            cleaned.append(char)
    
    return ''.join(cleaned)


def _extract_name_from_cv(cv_text: str, email: Optional[str] = None) -> str:
    """
    Extract candidate name from CV text using a 3-step approach:
    1. Heuristic on first page lines
    2. "Name:" pattern matching
    3. Fallback to email username
    
    Args:
        cv_text: Raw CV text content
        email: Optional email address (if already extracted)
        
    Returns:
        Extracted candidate name
    """
    # Step 1: Try heuristic on first page lines
    name = _extract_name_heuristic(cv_text)
    if name:
        return name
    
    # Step 2: Try "Name:" pattern
    name = _extract_name_from_pattern(cv_text)
    if name:
        return name
    
    # Step 3: Fallback to email username
    if not email:
        email = _extract_email_from_cv(cv_text)
    if email:
        name = _extract_name_from_email(email)
        if name:
            return name
    
    return "Unknown"


def _extract_name_heuristic(cv_text: str) -> Optional[str]:
    """
    Step 1: Extract name using heuristics on first page lines
    
    Args:
        cv_text: Raw CV text content
        
    Returns:
        Extracted name or None
    """
    # Get first page (first 15 non-empty lines)
    lines = [line.strip() for line in cv_text.split('\n') if line.strip()][:15]
    
    # Labels to skip
    skip_labels = [
        'resume', 'curriculum vitae', 'cv', 'profile', 'career objective',
        'professional summary', 'contact', 'email', 'mobile', 'phone', 'address'
    ]
    
    for line in lines:
        line_lower = line.lower()
        
        # Skip lines that start with labels
        if any(line_lower.startswith(label) for label in skip_labels):
            continue
        
        # Skip lines containing email, phone, or URLs
        if '@' in line or 'www.' in line_lower or 'linkedin' in line_lower or 'github' in line_lower:
            continue
        
        # Skip lines with long numbers (likely phone numbers)
        if re.search(r'\d{8,}', line):
            continue
        
        # Clean the line
        cleaned = _clean_name_line(line)
        
        # Check if it looks like a name
        if _looks_like_name(cleaned):
            return cleaned
    
    return None


def _clean_name_line(line: str) -> str:
    """
    Clean a line to extract potential name
    
    Args:
        line: Raw line text
        
    Returns:
        Cleaned name string
    """
    # Remove bullets and extra punctuation at start/end
    line = re.sub(r'^[\s\-\•\*\>\<]+', '', line)
    line = re.sub(r'[\s\-\•\*\>\<]+$', '', line)
    
    # Remove angle brackets (e.g., "<<Soniya Loganathan>>" -> "Soniya Loganathan")
    line = re.sub(r'^[<>]+', '', line)
    line = re.sub(r'[<>]+$', '', line)
    
    # Remove common prefixes (Mr, Ms, Dr, etc.)
    line = re.sub(r'^(mr|mrs|ms|miss|dr|prof)\.?\s+', '', line, flags=re.IGNORECASE)
    
    # Remove extra whitespace
    line = ' '.join(line.split())
    
    return line.strip()


def _looks_like_name(text: str) -> bool:
    """
    Check if text looks like an Indian name
    
    Args:
        text: Text to check
        
    Returns:
        True if text looks like a name
    """
    if not text or len(text) < 2:
        return False
    
    # Split into words
    words = text.split()
    
    # Should have 1-4 words
    if len(words) < 1 or len(words) > 4:
        return False
    
    # Check each word
    for word in words:
        # Remove dots and hyphens for validation (e.g., "A. Kumar", "Sai-Teja")
        word_clean = re.sub(r'[.\-]', '', word)
        
        # Should be 2-20 letters
        if not re.match(r'^[a-zA-Z]{2,20}$', word_clean):
            return False
    
    # Should have few or no digits/special symbols overall
    digit_count = len(re.findall(r'\d', text))
    if digit_count > 2:  # Allow for initials like "A. Kumar" or years
        return False
    
    return True


def _extract_name_from_pattern(cv_text: str) -> Optional[str]:
    """
    Step 2: Extract name from "Name:" patterns
    
    Args:
        cv_text: Raw CV text content
        
    Returns:
        Extracted name or None
    """
    # Search first 30 lines
    lines = [line.strip() for line in cv_text.split('\n')[:30] if line.strip()]
    
    # Pattern: "Name : Ravi Kumar Gupta" or "NAME- Ravi K Gupta"
    pattern = r'(?i)^\s*name\s*[:\-]\s*(.+)$'
    
    for line in lines:
        match = re.match(pattern, line)
        if match:
            name_candidate = match.group(1).strip()
            cleaned = _clean_name_line(name_candidate)
            if _looks_like_name(cleaned):
                return cleaned
    
    return None


def _extract_name_from_email(email: str) -> Optional[str]:
    """
    Step 3: Extract name from email username (fallback)
    
    Args:
        email: Email address
        
    Returns:
        Extracted name or None
    """
    if not email or '@' not in email:
        return None
    
    # Get username part (before @)
    username = email.split('@')[0]
    
    # Replace separators with space
    username = re.sub(r'[._\-]', ' ', username)
    
    # Split into tokens
    tokens = username.split()
    
    # Clean each token: remove digits, keep only letters
    cleaned_tokens = []
    for token in tokens:
        # Remove digits
        token_clean = re.sub(r'\d', '', token)
        # Keep only letters
        token_clean = re.sub(r'[^a-zA-Z]', '', token_clean)
        # Skip empty or very short tokens
        if len(token_clean) >= 2:
            cleaned_tokens.append(token_clean)
    
    # Take first 2-3 tokens (to avoid picking up too much)
    if cleaned_tokens:
        name_tokens = cleaned_tokens[:3]
        # Capitalize first letter of each token
        name = ' '.join(token.capitalize() for token in name_tokens)
        return name
    
    return None


def _extract_email_from_cv(cv_text: str) -> str:
    """Extract email from CV text"""
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    matches = re.findall(email_pattern, cv_text)
    return matches[0] if matches else ""


def _store_candidate_profile(db_manager: DatabaseManager, profile) -> None:
    """Store candidate profile in database"""
    import json
    
    query = """
        INSERT INTO candidate_profiles 
            (name, email, raw_text, extracted_skills, years_of_experience, 
             domain_tags, experience_summary, embedding, cv_s3_key, cv_s3_url)
        VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s)
        ON CONFLICT (email) 
        DO UPDATE SET
            name = EXCLUDED.name,
            raw_text = EXCLUDED.raw_text,
            extracted_skills = EXCLUDED.extracted_skills,
            years_of_experience = EXCLUDED.years_of_experience,
            domain_tags = EXCLUDED.domain_tags,
            experience_summary = EXCLUDED.experience_summary,
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
        profile.experience_summary,
        profile.embedding,
        profile.cv_s3_key,
        profile.cv_s3_url
    )
    
    db_manager.execute_update(query, params)


