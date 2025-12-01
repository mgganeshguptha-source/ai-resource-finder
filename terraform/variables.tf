variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "ai-resource-finder"
}

variable "s3_cv_bucket_name" {
  description = "S3 bucket name for CV storage (must be globally unique)"
  type        = string
  default     ="ai-resource-finder-cvs-v1"
}

variable "lambda_function_name" {
  description = "Lambda function name for CV ingestion"
  type        = string
  default     = "cv-ingestion-processor"
}

variable "ses_from_email" {
  description = "Email address for SES (must be verified)"
  type        = string
  default     = "mg.ganeshguptha@gmail.com"
}

variable "ses_admin_email" {
  description = "Admin email for allocation notifications"
  type        = string
  default     = "mg.ganeshguptha@gmail.com"
}

variable "bedrock_model_id" {
  description = "Bedrock model ID to use"
  type        = string
  default     = "anthropic.claude-3-7-sonnet-20250219-v1:0"
}

variable "database_url" {
  description = "PostgreSQL database connection URL (optional, can be set as environment variable)"
  type        = string
  default     = "postgresql://postgres.qxkeklaxdkgkzzcgqdnm:Ganesh2tcscom@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres"
  sensitive   = true
}

