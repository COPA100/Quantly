# task role policies: what each service's own code may call in aws. the roles
# themselves live in the ecs-service module, one pair per service.
#
# rds and redis are not here on purpose. access to those is by network path
# (security groups) plus the db password, not by iam.

locals {
  # the api only ever writes the raw csv on upload
  api_task_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "UploadRawCsv"
        Effect   = "Allow"
        Action   = "s3:PutObject"
        Resource = "${module.s3.bucket_arn}/*"
      }
    ]
  })

  # the worker only ever reads it back to run the analysis
  # beat only schedules tasks over redis
  beat_task_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "NoAwsAccess"
        Effect   = "Deny"
        Action   = "*"
        Resource = "*"
      }
    ]
  })

  worker_task_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "DownloadRawCsv"
        Effect   = "Allow"
        Action   = "s3:GetObject"
        Resource = "${module.s3.bucket_arn}/*"
      }
    ]
  })
}
