variable "enable_observability" {
  description = "add an aws otel collector sidecar to the api and worker tasks (traces to x-ray, metrics to cloudwatch via emf) and turn on the app's telemetry"
  type        = bool
  default     = false
}

locals {
  # app settings merged into the services only when observability is on. the
  # sidecar shares the task's network namespace, so the endpoint is localhost.
  observability_environment = var.enable_observability ? {
    QUANTLY_OTEL_ENABLED           = "true"
    QUANTLY_OTEL_EXPORTER_ENDPOINT = "http://localhost:4318"
  } : {}
}
