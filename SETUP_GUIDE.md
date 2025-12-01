# AI Resource Finder - Setup Guide

Complete step-by-step setup instructions for the AI Resource Finder system.

## Prerequisites Checklist

- [ ] AWS Account with admin access
- [ ] PostgreSQL database (Supabase or RDS) with pgvector extension
- [ ] Python 3.11+ installed
- [ ] Terraform >= 1.0 installed
- [ ] AWS CLI configured
- [ ] Git (optional, for version control)

## Step 1: AWS Infrastructure Setup

### 1.1 Install Terraform

**Windows:**
```powershell
# Using Chocolatey
choco install terraform

# Or download from https://www.terraform.io/downloads
```

**Mac:**
```bash
brew install terraform
```

**Linux:**
```bash
# Download from https://www.terraform.io/downloads
# Or use package manager
sudo apt-get update && sudo apt-get install terraform
```

### 1.2 Configure Terraform

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`:
```hcl
aws_region = "us-east-1"
environment = "dev"
project_name = "ai-resource-finder"
s3_cv_bucket_name = "your-unique-bucket-name-ai-resource-finder-cvs"
lambda_function_name = "cv-ingestion-processor"
ses_from_email = "mg.ganeshguptha@gmail.com"
ses_admin_email = "mg.ganeshguptha@gmail.com"
bedrock_model_id = "anthropic.claude-3-haiku-20240307-v1:0"
```

**Important:** The S3 bucket name must be globally unique!

### 1.3 Initialize and Apply Terraform

```bash
terraform init
terraform plan  # Review what will be created
terraform apply  # Type 'yes' when prompted
```

This creates:
- S3 bucket for CV storage
- Lambda function for CV processing
- IAM roles and policies
- SES email identity

### 1.4 Post-Terraform Steps

#### a. Verify SES Email

1. Go to [AWS SES Console](https://console.aws.amazon.com/ses/)
2. Click "Verified identities" → "Create identity"
3. Select "Email address"
4. Enter your email: `mg.ganeshguptha@gmail.com`
5. Click "Create identity"
6. Check your email and click the verification link

#### b. Enable Bedrock Model Access

1. Go to [AWS Bedrock Console](https://console.aws.amazon.com/bedrock/)
2. Click "Model access" in left sidebar
3. Find "Claude 3 Haiku" or your model
4. Click "Enable" (one-time per account/region)

#### c. Create Lambda Deployment Package

```bash
cd ../ingestion

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r ../requirements.txt

# Create deployment package
# Note: This is a simplified approach - in production, use proper packaging
zip -r lambda_deployment.zip . \
    -x "*.pyc" "__pycache__/*" "*.git*" "venv/*" "*.zip"

# Upload to Lambda (or use Terraform)
aws lambda update-function-code \
  --function-name <your-lambda-function-name> \
  --zip-file fileb://lambda_deployment.zip
```

## Step 2: Database Setup

### 2.1 Create Database Schema

If using Supabase:
1. Go to your Supabase project
2. Navigate to SQL Editor
3. Copy contents of `database/schema.sql`
4. Run the SQL script

If using RDS or local PostgreSQL:
```bash
psql -h your-host -U your-user -d your-database -f database/schema.sql
```

### 2.2 Verify pgvector Extension

```sql
-- Check if pgvector is enabled
SELECT * FROM pg_extension WHERE extname = 'vector';

-- If not enabled, run:
CREATE EXTENSION IF NOT EXISTS vector;
```

### 2.3 Test Database Connection

```python
from utils.database import DatabaseManager
import os
    
db_manager = DatabaseManager(os.getenv("DATABASE_URL"))
print("✅ Database connection successful!")
```

## Step 3: Application Configuration

### 3.1 Create Environment File

Create a `.env` file in the project root:

```bash
# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-aws-access-key-id
AWS_SECRET_ACCESS_KEY=your-aws-secret-access-key

# AWS Bedrock
BEDROCK_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0

# AWS S3
S3_BUCKET_NAME=your-s3-bucket-name
S3_CV_PREFIX=cvs/

# AWS SES
SES_REGION=us-east-1
SES_FROM_EMAIL=mg.ganeshguptha@gmail.com
SES_ADMIN_EMAIL=mg.ganeshguptha@gmail.com

# Database
DATABASE_URL=postgresql://user:password@host:port/database
# OR use Supabase
SUPABASE_DATABASE_URL=postgresql://postgres:password@db.xxxxx.supabase.co:5432/postgres

