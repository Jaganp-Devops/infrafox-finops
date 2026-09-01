"""
CloudWatch utilization data - primarily EC2 CPUUtilization, used by the
rule engine to detect underutilized instances. Read-only: GetMetricData,
GetMetricStatistics, ListMetrics only.
"""
import logging
from datetime import datetime, timedelta, timezone

from botocore.exceptions import ClientError

from app.aws.session import get_client
from app.core.config import settings
from app.models.resource import UtilizationSample

logger = logging.getLogger(__name__)


class CloudWatchError(Exception):
    """Raised when CloudWatch API calls fail after retries are exhausted."""


def get_ec2_cpu_utilization(
    instance_id: str, lookback_days: int | None = None
) -> UtilizationSample | None:
    """
    Fetches average and max CPUUtilization for an instance over the
    lookback window. Returns None (not an error) if no datapoints exist -
    this is expected for instances younger than the lookback window, and
    the rule engine must treat 'no data' differently from 'confirmed low
    usage' (lower confidence, not a false positive).
    """
    lookback = lookback_days or settings.cloudwatch_lookback_days
    client = get_client("cloudwatch")

    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=lookback)

    try:
        response = client.get_metric_statistics(
            Namespace="AWS/EC2",
            MetricName="CPUUtilization",
            Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
            StartTime=start_time,
            EndTime=end_time,
            Period=3600,
            Statistics=["Average", "Maximum"],
        )
    except ClientError as e:
        logger.error(
            "cloudwatch_get_metric_statistics_failure",
            extra={
                "extra_fields": {
                    "instance_id": instance_id,
                    "error_code": e.response["Error"]["Code"],
                }
            },
        )
        raise CloudWatchError(f"get_metric_statistics failed: {e}") from e

    datapoints = response.get("Datapoints", [])
    if not datapoints:
        logger.info(
            "no_cloudwatch_datapoints",
            extra={"extra_fields": {"instance_id": instance_id}},
        )
        return None

    avg = sum(dp["Average"] for dp in datapoints) / len(datapoints)
    maximum = max(dp["Maximum"] for dp in datapoints)

    return UtilizationSample(
        resource_id=instance_id,
        metric_name="CPUUtilization",
        average=round(avg, 2),
        maximum=round(maximum, 2),
        period_start=start_time,
        period_end=end_time,
        datapoint_count=len(datapoints),
    )


def get_ec2_cpu_utilization_today(instance_id: str) -> float | None:
    """
    Average CPU for just the last 24 hours - a separate, shorter window
    from the multi-day trend, so 'today' and 'this week' can be shown
    as two distinct, honestly-labeled numbers.
    """
    client = get_client("cloudwatch")
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=24)

    try:
        response = client.get_metric_statistics(
            Namespace="AWS/EC2",
            MetricName="CPUUtilization",
            Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
            StartTime=start_time,
            EndTime=end_time,
            Period=3600,
            Statistics=["Average"],
        )
    except ClientError as e:
        logger.error(
            "cloudwatch_today_cpu_failure",
            extra={"extra_fields": {"instance_id": instance_id, "error_code": e.response["Error"]["Code"]}},
        )
        return None

    datapoints = response.get("Datapoints", [])
    if not datapoints:
        return None

    avg_today = sum(dp["Average"] for dp in datapoints) / len(datapoints)
    return round(avg_today, 2)
