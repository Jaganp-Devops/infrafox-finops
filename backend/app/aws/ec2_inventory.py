"""
EC2 resource discovery - instances, EBS volumes, Elastic IPs.
Read-only Describe* calls only, matching the EC2DescribeOnly IAM
statement in Terraform. No state-changing calls exist in this file
by design.
"""
import logging

from botocore.exceptions import ClientError

from app.aws.session import get_client
from app.models.resource import EbsVolume, Ec2Instance, ElasticIp

logger = logging.getLogger(__name__)


class Ec2InventoryError(Exception):
    """Raised when EC2 Describe* calls fail after retries are exhausted."""


def _tags_to_dict(tag_list: list[dict]) -> dict[str, str]:
    return {t["Key"]: t["Value"] for t in tag_list or []}


def list_instances() -> list[Ec2Instance]:
    client = get_client("ec2")
    instances: list[Ec2Instance] = []

    try:
        paginator = client.get_paginator("describe_instances")
        for page in paginator.paginate():
            for reservation in page.get("Reservations", []):
                for inst in reservation.get("Instances", []):
                    instances.append(
                        Ec2Instance(
                            instance_id=inst["InstanceId"],
                            instance_type=inst["InstanceType"],
                            state=inst["State"]["Name"],
                            launch_time=inst["LaunchTime"],
                            region=client.meta.region_name,
                            availability_zone=inst.get("Placement", {}).get("AvailabilityZone"),
                            tags=_tags_to_dict(inst.get("Tags", [])),
                            private_ip=inst.get("PrivateIpAddress"),
                            public_ip=inst.get("PublicIpAddress"),
                        )
                    )
    except ClientError as e:
        logger.error("ec2_describe_instances_failure", extra={"extra_fields": {"error_code": e.response["Error"]["Code"]}})
        raise Ec2InventoryError(f"describe_instances failed: {e}") from e

    return instances


def list_volumes() -> list[EbsVolume]:
    client = get_client("ec2")
    volumes: list[EbsVolume] = []

    try:
        paginator = client.get_paginator("describe_volumes")
        for page in paginator.paginate():
            for vol in page.get("Volumes", []):
                attachments = vol.get("Attachments", [])
                attached_id = attachments[0]["InstanceId"] if attachments else None
                volumes.append(
                    EbsVolume(
                        volume_id=vol["VolumeId"],
                        size_gb=vol["Size"],
                        volume_type=vol["VolumeType"],
                        state=vol["State"],
                        create_time=vol["CreateTime"],
                        attached_instance_id=attached_id,
                        tags=_tags_to_dict(vol.get("Tags", [])),
                    )
                )
    except ClientError as e:
        logger.error("ec2_describe_volumes_failure", extra={"extra_fields": {"error_code": e.response["Error"]["Code"]}})
        raise Ec2InventoryError(f"describe_volumes failed: {e}") from e

    return volumes


def list_elastic_ips() -> list[ElasticIp]:
    client = get_client("ec2")

    try:
        response = client.describe_addresses()
    except ClientError as e:
        logger.error("ec2_describe_addresses_failure", extra={"extra_fields": {"error_code": e.response["Error"]["Code"]}})
        raise Ec2InventoryError(f"describe_addresses failed: {e}") from e

    return [
        ElasticIp(
            allocation_id=addr.get("AllocationId", addr["PublicIp"]),
            public_ip=addr["PublicIp"],
            associated_instance_id=addr.get("InstanceId"),
            tags=_tags_to_dict(addr.get("Tags", [])),
        )
        for addr in response.get("Addresses", [])
    ]
