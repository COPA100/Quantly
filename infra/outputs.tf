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
