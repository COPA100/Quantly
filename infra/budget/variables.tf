variable "project" {
  description = "project name, used in the budget name"
  type        = string
  default     = "quantly"
}

variable "aws_region" {
  description = "region for the provider (budgets themselves are account-wide)"
  type        = string
  default     = "us-east-1"
}

variable "limit_usd" {
  description = "monthly spend, in usd, that triggers the alarm"
  type        = number
  default     = 20
}

variable "alert_email" {
  description = "address that receives the budget alerts"
  type        = string
}
