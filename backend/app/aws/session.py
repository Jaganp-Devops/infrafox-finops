"""
Central boto3 session factory. On EC2 with an attached instance profile,
boto3 automatically discovers credentials via the instance metadata
service (IMDSv2) — no access keys, no explicit credential handling here
at all. This file exists so every client is built consistently and the
region is never hardcoded in more than one place.
"""
import boto3

from app.core.config import settings


def get_client(service_name: str):
    """Returns a boto3 client for the given service, in the configured region."""
    return boto3.client(service_name, region_name=settings.aws_region)
