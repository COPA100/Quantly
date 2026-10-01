variable "name" {
  description = "prefix for resource names"
  type        = string
}

variable "vpc_cidr" {
  description = "cidr block for the vpc"
  type        = string
  default     = "10.0.0.0/16"
}

variable "az_count" {
  description = "number of availability zones to spread public subnets across (alb and rds need at least 2)"
  type        = number
  default     = 2

  validation {
    condition     = var.az_count >= 2
    error_message = "az_count must be at least 2."
  }
}

variable "api_port" {
  description = "port the api container listens on"
  type        = number
  default     = 8000
}
