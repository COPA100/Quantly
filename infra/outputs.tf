output "name_prefix" {
  description = "prefix shared by every resource in this stack"
  value       = local.name
}

output "vpc_id" {
  value = module.network.vpc_id
}

output "public_subnet_ids" {
  description = "handy for one-off `aws ecs run-task` calls (migrations, seeding)"
  value       = module.network.public_subnet_ids
}

output "s3_bucket" {
  value = module.s3.bucket_name
}

output "rds_address" {
  value = module.rds.address
}

output "redis_address" {
  value = module.redis.address
}

output "ecr_repository_urls" {
  description = "where to push the api and worker images"
  value       = module.ecr.repository_urls
}

output "alb_dns_name" {
  value = aws_lb.api.dns_name
}

output "api_url" {
  description = "base url of the api (point a cname at the alb when using a certificate)"
  value       = "${local.tls_enabled ? "https" : "http"}://${aws_lb.api.dns_name}"
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.this.name
}

output "api_service_name" {
  value = module.api.service_name
}

output "worker_service_name" {
  value = module.worker.service_name
}

output "api_task_definition_arn" {
  description = "used to run one-off tasks like `alembic upgrade head`"
  value       = module.api.task_definition_arn
}

output "api_security_group_id" {
  description = "security group for one-off api tasks, the only path into rds"
  value       = module.network.api_security_group_id
}
