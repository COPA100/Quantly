variable "project" {
  description = "project name, used as a prefix for the bucket and role names"
  type        = string
  default     = "quantly"
}

variable "aws_region" {
  description = "region the state bucket lives in"
  type        = string
  default     = "us-east-1"
}

variable "github_repository" {
  description = "owner/name of the github repo allowed to assume the ci roles"
  type        = string
  default     = "COPA100/Quantly"
}

variable "deploy_branch" {
  description = "the only branch whose workflow runs may assume the deploy role"
  type        = string
  default     = "main"
}
