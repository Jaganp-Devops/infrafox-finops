"""
AWS Pricing API integration. Fetches real, current on-demand EC2 prices
live from AWS, instead of a hardcoded lookup table that can drift out
of date. The Pricing API only operates from us-east-1, regardless of
which region the actual resource lives in - this is an AWS-wide quirk,
not a bug in this code.
"""
import json
import logging

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class PricingError(Exception):
    """Raised when the Pricing API call fails."""


def get_ec2_hourly_price(instance_type: str, region: str) -> float | None:
    """
    Returns the current on-demand hourly USD price for a given EC2
    instance type in a given region, fetched live from AWS. Returns
    None if no matching price is found, rather than guessing.
    """
    region_name_map = {
        "ap-south-1": "Asia Pacific (Mumbai)",
    }
    location = region_name_map.get(region)
    if location is None:
        logger.error(
            "pricing_unknown_region",
            extra={"extra_fields": {"region": region}},
        )
        return None

    client = boto3.client("pricing", region_name="us-east-1")

    try:
        response = client.get_products(
            ServiceCode="AmazonEC2",
            Filters=[
                {"Type": "TERM_MATCH", "Field": "instanceType", "Value": instance_type},
                {"Type": "TERM_MATCH", "Field": "location", "Value": location},
                {"Type": "TERM_MATCH", "Field": "operatingSystem", "Value": "Linux"},
                {"Type": "TERM_MATCH", "Field": "tenancy", "Value": "Shared"},
                {"Type": "TERM_MATCH", "Field": "preInstalledSw", "Value": "NA"},
                {"Type": "TERM_MATCH", "Field": "capacitystatus", "Value": "Used"},
            ],
            MaxResults=1,
        )
    except ClientError as e:
        logger.error(
            "pricing_api_failure",
            extra={"extra_fields": {"error_code": e.response["Error"]["Code"]}},
        )
        raise PricingError(f"Pricing API call failed: {e}") from e

    price_list = response.get("PriceList", [])
    if not price_list:
        return None

    product = json.loads(price_list[0])
    terms = product.get("terms", {}).get("OnDemand", {})
    for term in terms.values():
        for dimension in term.get("priceDimensions", {}).values():
            usd_price = dimension.get("pricePerUnit", {}).get("USD")
            if usd_price is not None:
                return round(float(usd_price), 4)

    return None
