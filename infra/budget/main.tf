# cost guardrail, kept as its own tiny root with its own state on purpose: it is
# applied once, before the main stack ever exists, and it has to survive every
# `terraform destroy` of that stack so a forgotten teardown still gets caught.

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
}

resource "aws_budgets_budget" "monthly" {
  name        = "${var.project}-monthly"
  budget_type = "COST"
  time_unit   = "MONTHLY"

  limit_amount = tostring(var.limit_usd)
  limit_unit   = "USD"

  # early warning at half the budget
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 50
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }

  # the month is on track to blow the budget, usually a stack left running
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }
}
