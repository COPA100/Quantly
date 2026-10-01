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
