# public entry point for the api: a stable dns name, health checks, and tls
# termination when a certificate is supplied. the alb bills hourly just for
# existing, which is one more reason the stack is torn down between demos.

locals {
  tls_enabled = var.certificate_arn != null
}

resource "aws_lb" "api" {
  name               = local.name
  load_balancer_type = "application"
  internal           = false

  subnets         = module.network.public_subnet_ids
  security_groups = [module.network.alb_security_group_id]

  drop_invalid_header_fields = true
}

resource "aws_lb_target_group" "api" {
  name     = "${local.name}-api"
  vpc_id   = module.network.vpc_id
  port     = var.api_port
  protocol = "HTTP"

  # fargate tasks register by ip, not instance id
  target_type = "ip"

  # default is 300s, which just slows deploys and teardown down
  deregistration_delay = 30

  health_check {
    path                = "/health"
    matcher             = "200"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}

# no certificate: serve plain http on 80
resource "aws_lb_listener" "http" {
  count = local.tls_enabled ? 0 : 1

  load_balancer_arn = aws_lb.api.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

# with a certificate: terminate tls on 443 and bounce 80 over to it
resource "aws_lb_listener" "http_redirect" {
  count = local.tls_enabled ? 1 : 0

  load_balancer_arn = aws_lb.api.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_lb_listener" "https" {
  count = local.tls_enabled ? 1 : 0

  load_balancer_arn = aws_lb.api.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}
