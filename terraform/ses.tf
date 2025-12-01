# SES Configuration Set (optional, for tracking)
resource "aws_ses_configuration_set" "email_config" {
  name = "${var.project_name}-email-config"
}

# SES Identity (Email Address)
# Note: Email verification must be done manually in AWS Console
# This resource just documents the requirement
resource "aws_ses_email_identity" "from_email" {
  email = var.ses_from_email
}

# SES Domain Identity (optional, if using custom domain)
# Uncomment if you want to use a custom domain
# resource "aws_ses_domain_identity" "domain" {
#   domain = "example.com"
# }

# Output SES email
output "ses_from_email" {
  description = "SES verified email address"
  value       = aws_ses_email_identity.from_email.email
}

output "ses_verification_instructions" {
  description = "Instructions for email verification"
  value       = "Go to AWS SES Console and verify the email address: ${var.ses_from_email}"
}

