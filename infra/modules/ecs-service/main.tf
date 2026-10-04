# a fargate service running a single container. instantiated once per service
# (api, worker) so each gets its own task size, scaling and capacity provider.

locals {
  container = merge(
    {
      name      = var.name
      image     = var.image
      essential = true

      environment = [for key, value in var.environment : { name = key, value = value }]
      secrets     = [for key, arn in var.secrets : { name = key, valueFrom = arn }]

      portMappings = var.container_port == null ? [] : [
        { containerPort = var.container_port, protocol = "tcp" }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.this.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
    },
    # only override the image's CMD when asked to
    var.command == null ? {} : { command = var.command },
  )
}

resource "aws_ecs_task_definition" "this" {
  family                   = var.name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory

  execution_role_arn = aws_iam_role.execution.arn
  task_role_arn      = aws_iam_role.task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = var.cpu_architecture
  }

  container_definitions = jsonencode(concat([local.container], local.collector))
}

resource "aws_ecs_service" "this" {
  name            = var.name
  cluster         = var.cluster_arn
  task_definition = aws_ecs_task_definition.this.arn
  desired_count   = var.desired_count

  # FARGATE or FARGATE_SPOT, picked per service
  capacity_provider_strategy {
    capacity_provider = var.capacity_provider
    weight            = 1
  }

  # public subnets with a public ip stand in for a nat gateway
  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = var.security_group_ids
    assign_public_ip = true
  }

  # a failed rollout rolls itself back instead of flapping forever
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  dynamic "load_balancer" {
    for_each = var.load_balancer == null ? [] : [var.load_balancer]

    content {
      target_group_arn = load_balancer.value.target_group_arn
      container_name   = var.name
      container_port   = var.container_port
    }
  }

  # give the app time to boot before failed health checks kill the task
  health_check_grace_period_seconds = var.load_balancer == null ? null : 60

  # tasks fail to start if they launch before their permissions exist
  depends_on = [
    aws_iam_role_policy.execution,
    aws_iam_role_policy.execution_logs,
    aws_iam_role_policy.task,
  ]

  lifecycle {
    # application auto scaling owns the task count once it is attached, and a
    # later apply must not reset it to desired_count
    ignore_changes = [desired_count]

    precondition {
      condition     = var.load_balancer == null || var.container_port != null
      error_message = "container_port is required when the service sits behind a load balancer."
    }
  }
}
