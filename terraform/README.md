# AWS Infrastructure Setup with Terraform

This directory contains Terraform scripts to provision AWS infrastructure for the AI Resource Finder.

## Prerequisites

1. **AWS Account** with appropriate permissions
2. **Terraform** installed (>= 1.0)
3. **AWS CLI** configured with credentials
4. **Python 3.11+** for Lambda function

## Quick Start

### 1. Configure Variables

Copy the example variables file and customize:

```bash
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` with your values:
- `s3_cv_bucket_name`: Must be globally unique
- `ses_from_email`: Your verified email address
- `database_url`: PostgreSQL connection string (or set as environment variable)

### 2. Initialize Terraform

```bash
cd terraform
terraform init
```

### 3. Review Plan

```bash
terraform plan
```

This will show what resources will be created:
- S3 bucket for CV storage
- Lambda function for CV processing
- IAM roles and policies
- SES email identity

### 4. Apply Infrastructure

```bash
terraform apply
```

Type `yes` when prompted to create the resources.

### 5. Post-Deployment Steps

After infrastructure is created, you need to:

#### a. Verify SES Email

1. Go to [AWS SES Console](https://console.aws.amazon.com/ses/)
2. Navigate to "Verified identities"
3. Click on your email address
4. Click "Send verification email" or verify via DNS

#### b. Enable Bedrock Model Access

1. Go to [AWS Bedrock Console](https://console.aws.amazon.com/bedrock/)
2. Navigate to "Model access" in left sidebar
3. Find your model (e.g., `anthropic.claude-3-haiku-20240307-v1:0`)
4. Click "Enable" (one-time per account/region)

#### c. Create Lambda Deployment Package

```bash
cd ../ingestion
pip install -r requirements.txt -t .
zip -r lambda_deployment.zip . -x "*.pyc" "__pycache__/*" "*.git*"
```

Or use the provided script:

```bash
cd terraform
./package_lambda.sh  # Create this script if needed
```

#### d. Update Lambda Function Code

```bash
aws lambda update-function-code \
  --function-name <lambda-function-name> \
  --zip-file fileb://../ingestion/lambda_deployment.zip
```

Or use Terraform (if you add the zip file to the resource):

```bash
terraform apply
```

## Infrastructure Components

### S3 Bucket
- **Purpose**: Store CV PDF files
- **Prefix**: `cvs/`
- **Encryption**: AES256 server-side encryption
- **Access**: Private (no public access)
- **Trigger**: Automatically triggers Lambda on PDF upload

### Lambda Function
- **Purpose**: Process CVs when uploaded to S3
- **Runtime**: Python 3.11
- **Timeout**: 5 minutes
- **Memory**: 512 MB
- **Permissions**: 
  - Read from S3 bucket
  - Invoke Bedrock models
  - Send emails via SES

### IAM Roles
- **Lambda Execution Role**: Basic execution + custom policies for S3, Bedrock, SES

### SES (Simple Email Service)
- **Purpose**: Send allocation and training emails
- **Configuration**: Email identity for sending emails
- **Note**: Must verify email address manually

### Bedrock
- **Model**: Claude 3 Haiku (cost-effective)
- **Access**: Must enable model access in Bedrock Console
- **Region**: Same as other resources

## Cost Optimization

- **S3**: First 5GB free, then $0.023/GB/month
- **Lambda**: Free tier: 1M requests/month, 400K GB-seconds
- **SES**: Free tier: 62K emails/month (in sandbox)
- **Bedrock**: Pay per token (see cost estimate in main README)

## Troubleshooting

### Lambda Function Not Triggering

1. Check S3 bucket notification configuration
2. Verify Lambda permission for S3 invoke
3. Check CloudWatch logs for errors

### Bedrock Access Denied

1. Ensure model access is enabled in Bedrock Console
2. Check IAM policy allows `bedrock:InvokeModel`
3. Verify model ID is correct

### SES Email Not Sending

1. Verify email address in SES Console
2. Check if account is in SES sandbox (limited to verified emails)
3. Request production access if needed

## Destroying Infrastructure

To remove all resources:

```bash
terraform destroy
```

**Warning**: This will delete:
- S3 bucket and all CVs
- Lambda function
- IAM roles
- SES configuration

Make sure to backup any important data first!

## Variables Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `aws_region` | AWS region | `us-east-1` |
| `environment` | Environment name | `dev` |
| `s3_cv_bucket_name` | S3 bucket name (required) | - |
| `lambda_function_name` | Lambda function name | `cv-ingestion-processor` |
| `ses_from_email` | SES sender email | `mg.ganeshguptha@gmail.com` |
| `bedrock_model_id` | Bedrock model ID | `anthropic.claude-3-haiku-20240307-v1:0` |

## Security Notes

1. **S3 Bucket**: Private by default, no public access
2. **IAM Roles**: Follow principle of least privilege
3. **Secrets**: Never commit `terraform.tfvars` to git
4. **Database URL**: Store in environment variables or AWS Secrets Manager

## Next Steps

After infrastructure is set up:

1. Configure your application with AWS credentials
2. Set up database schema (run `database/schema.sql`)
3. Test CV upload to S3
4. Monitor Lambda logs in CloudWatch
5. Test email sending via SES

