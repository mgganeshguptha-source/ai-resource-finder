output "infrastructure_summary" {
  description = "Summary of created infrastructure"
  value = {
    s3_bucket_name        = aws_s3_bucket.cv_storage.id
    lambda_function_name  = aws_lambda_function.cv_processor.function_name
    lambda_function_arn   = aws_lambda_function.cv_processor.arn
    ses_from_email       = aws_ses_email_identity.from_email.email
    aws_region           = var.aws_region
  }
}

output "next_steps" {
  description = "Next steps after infrastructure creation"
  value = <<-EOT
    1. Verify SES email: Go to AWS SES Console and verify ${var.ses_from_email}
    2. Enable Bedrock model access: Go to Bedrock Console > Model access > Enable ${var.bedrock_model_id}
    3. Create Lambda deployment package: See deployment instructions in README
    4. Update Lambda function code: Upload the deployment package
    5. Test CV upload: Upload a test PDF to s3://${aws_s3_bucket.cv_storage.id}/cvs/
    6. Set environment variables in your application:
       - AWS_REGION=${var.aws_region}
       - S3_BUCKET_NAME=${aws_s3_bucket.cv_storage.id}
       - DATABASE_URL=<your-database-url>
  EOT
}

