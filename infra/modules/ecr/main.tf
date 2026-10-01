# one repository per service image (api, worker)
resource "aws_ecr_repository" "this" {
  for_each = toset(var.repositories)

  name = "${var.name}-${each.key}"

  # ci pushes an immutable sha tag and moves `latest` alongside it
  image_tag_mutability = "MUTABLE"

  # demo stack: let `terraform destroy` remove repos that still hold images
  force_delete = var.force_delete

  image_scanning_configuration {
    scan_on_push = true
  }
}

# keep only the newest few images so storage stays near zero
resource "aws_ecr_lifecycle_policy" "this" {
  for_each = aws_ecr_repository.this

  repository = each.value.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "keep the last ${var.keep_images} images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = var.keep_images
        }
        action = { type = "expire" }
      }
    ]
  })
}
