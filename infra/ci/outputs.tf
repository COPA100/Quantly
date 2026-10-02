output "state_bucket" {
  description = "pass to `terraform init -backend-config=bucket=...`, and set as the TF_STATE_BUCKET repo variable"
  value       = aws_s3_bucket.state.bucket
}

output "plan_role_arn" {
  description = "set as the AWS_PLAN_ROLE_ARN repo variable"
  value       = aws_iam_role.plan.arn
}

output "deploy_role_arn" {
  description = "set as the AWS_DEPLOY_ROLE_ARN repo variable"
  value       = aws_iam_role.deploy.arn
}
