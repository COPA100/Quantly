terraform {
  required_version = ">= 1.9"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

data "aws_caller_identity" "current" {}

locals {
  # prefix for every resource name, e.g. quantly-dev
  name = "${var.project}-${var.environment}"
}

module "network" {
  source = "./modules/network"

  name     = local.name
  vpc_cidr = var.vpc_cidr
  api_port = var.api_port
}

module "s3" {
  source = "./modules/s3"

  # bucket names are global, the account id keeps this one unique
  bucket_name       = "${local.name}-portfolios-${data.aws_caller_identity.current.account_id}"
  expire_after_days = var.csv_expire_after_days
}
