variable "name" {
  description = "cluster id and subnet group name"
  type        = string
}

variable "subnet_ids" {
  description = "subnets for the cache subnet group"
  type        = list(string)
}

variable "security_group_ids" {
  description = "security groups attached to the node"
  type        = list(string)
}

variable "node_type" {
  description = "elasticache node type"
  type        = string
  default     = "cache.t4g.micro"
}

variable "engine_version" {
  description = "redis engine version"
  type        = string
  default     = "7.1"
}

variable "parameter_group_name" {
  description = "parameter group matching the engine version"
  type        = string
  default     = "default.redis7"
}
