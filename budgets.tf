# ---------------------------------------------------------------------------
# Credit safety net. This is not optional — see COST-SAFETY.md.
#
# An AWS Budget alone doesn't stop spending, it only notifies. For a $200
# credit balance, notification at 50/80/100% plus a forecasted-overrun
# alert gives enough lead time to stop the instance manually before credits
# run out.
# ---------------------------------------------------------------------------

resource "aws_sns_topic" "budget_alerts" {
  name = "infrafox-budget-alerts"
}

resource "aws_sns_topic_subscription" "budget_email" {
  topic_arn = aws_sns_topic.budget_alerts.arn
  protocol  = "email"
  endpoint  = var.budget_alert_email
  # NOTE: AWS sends a confirmation email to this address after `terraform
  # apply`. You must click "Confirm subscription" or you will not receive
  # alerts. Terraform cannot do this step for you.
}

resource "aws_budgets_budget" "infrafox_monthly" {
  name         = "infrafox-monthly-budget"
  budget_type  = "COST"
  limit_amount = tostring(var.budget_limit_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  cost_filter {
    name   = "TagKeyValue"
    values = ["user:Project$infrafox"]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 50
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.budget_alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.budget_alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.budget_alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.budget_alert_email]
  }
}
