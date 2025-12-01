# AI Resource Finder

AI-powered system that identifies the top 3 most suitable internal associates for any given resource requirement. It extracts skills from CVs, performs semantic search with LLM-enhanced scoring, identifies skill gaps, recommends appropriate training programs, and supports allocation workflows via email.

## Features

- 🔍 **Hybrid AI Matching**: Combines vector search, LLM re-ranking, and rule-based scoring
- 📊 **Transparent Scoring**: Match percentage with skill-level breakdown and evidence
- ⚠️ **Skill Gap Detection**: Identifies missing or insufficient skills
- 📚 **Training Recommendations**: Suggests up to 3 training programs to close gaps
- 📧 **Allocation Workflow**: Email notifications for allocation requests
- 🤖 **Agentic Architecture**: Orchestrator, ResourceAgent, and CourseAgent
- 💰 **Cost-Effective**: Uses small Bedrock models and free local embeddings

## Architecture

```
User Requirement
    ↓
Orchestrator Agent
    ├──→ Requirement Parser (Bedrock)
    ├──→ ResourceAgent
    │     ├──→ Vector Search (pgvector)
    │     ├──→ LLM Re-ranking (Bedrock)
    │     └──→ Rule-based Scoring
    └──→ CourseAgent (for each candidate)
          ├──→ Vector Search Courses
          ├──→ LLM Re-ranking
          └──→ Rule Filtering
```

## Prerequisites

1. **AWS Account** with:
   - Bedrock access (Claude 3 Haiku model enabled)
   - S3 bucket for CV storage
   - SES configured (email verified)
   - IAM credentials

2. **PostgreSQL Database** with:
   - pgvector extension
   - Connection string

3. **Python 3.11+**

4. **Terraform** (for infrastructure setup)

## Quick Start

### 1. Set Up AWS Infrastructure

See [terraform/README.md](terraform/README.md) for detailed instructions.

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values
terraform init
terraform plan
terraform apply
```

### 2. Set Up Database Schema

```bash
# Connect to your PostgreSQL database
psql -h your-host -U your-user -d your-database -f database/schema.sql
```

### 3. Configure Environment Variables

```bash
cp .env.example .env
# Edit .env with your AWS credentials and database URL
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Run the Application

```bash
streamlit run app.py
```

## Configuration

### Environment Variables

See `.env.example` for all available configuration options.

**Required:**
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `S3_BUCKET_NAME`
- `DATABASE_URL` or `SUPABASE_DATABASE_URL`

**Optional:**
- `BEDROCK_MODEL_ID` (default: Claude 3 Haiku)
- `AWS_REGION` (default: us-east-1)
- Matching weights and thresholds

### Scoring Formula

**Final Candidate Score:**
```
Final Score = 0.15 × Vector Search + 0.25 × LLM Score + 0.60 × Rule Score
Match % = round(Final Score × 100)
```

**Course Recommendation Score:**
```
Course Score = 0.30 × Vector + 0.50 × LLM + 0.20 × Rule
```

## Usage

### 1. Upload CVs to S3

Upload CV PDFs to your S3 bucket under the `cvs/` prefix. The Lambda function will automatically:
- Extract text from PDF
- Extract skills and experience using Bedrock
- Generate embeddings
- Store in PostgreSQL

### 2. Add Training Courses

Insert training courses into the `training_courses` table:

```sql
INSERT INTO training_courses (title, description, level, prerequisites, embedding)
VALUES (
    'Advanced Python Programming',
    'Learn advanced Python concepts...',
    'advanced',
    ARRAY['Python basics', 'OOP'],
    %s::vector
);
```

### 3. Search for Resources

1. Enter a resource requirement in the Streamlit UI
2. Click "Find Matching Resource"
3. Review top 3 candidates with:
   - Match percentage
   - Matched skills
   - Skill gaps
   - Recommended courses
4. Click "Allocate Resource" to submit allocation request

## Project Structure

```
ai-resource-finder/
├── app.py                      # Streamlit main application
├── config.py                   # Configuration management
├── requirements.txt            # Python dependencies
├── .env.example                # Environment variables template
├── database/
│   └── schema.sql              # Database schema
├── agents/
│   ├── orchestrator.py         # Main orchestrator agent
│   ├── resource_agent.py       # Candidate matching agent
│   └── course_agent.py         # Training recommendation agent
├── services/
│   ├── requirement_parser.py  # Bedrock requirement parsing
│   ├── cv_processor.py         # CV extraction
│   ├── matching_engine.py     # Hybrid matching logic
│   ├──         # Skill gap detection
│   └── email_service.py       # AWS SES integration
├── ingestion/
│   ├── lambda_handler.py      # S3-triggered Lambda
│   ├── pdf_extractor.py       # PDF text extraction
│   └── cv_embedder.py         # CV embedding generation
├── models/
│   ├── candidate.py           # Candidate data models
│   ├── course.py             # Course data models
│   └── allocation.py         # Allocation request models
├── utils/
│   ├── database.py           # DB connection utilities
│   └── bedrock_client.py     # AWS Bedrock client wrapper
└── terraform/
    ├── main.tf               # Terraform main file
    ├── variables.tf          # Terraform variables
    ├── s3.tf                 # S3 bucket configuration
    ├── lambda.tf             # Lambda function configuration
    ├── ses.tf                # SES configuration
    └── README.md             # Infrastructure setup guide
```

## Cost Estimate

### Pilot Phase (30 CVs, 10 courses, ~50 searches/month)
- **Monthly Cost**: $3-6
  - AWS Bedrock: $3-5
  - S3: $0.001
  - Lambda: $0 (free tier)
  - SES: $0.01
  - Database: $0 (Supabase free tier)
  - Streamlit: $0 (free tier)

### Production Phase (500 CVs, 500 courses, ~500 searches/month)
- **Monthly Cost**: $90-200
  - AWS Bedrock: $75-150
  - S3: $0.02
  - Lambda: $0-0.50
  - SES: $0.10
  - Database: $15-25 (Supabase Pro or RDS)
  - Streamlit: $0-20

See cost optimization strategies in the plan document.

## Development

### Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
export DATABASE_URL=your-db-url

# Run Streamlit
streamlit run app.py
```

### Testing CV Ingestion

```bash
# Upload a test CV to S3
aws s3 cp test-cv.pdf s3://your-bucket/cvs/test-cv.pdf

# Check Lambda logs
aws logs tail /aws/lambda/your-lambda-function-name --follow
```

## Troubleshooting

### Bedrock Access Denied
- Enable model access in Bedrock Console
- Check IAM permissions for `bedrock:InvokeModel`

### Lambda Not Triggering
- Verify S3 bucket notification configuration
- Check Lambda permission for S3 invoke
- Review CloudWatch logs

### SES Email Not Sending
- Verify email address in SES Console
- Check if account is in SES sandbox
- Request production access if needed

### Database Connection Issues
- Verify connection string format
- Check pgvector extension is enabled
- Ensure network access is allowed

## License

[Specify your license here]

## Support

For issues and questions:
- Check the Troubleshooting section
- Review AWS service documentation
- Ensure all environment variables are correctly set

