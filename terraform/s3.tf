# S3 Bucket for CV Storage
resource "aws_s3_bucket" "cv_storage" {
  bucket = var.s3_cv_bucket_name
  
  tags = {
    Name        = "${var.project_name}-cv-storage"
    Description = "Storage for CV PDFs"
  }
}

# S3 Bucket Versioning
resource "aws_s3_bucket_versioning" "cv_storage_versioning" {
  bucket = aws_s3_bucket.cv_storage.id
  
  versioning_configuration {
    status = "Enabled"
  }
}

# S3 Bucket Server-Side Encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "cv_storage_encryption" {
  bucket = aws_s3_bucket.cv_storage.id
  
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# S3 Bucket Public Access Block (keep private)
resource "aws_s3_bucket_public_access_block" "cv_storage_pab" {
  bucket = aws_s3_bucket.cv_storage.id
  
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# S3 Bucket Notification for Lambda Trigger
resource "aws_s3_bucket_notification" "cv_storage_notification" {
  bucket = aws_s3_bucket.cv_storage.id
  
  lambda_function {
    lambda_function_arn = aws_lambda_function.cv_processor.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "cvs/"
    filter_suffix       = ".pdf"
  }
  
  depends_on = [aws_lambda_permission.allow_s3_invoke]
}

# Output S3 bucket name
output "s3_bucket_name" {
  description = "S3 bucket name for CV storage"
  value       = aws_s3_bucket.cv_storage.id
}

output "s3_bucket_arn" {
  description = "S3 bucket ARN"
  value       = aws_s3_bucket.cv_storage.arn
}

