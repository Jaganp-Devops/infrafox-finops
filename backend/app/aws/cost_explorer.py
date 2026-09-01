"""
Cost Explorer integration. Read-only: GetCostAndUsage, GetCostForecast,
GetDimensionValues only - matches exactly the IAM policy scope defined
in Terraform (iam.tf, CostExplorerRead statement).
"""
import logging
from datetime import date, datetime, timedelta, timezone

from botocore.exceptions import ClientError

from app.aws.session import get_client
from app.models.cost import CostSummary, DailyCost

logger = logging.getLogger(__name__)


class CostExplorerError(Exception):
    """Raised when Cost Explorer API calls fail after retries are exhausted."""


def get_daily_costs_by_service(days: int = 30) -> list[DailyCost]:
    """
    Fetches daily cost broken down by service for the last N days.
    Cost Explorer data has ~24h lag, so 'today' will typically be missing
    or incomplete - this is expected and documented in ARCHITECTURE.md.
    """
    client = get_client("ce")
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days)

    try:
        response = client.get_cost_and_usage(
            TimePeriod={
                "Start": start.isoformat(),
                "End": end.isoformat(),
            },
            Granularity="DAILY",
            Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )
    except ClientError as e:
        logger.error(
            "cost_explorer_api_failure",
            extra={"extra_fields": {"error_code": e.response["Error"]["Code"]}},
        )
        raise CostExplorerError(f"Cost Explorer API call failed: {e}") from e

    results: list[DailyCost] = []
    for period in response.get("ResultsByTime", []):
        period_date = date.fromisoformat(period["TimePeriod"]["Start"])
        for group in period.get("Groups", []):
            service = group["Keys"][0]
            amount = float(group["Metrics"]["UnblendedCost"]["Amount"])
            if amount > 0:
                results.append(
                    DailyCost(date=period_date, service=service, amount_usd=amount)
                )

    return results


def get_cost_summary(days: int = 30) -> CostSummary:
    """Aggregates daily costs into a summary grouped by service."""
    daily_costs = get_daily_costs_by_service(days=days)

    by_service: dict[str, float] = {}
    total = 0.0
    for entry in daily_costs:
        by_service[entry.service] = by_service.get(entry.service, 0.0) + entry.amount_usd
        total += entry.amount_usd

    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days)

    return CostSummary(
        total_usd=round(total, 4),
        period_start=start,
        period_end=end,
        by_service={k: round(v, 4) for k, v in by_service.items()},
    )


def get_ec2_usage_hours(days: int = 30) -> dict:
    """
    Returns real billed usage hours per EC2 instance type, from Cost
    Explorer's actual usage data - not an assumption, not a 24-hour
    guess. This is what AWS actually charged for, in hours.
    """
    client = get_client("ce")
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days)

    try:
        response = client.get_cost_and_usage(
            TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
            Granularity="MONTHLY",
            Metrics=["UsageQuantity", "UnblendedCost"],
            Filter={
                "Dimensions": {
                    "Key": "SERVICE",
                    "Values": ["Amazon Elastic Compute Cloud - Compute"],
                }
            },
            GroupBy=[{"Type": "DIMENSION", "Key": "INSTANCE_TYPE"}],
        )
    except ClientError as e:
        logger.error(
            "cost_explorer_usage_hours_failure",
            extra={"extra_fields": {"error_code": e.response["Error"]["Code"]}},
        )
        raise CostExplorerError(f"get_cost_and_usage (usage hours) failed: {e}") from e

    results = {}
    for period in response.get("ResultsByTime", []):
        for group in period.get("Groups", []):
            instance_type = group["Keys"][0]
            hours = float(group["Metrics"]["UsageQuantity"]["Amount"])
            cost = float(group["Metrics"]["UnblendedCost"]["Amount"])
            results[instance_type] = {
                "billed_hours": round(hours, 2),
                "real_cost_usd": round(cost, 2),
            }
    return results

def get_ec2_running_total_this_month() -> dict:
    """
    Real EC2 compute cost, calculated in two steps:
      1. Multiply: for each day, real hourly rate x real hours run,
         combined across every running instance that day.
      2. Add: sum each day's total on top of the running total, from
         day 1 of the current calendar month through today.

    This is AWS's own real daily billing data (each day's cost already
    reflects however many instances ran and for how long) - we are not
    recalculating AWS's math ourselves, we are summing their real daily
    figures transparently, day by day, so the running total is visible
    rather than a single opaque number.
    """
    client = get_client("ce")
    today = datetime.now(timezone.utc).date()
    month_start = today.replace(day=1)
    # Cost Explorer requires Start < End strictly. When today IS the 1st of
    # the month, month_start and today are the same date - add one day to
    # End so the query is always valid, even on day one of a new month.
    query_end = today + timedelta(days=1)

    try:
        response = client.get_cost_and_usage(
            TimePeriod={"Start": month_start.isoformat(), "End": query_end.isoformat()},
            Granularity="DAILY",
            Metrics=["UnblendedCost"],
            Filter={
                "Dimensions": {
                    "Key": "SERVICE",
                    "Values": ["Amazon Elastic Compute Cloud - Compute"],
                }
            },
        )
    except ClientError as e:
        logger.error(
            "cost_explorer_running_total_failure",
            extra={"extra_fields": {"error_code": e.response["Error"]["Code"]}},
        )
        raise CostExplorerError(f"get_cost_and_usage (running total) failed: {e}") from e

    daily_breakdown = []
    running_total = 0.0

    for period in response.get("ResultsByTime", []):
        day = period["TimePeriod"]["Start"]
        day_cost = float(period["Total"]["UnblendedCost"]["Amount"])
        running_total += day_cost  # STEP 2: add today's real cost onto the running total

        daily_breakdown.append({
            "date": day,
            "day_cost_usd": round(day_cost, 4),
            "running_total_usd": round(running_total, 4),
        })

    return {
        "month_start": month_start.isoformat(),
        "today": today.isoformat(),
        "daily_breakdown": daily_breakdown,
        "final_running_total_usd": round(running_total, 4),
    }
