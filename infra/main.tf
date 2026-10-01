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
