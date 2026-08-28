"""
InfraFox FinOps Platform - FastAPI entrypoint.

Phase 3 scope: persistence added. /api/v1/findings now triggers a fresh
scan AND saves it; /api/v1/findings/latest reads the last saved scan
without re-scanning AWS; /api/v1/scans lists history (Feature #18).

Phase 4: CORS middleware added to allow the React dev server (running
on a different port, so a different origin) to call this API from the
browser. allow_origins is a specific allowlist, not "*" - kept tight
even in development, and will be updated again in Phase 5 once the
real domain is live behind Nginx.
"""
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.core.logging_config import configure_logging
from app.core.config import settings
from app.aws import cost_explorer, ec2_inventory, cloudwatch_metrics
from app.aws.session import get_client
from app.engine.runner import run_scan
from app.db.session import get_db, engine
from app.db.models import Base
from app.db import crud

configure_logging()

# Creates tables if they don't exist yet. Fine for this project's scale;
# a real migration tool (Alembic) would replace this if the schema needs
# to evolve after real data exists - noted as a production extension.
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.app_name,
    description="AWS FinOps & Cloud Cost Optimization Platform",
    version="0.4.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://3.109.152.62:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/ready")
def ready(db: Session = Depends(get_db)):
    """
    Readiness now checks both AWS connectivity and the database -
    either failing means the app can't do its job correctly.
    """
    try:
        client = get_client("ec2")
        client.describe_regions(RegionNames=[settings.aws_region])
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"AWS connectivity check failed: {e}")

    try:
        db.execute("SELECT 1")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database connectivity check failed: {e}")

    return {"status": "ready", "aws_region": settings.aws_region}


@app.get("/api/v1/costs/summary")
def cost_summary(days: int = 30):
    try:
        return cost_explorer.get_cost_summary(days=days)
    except cost_explorer.CostExplorerError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/v1/resources/instances")
def instances():
    try:
        return ec2_inventory.list_instances()
    except ec2_inventory.Ec2InventoryError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/v1/resources/volumes")
def volumes():
    try:
        return ec2_inventory.list_volumes()
    except ec2_inventory.Ec2InventoryError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/v1/resources/elastic-ips")
def elastic_ips():
    try:
        return ec2_inventory.list_elastic_ips()
    except ec2_inventory.Ec2InventoryError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/v1/resources/instances/{instance_id}/utilization")
def instance_utilization(instance_id: str):
    try:
        sample = cloudwatch_metrics.get_ec2_cpu_utilization(instance_id)
        if sample is None:
            return {"instance_id": instance_id, "message": "No CloudWatch datapoints in lookback window"}
        return sample
    except cloudwatch_metrics.CloudWatchError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/v1/findings")
def findings(db: Session = Depends(get_db)):
    """
    Runs a fresh scan AND persists it. This is the endpoint to call when
    you actually want up-to-date findings and are fine paying the cost
    of live AWS API calls (~1 second, negligible API cost).
    """
    result = run_scan()
    crud.save_scan_result(db, result)
    return result


@app.get("/api/v1/findings/latest")
def findings_latest(db: Session = Depends(get_db)):
    """
    Reads the most recently SAVED scan without touching AWS at all.
    Use this for dashboard loads where you don't need live data on
    every page refresh.
    """
    latest = crud.get_latest_scan(db)
    if latest is None:
        raise HTTPException(status_code=404, detail="No scans have been run yet. Call /api/v1/findings first.")
    return latest


@app.get("/api/v1/findings/open")
def findings_open(db: Session = Depends(get_db)):
    """Currently-open findings only, across all resources - the dashboard's main list."""
    return crud.get_open_findings(db)


@app.get("/api/v1/scans")
def scan_history(limit: int = 20, db: Session = Depends(get_db)):
    """Feature #18: historical recommendation/scan tracking."""
    return crud.get_scan_history(db, limit=limit)


@app.get("/api/v1/resources/{resource_id}/history")
def resource_history(resource_id: str, db: Session = Depends(get_db)):
    """Drill-down: every finding ever recorded for a specific resource."""
    return crud.get_finding_history(db, resource_id)
