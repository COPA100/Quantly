variable "name" {
  description = "instance identifier and subnet group name"
  type        = string
}

variable "subnet_ids" {
  description = "subnets for the db subnet group (2+ azs)"
  type        = list(string)
}

variable "security_group_ids" {
  description = "security groups attached to the instance"
  type        = list(string)
}

variable "engine_version" {
  description = "postgres major version"
  type        = string
  default     = "16"
}

variable "instance_class" {
  description = "rds instance class"
  type        = string
  default     = "db.t4g.micro"
}

variable "allocated_storage" {
  description = "storage in gb (20 is the rds minimum)"
  type        = number
  default     = 20
}

variable "db_name" {
  description = "name of the initial database"
  type        = string
  default     = "quantly"
}

variable "username" {
  description = "master username"
  type        = string
  default     = "quantly"
}

variable "backup_retention_days" {
  description = "days of automated backups to keep, 0 disables them"
  type        = number
  default     = 0
}
