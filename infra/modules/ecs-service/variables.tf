variable "name" {
  description = "service, task family and container name"
  type        = string
}

variable "cluster_arn" {
  description = "ecs cluster the service runs in"
  type        = string
}

variable "image" {
  description = "container image, including tag"
  type        = string
}

variable "command" {
  description = "overrides the image's CMD when set"
  type        = list(string)
  default     = null
}

variable "cpu" {
  description = "task cpu units (256 = 0.25 vcpu)"
  type        = number
  default     = 256
}

variable "memory" {
  description = "task memory in mib"
  type        = number
  default     = 512
}

variable "cpu_architecture" {
  description = "X86_64 or ARM64, must match how the image was built"
  type        = string
  default     = "X86_64"
}

variable "desired_count" {
  description = "number of tasks to keep running"
  type        = number
  default     = 1
}

variable "capacity_provider" {
  description = "FARGATE or FARGATE_SPOT"
  type        = string
  default     = "FARGATE"

  validation {
    condition     = contains(["FARGATE", "FARGATE_SPOT"], var.capacity_provider)
    error_message = "capacity_provider must be FARGATE or FARGATE_SPOT."
  }
}

variable "subnet_ids" {
  description = "subnets the tasks are placed in"
  type        = list(string)
}

variable "security_group_ids" {
  description = "security groups attached to the tasks"
  type        = list(string)
}

variable "container_port" {
  description = "port the container listens on, null for services with no inbound traffic"
  type        = number
  default     = null
}

variable "environment" {
  description = "plain environment variables"
  type        = map(string)
  default     = {}
}

variable "secrets" {
  description = "env var name => ssm parameter (or secrets manager) arn, resolved by ecs at task start"
  type        = map(string)
  default     = {}
}

variable "aws_region" {
  description = "region the service's log group lives in"
  type        = string
}

variable "log_retention_days" {
  description = "days to keep container logs"
  type        = number
  default     = 14
}

variable "ecr_repository_arn" {
  description = "the one repository this service is allowed to pull its image from"
  type        = string
}

variable "task_policy_json" {
  description = "iam policy for the task role: what the application itself may call"
  type        = string
}

variable "load_balancer" {
  description = "register tasks with this target group, null for no load balancer"
  type = object({
    target_group_arn = string
  })
  default = null
}
