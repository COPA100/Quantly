variable "project" {
  description = "project name, used as a prefix for resource names"
  type        = string
  default     = "quantly"
}

variable "environment" {
  description = "deployment environment (dev, prod)"
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "aws region everything is provisioned in"
  type        = string
  default     = "us-east-1"
}

variable "vpc_cidr" {
  description = "cidr block for the vpc"
  type        = string
  default     = "10.0.0.0/16"
}

variable "api_port" {
  description = "port the api container listens on"
  type        = number
  default     = 8000
}

variable "csv_expire_after_days" {
  description = "days before a raw csv upload is deleted from s3"
  type        = number
  default     = 90
}

variable "db_instance_class" {
  description = "rds instance class"
  type        = string
  default     = "db.t4g.micro"
}

variable "redis_node_type" {
  description = "elasticache node type"
  type        = string
  default     = "cache.t4g.micro"
}

variable "image_tag" {
  description = "tag of the api and worker images to deploy"
  type        = string
  default     = "latest"
}

variable "api_cpu" {
  description = "api task cpu units (256 = 0.25 vcpu)"
  type        = number
  default     = 256
}

variable "api_memory" {
  description = "api task memory in mib"
  type        = number
  default     = 512
}

variable "api_desired_count" {
  description = "number of api tasks"
  type        = number
  default     = 1
}

variable "worker_cpu" {
  description = "worker task cpu units, larger than the api since it runs the analytics engine"
  type        = number
  default     = 1024
}

variable "worker_memory" {
  description = "worker task memory in mib"
  type        = number
  default     = 2048
}

variable "worker_desired_count" {
  description = "number of worker tasks"
  type        = number
  default     = 1
}

variable "worker_capacity_provider" {
  description = "FARGATE or FARGATE_SPOT for the worker"
  type        = string
  default     = "FARGATE_SPOT"
}

variable "certificate_arn" {
  description = "acm certificate for the alb. when set, the api is served over https and http redirects to it"
  type        = string
  default     = null
}

variable "cors_origins" {
  description = "origins the api accepts browser requests from (the frontend's url)"
  type        = list(string)
  default     = ["http://localhost:5173"]
}

variable "google_client_id" {
  description = "google oauth client id, empty disables google sign-in"
  type        = string
  default     = ""
}
