import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.vision import analyze_image_with_ai
from app.generator import generate_cisco_ospf_config
from app.producer import send_config_job

app = FastAPI(title="AI Network Automation API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEPLOY_ENABLED = os.getenv("LAB_DEPLOY_ENABLED", "true").lower() == "true"

# เก็บข้อมูลใน Memory
db = {
    "bundles": {},
    "jobs": {},
    "verifications": []
}

class VisionReq(BaseModel):
    image_base64: str

class GenerateReq(BaseModel):
    r1_lan_ip: str = "10.0.0.1"
    r1_transit_ip: str = "10.1.0.1"
    r2_transit_ip: str = "10.1.0.2"
    r2_lan_ip: str = "10.2.0.2"
    netmask: str = "255.255.255.0"

@app.get("/health")
def health():
    return {"status": "ok", "service": "lab-backend", "deploy_enabled": DEPLOY_ENABLED}

@app.post("/vision/analyze")
def vision_analyze(req: VisionReq):
    return analyze_image_with_ai(req.image_base64)

@app.post("/plans/generate")
def plan_generate(req: GenerateReq):
    r1_cfg = generate_cisco_ospf_config(
        device_id="R1", router_id="1.1.1.1",
        lan_ip=req.r1_lan_ip, lan_mask=req.netmask,
        transit_ip=req.r1_transit_ip, transit_mask=req.netmask
    )
    r2_cfg = generate_cisco_ospf_config(
        device_id="R2", router_id="2.2.2.2",
        lan_ip=req.r2_lan_ip, lan_mask=req.netmask,
        transit_ip=req.r2_transit_ip, transit_mask=req.netmask
    )
    configs = {"R1": r1_cfg, "R2": r2_cfg}
    config_hash = hashlib.sha256(json.dumps(configs, sort_keys=True).encode()).hexdigest()
    bundle_id = str(uuid.uuid4())
    
    db["bundles"][bundle_id] = {
        "id": bundle_id,
        "configs": configs,
        "config_hash": config_hash,
        "status": "DRAFT",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "approved_at": None
    }
    return db["bundles"][bundle_id]

@app.post("/bundles/{bundle_id}/approve")
def approve_bundle(bundle_id: str):
    if bundle_id not in db["bundles"]:
        raise HTTPException(404, "Bundle not found")
    bundle = db["bundles"][bundle_id]
    bundle["status"] = "APPROVED"
    bundle["approved_at"] = datetime.now(timezone.utc).isoformat()
    return {"status": "APPROVED", "bundle_id": bundle_id, "config_hash": bundle["config_hash"]}

@app.post("/bundles/{bundle_id}/deploy")
def deploy_bundle(bundle_id: str):
    if not DEPLOY_ENABLED:
        raise HTTPException(403, "Deployment is disabled")
    if bundle_id not in db["bundles"]:
        raise HTTPException(404, "Bundle not found")
    bundle = db["bundles"][bundle_id]
    if bundle["status"] != "APPROVED":
        raise HTTPException(400, "Bundle must be APPROVED first")
    
    # ส่ง Job เข้า Kafka แยกตามอุปกรณ์ R1 และ R2
    dispatched = []
    for device in ["R1", "R2"]:
        job_id = send_config_job(device, bundle_id, bundle["config_hash"])
        db["jobs"][job_id] = {
            "job_id": job_id,
            "bundle_id": bundle_id,
            "device_id": device,
            "status": "PENDING",
            "output": "",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        dispatched.append({"device": device, "job_id": job_id})
    return {"status": "DISPATCHED", "jobs": dispatched}

@app.get("/bundles/{bundle_id}")
def get_bundle(bundle_id: str):
    if bundle_id not in db["bundles"]:
        raise HTTPException(404, "Bundle not found")
    return db["bundles"][bundle_id]

@app.get("/bundles/{bundle_id}/deploy-readiness")
def deploy_readiness(bundle_id: str):
    return {"real_deployment_enabled": DEPLOY_ENABLED}

@app.get("/jobs")
def list_jobs():
    return list(db["jobs"].values())

@app.post("/internal/jobs/{job_id}/claim")
def claim_job(job_id: str):
    if job_id in db["jobs"]:
        db["jobs"][job_id]["status"] = "RUNNING"
    return {"action": "CLAIMED"}

@app.post("/internal/jobs/{job_id}/complete")
def complete_job(job_id: str, data: dict):
    if job_id in db["jobs"]:
        db["jobs"][job_id]["status"] = data.get("status", "SUCCESS")
        db["jobs"][job_id]["output"] = data.get("output", "")
    return {"status": "UPDATED"}

@app.get("/verifications")
def get_verifications():
    return db["verifications"]

@app.post("/internal/verifications")
def post_verification(data: dict):
    db["verifications"].append(data)
    return {"status": "RECORDED"}
