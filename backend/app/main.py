"""
InfraFox FinOps Platform - FastAPI entrypoint.

Phase 3: persistence added. /api/v1/findings now triggers a fresh scan
AND saves it; /api/v1/findings/latest reads the last saved scan without
re-scanning AWS; /api/v1/scans lists history (Feature #18).

Phase 4: CORS middleware added to allow the React dev server (running
on a different port, so a different origin) to call this API from the
browser.

Phase 5: containerized, running against Postgres instead of SQLite.
"""
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.aws import cloudwatch_metrics, cost_explorer, ec2_inventory
from app.aws.session import get_client
from app.core.config import settings
from app.core.logging_config import configure_logging
from app.db import crud
from app.db.models import Base, DailyRunningCost
from app.db.session import engine, get_db
from app.engine.runner import run_scan

configure_logging()

# Creates tables if they don't exist yet. Fine for this project's scale;
# a real migration tool (Alembic) would replace this if the schema needs
# to evolve after real data exists - noted as a production extension.
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.app_name,
    description="AWS FinOps & Cloud Cost Optimization Platform",
    version="0.5.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://infrafox.duckdns.org",
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
    Readiness checks both AWS connectivity and the database - either
    failing means the app can't do its job correctly.
    """
    try:
        client = get_client("ec2")
        client.describe_regions(RegionNames=[settings.aws_region])
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"AWS connectivity check failed: {e}")

    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database connectivity check failed: {e}")

    return {"status": "ready", "aws_region": settings.aws_region}

@app.get("/api/v1/costs/summary")
def cost_summary(db: Session = Depends(get_db)):
    """
    Total spend this month, calculated as the accumulating sum of each
    real day's EC2 cost (day1 + day2 + ... + today) - not a fixed
    30-day AWS query. Reads from the running ledger built by
    /api/v1/costs/record-today.
    """
    latest = db.query(DailyRunningCost).order_by(DailyRunningCost.date.desc()).first()
    if latest is None:
        return {"total_usd": 0.0, "date": None, "message": "No cost recorded yet - call /api/v1/costs/record-today first"}
    return {
        "total_usd": latest.running_total_usd,
        "date": latest.date,
    }


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

@app.get("/api/v1/costs/ec2-usage-hours")
def ec2_usage_hours(days: int = 30):
    """Real billed hours and real cost, per EC2 instance type - from AWS's actual billing, not an assumption."""
    try:
        return cost_explorer.get_ec2_usage_hours(days=days)
    except cost_explorer.CostExplorerError as e:
        raise HTTPException(status_code=502, detail=str(e))

@app.get("/api/v1/costs/ec2-month-to-date")
def ec2_month_to_date():
    """
    Real, day-by-day EC2 compute cost, summed from day 1 of the current
    calendar month through today. Excludes EBS, NAT, EIP, and every
    other service - EC2 compute time only. Each day's figure is real
    AWS billing data, not a projection.
    """
    try:
        return cost_explorer.get_ec2_compute_cost_this_month()
    except cost_explorer.CostExplorerError as e:
        raise HTTPException(status_code=502, detail=str(e))

@app.get("/api/v1/costs/ec2-running-total")
def ec2_running_total():
    """Real EC2 compute cost, day by day, accumulating from day 1 of the month to today."""
    try:
        return cost_explorer.get_ec2_running_total_this_month()
    except cost_explorer.CostExplorerError as e:
        raise HTTPException(status_code=502, detail=str(e))

@app.post("/api/v1/costs/record-today")
def record_today_cost(db: Session = Depends(get_db)):
    """
    Pulls today's real EC2 compute cost (across all instances, combined,
    from AWS Cost Explorer) and records it into the running ledger,
    adding it onto the previous day's stored total.
    """
    try:
        result = cost_explorer.get_ec2_running_total_this_month()
        today_entry = result["daily_breakdown"][-1] if result["daily_breakdown"] else {"day_cost_usd": 0.0}
        record = crud.record_daily_running_cost(db, today_entry["day_cost_usd"])
        return {
            "date": record.date,
            "day_cost_usd": record.day_cost_usd,
            "running_total_usd": record.running_total_usd,
        }
    except cost_explorer.CostExplorerError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/v1/costs/running-history")
def running_cost_history(db: Session = Depends(get_db)):
    """Full day-by-day ledger: date, that day's cost, and the running total through that day."""
    history = crud.get_running_cost_history(db)
    return [
        {"date": h.date, "day_cost_usd": h.day_cost_usd, "running_total_usd": h.running_total_usd}
        for h in history
    ]
