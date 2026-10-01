output "repository_urls" {
  description = "short name => repository url"
  value       = { for key, repo in aws_ecr_repository.this : key => repo.repository_url }
}

output "repository_arns" {
  description = "short name => repository arn"
  value       = { for key, repo in aws_ecr_repository.this : key => repo.arn }
}
