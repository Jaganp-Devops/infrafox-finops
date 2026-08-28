"""
Cost Explorer integration. Read-only: GetCostAndUsage, GetCostForecast,
GetDimensionValues only — matches exactly the IAM policy scope defined
in Terraform (iam.tf, CostExplorerRead statement).
"""
import logging
from datetime import date, timedelta
from botocore.exceptions import ClientError

from app.aws.session import get_client
from app.models.cost import DailyCost, CostSummary

logger = logging.getLogger(__name__)


class CostExplorerError(Exception):
    """Raised when Cost Explorer API calls fail after retries are exhausted."""


def get_daily_costs_by_service(days: int = 30) -> list[DailyCost]:
    """
    Fetches daily cost broken down by service for the last N days.
    Cost Explorer data has ~24h lag, so 'today' will typically be missing
    or incomplete — this is expected and documented in ARCHITECTURE.md.
    """
    client = get_client("ce")
    end = date.today()
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

    end = date.today()
    start = end - timedelta(days=days)

    return CostSummary(
        total_usd=round(total, 4),
        period_start=start,
        period_end=end,
        by_service={k: round(v, 4) for k, v in by_service.items()},
    )