# Embedding Model
EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
```

### 3.2 Get AWS Credentials

1. Go to [AWS IAM Console](https://console.aws.amazon.com/iam/)
2. Click "Users" → Your user → "Security credentials"
3. Click "Create access key"
4. Choose "Application running outside AWS"
5. Copy Access Key ID and Secret Access Key
6. Add to `.env` file

**Security Note:** Never commit `.env` to git!

## Step 4: Install Python Dependencies

```bash
# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

**Note:** The first run will download the embedding model (~90MB), which may take a few minutes.

## Step 5: Initial Data Setup

### 5.1 Add Training Courses

You can add courses via SQL or create a Python script:

```python
from utils.database import DatabaseManager
from ingestion.cv_embedder import CVEmbedder
import json

db_manager = DatabaseManager()
embedder = CVEmbedder()

# Example course
course_title = "Advanced Python Programming"
course_description = "Learn advanced Python concepts including decorators, generators, and async programming"
course_level = "advanced"
prerequisites = ["Python basics", "Object-oriented programming"]

# Generate embedding
embedding = embedder.generate_embedding(f"{course_title} {course_description}")

# Insert into database
query = """
    INSERT INTO training_courses (title, description, level, prerequisites, embedding)
    VALUES (%s, %s, %s, %s, %s)
"""
db_manager.execute_update(
    query,
    params=(course_title, course_description, course_level, prerequisites, embedding)
)
```

### 5.2 Upload Initial CVs

Upload CV PDFs to S3:

```bash
# Using AWS CLI
aws s3 cp candidate-cv.pdf s3://your-bucket-name/cvs/candidate-cv.pdf

# Or use AWS Console
# Go to S3 → your-bucket → cvs/ → Upload
```

The Lambda function will automatically process uploaded CVs.

## Step 6: Run the Application

```bash
# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Run Streamlit
streamlit run app.py
```

The application will open in your browser at `http://localhost:8501`

## Step 7: Testing

### 7.1 Test CV Ingestion

1. Upload a test CV to S3
2. Check CloudWatch logs for Lambda execution
3. Verify candidate appears in database:

```sql
SELECT name, email, extracted_skills FROM candidate_profiles;
```

### 7.2 Test Resource Matching

1. Open Streamlit app
2. Enter a requirement like: "Need a Python developer with AWS experience"
3. Click "Find Matching Resource"
4. Verify results show candidates with match scores

### 7.3 Test Allocation Workflow

1. Find a matching candidate
2. Click "Allocate Resource"
3. Fill in all required fields
4. Submit
5. Check emails (admin and associate should receive emails)

## Troubleshooting

### Issue: "Bedrock Access Denied"

**Solution:**
1. Go to Bedrock Console → Model access
2. Enable the model you're using
3. Wait a few minutes for propagation

### Issue: "SES Email Not Verified"

**Solution:**
1. Go to SES Console → Verified identities
2. Click on your email
3. Click "Send verification email"
4. Check inbox and click verification link

### Issue: "Lambda Not Triggering"

**Solution:**
1. Check S3 bucket notification configuration
2. Verify Lambda permission for S3 invoke
3. Check CloudWatch logs for errors
4. Ensure file is uploaded to `cvs/` prefix with `.pdf` extension

### Issue: "Database Connection Failed"

**Solution:**
1. Verify connection string format
2. Check network access (firewall, security groups)
3. Verify pgvector extension is enabled
4. Test connection with `psql` command

### Issue: "Import Errors"

**Solution:**
1. Ensure you're in the project root directory
2. Activate virtual environment
3. Verify all dependencies are installed: `pip install -r requirements.txt`
4. Check Python path includes project directory

## Next Steps

After setup is complete:

1. **Add More CVs**: Upload CVs to S3 for processing
2. **Add Training Courses**: Populate the training_courses table
3. **Customize Scoring**: Adjust weights in `.env` if needed
4. **Monitor Costs**: Set up AWS Cost Alerts
5. **Scale Up**: Add more CVs and courses as needed

## Production Deployment

For production:

1. **Use RDS** instead of Supabase (better for production)
2. **Set up CloudWatch Alarms** for monitoring
3. **Enable SES Production Access** (request from AWS)
4. **Use Secrets Manager** for sensitive credentials
5. **Set up CI/CD** for automated deployments
6. **Enable CloudFront** for Streamlit app (if hosting on EC2)

## Support

For issues:
- Check CloudWatch logs
- Review AWS service documentation
- Verify all environment variables are set
- Test each component individually

