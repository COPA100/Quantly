variable "name" {
  description = "prefix for repository names"
  type        = string
}

variable "repositories" {
  description = "short names of the repositories to create"
  type        = list(string)
}

variable "keep_images" {
  description = "how many images to retain per repository"
  type        = number
  default     = 5
}

variable "force_delete" {
  description = "allow destroying a repository that still holds images"
  type        = bool
  default     = true
}
