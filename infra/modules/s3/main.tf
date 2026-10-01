# private bucket for the raw uploaded portfolio csvs
resource "aws_s3_bucket" "this" {
  bucket = var.bucket_name

  # demo stack: let `terraform destroy` remove the bucket even if it has objects
  force_destroy = var.force_destroy
}

resource "aws_s3_bucket_public_access_block" "this" {
  bucket = aws_s3_bucket.this.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "this" {
  bucket = aws_s3_bucket.this.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  bucket = aws_s3_bucket.this.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# the raw csv is only needed until its holdings are parsed into rds, so old
# uploads expire instead of piling up
resource "aws_s3_bucket_lifecycle_configuration" "this" {
  bucket = aws_s3_bucket.this.id

  rule {
    id     = "expire-raw-csvs"
    status = "Enabled"

    filter {}

    expiration {
      days = var.expire_after_days
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}
