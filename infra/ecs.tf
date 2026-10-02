resource "aws_ecs_cluster" "this" {
  name = local.name

  # container insights bills per metric, not worth it for a demo stack
  setting {
    name  = "containerInsights"
    value = "disabled"
  }
}

resource "aws_ecs_cluster_capacity_providers" "this" {
  cluster_name       = aws_ecs_cluster.this.name
  capacity_providers = ["FARGATE", "FARGATE_SPOT"]
}

# ---- secrets ----
# kept in ssm parameter store (free for standard params) and injected by ecs at
# task start, so they never appear in a task definition or a tfvars file.

resource "random_password" "jwt_secret" {
  length  = 64
  special = false
}

resource "aws_ssm_parameter" "database_url" {
  name  = "/${var.project}/${var.environment}/database_url"
  type  = "SecureString"
  value = module.rds.database_url
}

resource "aws_ssm_parameter" "jwt_secret" {
  name  = "/${var.project}/${var.environment}/jwt_secret"
  type  = "SecureString"
  value = random_password.jwt_secret.result
}

locals {
  # settings both services read (see backend/common/config.py)
  common_environment = {
    QUANTLY_ENVIRONMENT = var.environment

    QUANTLY_S3_BUCKET = module.s3.bucket_name
    QUANTLY_S3_REGION = var.aws_region
    # blank out the local dev defaults so boto3 talks to real s3 and picks up
    # credentials from the task role
    QUANTLY_S3_ENDPOINT_URL       = ""
    QUANTLY_AWS_ACCESS_KEY_ID     = ""
    QUANTLY_AWS_SECRET_ACCESS_KEY = ""

    # same db split as local dev: 0 price cache, 1 celery broker, 2 results
    QUANTLY_REDIS_URL             = "${module.redis.url}/0"
    QUANTLY_CELERY_BROKER_URL     = "${module.redis.url}/1"
    QUANTLY_CELERY_RESULT_BACKEND = "${module.redis.url}/2"
  }
}

# ---- api: small, stateless, always-on fargate ----
module "api" {
  source = "./modules/ecs-service"

  name        = "${local.name}-api"
  cluster_arn = aws_ecs_cluster.this.arn
  image       = "${module.ecr.repository_urls["api"]}:${var.image_tag}"

  cpu           = var.api_cpu
  memory        = var.api_memory
  desired_count = var.api_desired_count

  subnet_ids         = module.network.public_subnet_ids
  security_group_ids = [module.network.api_security_group_id]
  container_port     = var.api_port

  environment = merge(local.common_environment, {
    # pydantic-settings parses list fields from json
    QUANTLY_CORS_ORIGINS     = jsonencode(var.cors_origins)
    QUANTLY_GOOGLE_CLIENT_ID = var.google_client_id
  })

  secrets = {
    QUANTLY_DATABASE_URL = aws_ssm_parameter.database_url.arn
    QUANTLY_JWT_SECRET   = aws_ssm_parameter.jwt_secret.arn
  }

  ecr_repository_arn = module.ecr.repository_arns["api"]
  task_policy_json   = local.api_task_policy

  aws_region         = var.aws_region
  log_retention_days = var.log_retention_days

  load_balancer = {
    target_group_arn = aws_lb_target_group.api.arn
  }

  # the target group has to be attached to a listener before a service can use it
  depends_on = [
    aws_ecs_cluster_capacity_providers.this,
    aws_lb_listener.http,
    aws_lb_listener.https,
  ]
}

# ---- worker: bigger, cpu-bound, interruptible, so it runs on spot ----
module "worker" {
  source = "./modules/ecs-service"

  name        = "${local.name}-worker"
  cluster_arn = aws_ecs_cluster.this.arn
  image       = "${module.ecr.repository_urls["worker"]}:${var.image_tag}"

  cpu               = var.worker_cpu
  memory            = var.worker_memory
  desired_count     = var.worker_desired_count
  capacity_provider = var.worker_capacity_provider

  subnet_ids         = module.network.public_subnet_ids
  security_group_ids = [module.network.worker_security_group_id]

  environment = local.common_environment

  secrets = {
    QUANTLY_DATABASE_URL = aws_ssm_parameter.database_url.arn
  }

  ecr_repository_arn = module.ecr.repository_arns["worker"]
  task_policy_json   = local.worker_task_policy

  aws_region         = var.aws_region
  log_retention_days = var.log_retention_days

  depends_on = [aws_ecs_cluster_capacity_providers.this]
}
