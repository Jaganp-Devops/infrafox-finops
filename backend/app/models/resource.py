"""
Normalized resource models. Raw boto3 responses are messy and
inconsistent across services — everything gets mapped into these shapes
before any FinOps logic touches it. This is the boundary between
"AWS API shape" and "our domain shape."
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class Ec2Instance(BaseModel):
    instance_id: str
    instance_type: str
    state: str
    launch_time: datetime
    region: str
    availability_zone: Optional[str] = None
    tags: dict[str, str] = {}
    private_ip: Optional[str] = None
    public_ip: Optional[str] = None

    @property
    def owner(self) -> Optional[str]:
        return self.tags.get("Owner") or self.tags.get("owner")

    @property
    def environment(self) -> Optional[str]:
        return self.tags.get("Environment") or self.tags.get("environment")


class EbsVolume(BaseModel):
    volume_id: str
    size_gb: int
    volume_type: str
    state: str
    create_time: datetime
    attached_instance_id: Optional[str] = None
    tags: dict[str, str] = {}


class ElasticIp(BaseModel):
    allocation_id: str
    public_ip: str
    associated_instance_id: Optional[str] = None
    tags: dict[str, str] = {}


class UtilizationSample(BaseModel):
    resource_id: str
    metric_name: str
    average: float
    maximum: float
    period_start: datetime
    period_end: datetime
    datapoint_count: int
