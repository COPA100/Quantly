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
