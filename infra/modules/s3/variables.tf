variable "bucket_name" {
  description = "globally unique bucket name"
  type        = string
}

variable "expire_after_days" {
  description = "days before a raw csv upload is deleted"
  type        = number
  default     = 90
}

variable "force_destroy" {
  description = "allow destroying the bucket while it still holds objects"
  type        = bool
  default     = true
}
