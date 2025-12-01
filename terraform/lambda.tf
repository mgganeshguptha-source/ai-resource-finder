# Lambda Execution Role
resource "aws_iam_role" "lambda_execution_role" {
  name = "${var.project_name}-lambda-execution-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
  
  tags = {
    Name = "${var.project_name}-lambda-execution-role"
  }
}

# Lambda Execution Policy (attach AWS managed policy)
resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Lambda Policy for S3, Bedrock, and SES access
resource "aws_iam_role_policy" "lambda_custom_policy" {
  name = "${var.project_name}-lambda-custom-policy"
  role = aws_iam_role.lambda_execution_role.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]
        Resource = "${aws_s3_bucket.cv_storage.arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel"
        ]
        Resource = "arn:aws:bedrock:${var.aws_region}::foundation-model/${var.bedrock_model_id}"
      },
      {
        Effect = "Allow"
        Action = [
          "ses:SendEmail",
          "ses:SendRawEmail"
        ]
        Resource = "*"
      }
    ]
  })
}

# Lambda Function for CV Processing
resource "aws_lambda_function" "cv_processor" {
  filename         = "${path.module}/../ingestion/lambda_deployment.zip"
  function_name    = "${var.project_name}-${var.lambda_function_name}"
  role            = aws_iam_role.lambda_execution_role.arn
  handler         = "lambda_handler.lambda_handler"
  runtime         = "python3.11"
  timeout         = 300  # 5 minutes
  memory_size     = 512
  
  environment {
    variables = {
      DATABASE_URL           = var.database_url != "" ? var.database_url : ""
      BEDROCK_MODEL_ID       = var.bedrock_model_id
      # AWS_REGION             = var.aws_region
      S3_BUCKET_NAME         = aws_s3_bucket.cv_storage.id
      S3_CV_PREFIX           = "cvs/"
      EMBEDDING_MODEL_NAME   = "sentence-transformers/all-MiniLM-L6-v2"
    }
  }
  
  # Note: You'll need to create the deployment package separately
  # See deployment instructions in README
  
  tags = {
    Name = "${var.project_name}-cv-processor"
  }
}

# Lambda Permission for S3 to invoke
resource "aws_lambda_permission" "allow_s3_invoke" {
  statement_id  = "AllowExecutionFromS3Bucket"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.cv_processor.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.cv_storage.arn
}

# Output Lambda function name
output "lambda_function_name" {
  description = "Lambda function name"
  value       = aws_lambda_function.cv_processor.function_name
}

output "lambda_function_arn" {
  description = "Lambda function ARN"
  value       = aws_lambda_function.cv_processor.arn
}

