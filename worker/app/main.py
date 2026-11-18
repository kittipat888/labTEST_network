import json
import os
import time
from pathlib import Path
import requests
from kafka import KafkaConsumer

try:
    from app.cisco_ssh import execute_config_via_ssh, verify_ospf_via_ssh
except ModuleNotFoundError:
    from cisco_ssh import execute_config_via_ssh, verify_ospf_via_ssh

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000").rstrip("/")
TOPIC_NAME = "network-config-jobs"
INVENTORY_PATH = "/app/config/inventory.json"

processed_jobs = set()
deployed_devices = set()

def get_inventory():
    p = Path(INVENTORY_PATH)
    if not p.exists():
        p = Path("config/inventory.json")
    return json.loads(p.read_text())

def main():
    print(f"[*] Worker started. Connecting to Kafka: {KAFKA_BOOTSTRAP}...", flush=True)

    # วนลูปเชื่อมต่อ Kafka จนกว่าจะพร้อม
    consumer = None
    while consumer is None:
        try:
            consumer = KafkaConsumer(
                TOPIC_NAME,
                bootstrap_servers=KAFKA_BOOTSTRAP,
                group_id="network-automation-worker-group",
                auto_offset_reset="earliest",
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                enable_auto_commit=True
            )
            print("[+] Connected to Kafka successfully! Waiting for jobs...", flush=True)
        except Exception as e:
            print(f"[-] Waiting for Kafka broker... ({e})", flush=True)
            time.sleep(3)

    for message in consumer:
        job = message.value
        job_id = job.get("job_id")
        device_id = job.get("device_id")
        bundle_id = job.get("bundle_id")

        if not job_id or not device_id or not bundle_id:
            continue

        # ป้องกันการรันซ้ำ (Task 6: Idempotent Execution)
        if job_id in processed_jobs:
            print(f"[!] Job {job_id} already processed. Skipping.", flush=True)
            continue

        processed_jobs.add(job_id)
        print(f"\n[+] Processing Job: {job_id} for Device: {device_id}", flush=True)

        try:
            # 1. แจ้ง Backend ว่าเริ่มรันงาน
            requests.post(f"{BACKEND_URL}/internal/jobs/{job_id}/claim", timeout=10)

            # 2. ดึงคอนฟิกที่ได้รับการอนุมัติจาก Backend
            bundle_resp = requests.get(f"{BACKEND_URL}/bundles/{bundle_id}", timeout=10)
            if bundle_resp.status_code != 200:
                raise RuntimeError(f"Failed to fetch bundle {bundle_id}")

            bundle = bundle_resp.json()
            configs = bundle.get("configs", {})
            device_config = configs.get(device_id)

            if not device_config:
                raise RuntimeError(f"No config found for device {device_id}")

            # 3. หา Management IP ของ Router จาก inventory
            inventory = get_inventory()
            router_ip = inventory.get(device_id, {}).get("management_ip")
            if not router_ip:
                raise RuntimeError(f"Management IP not found for {device_id}")

            # 4. Task 7: สั่ง Deploy ผ่าน Paramiko SSH
            print(f"[*] Deploying configuration to {device_id} ({router_ip})...", flush=True)
            ssh_output = execute_config_via_ssh(router_ip, device_config)
            print(f"[+] Successfully deployed configuration to {device_id}!", flush=True)

            # 5. แจ้ง Backend ว่างานสำเร็จ
            requests.post(
                f"{BACKEND_URL}/internal/jobs/{job_id}/complete",
                json={"status": "SUCCESS", "output": ssh_output},
                timeout=10
            )
            deployed_devices.add(device_id)

            # 6. Task 8: เมื่อคอนฟิกครบทั้ง R1 และ R2 ให้รอ OSPF เจรจากัน แล้ว Verify อัตโนมัติ
            if "R1" in deployed_devices and "R2" in deployed_devices:
                print("\n[*] Both routers configured. Waiting 6s for OSPF convergence...", flush=True)
                time.sleep(6)
                for dev in ["R1", "R2"]:
                    ip = inventory[dev]["management_ip"]
                    print(f"[*] Verifying OSPF on {dev} ({ip})...", flush=True)
                    verify_result = verify_ospf_via_ssh(ip, dev)
                    requests.post(f"{BACKEND_URL}/internal/verifications", json=verify_result, timeout=10)
                    print(f"[+] OSPF Verification for {dev}: Neighbor {verify_result.get('neighbor_state')}", flush=True)

        except Exception as e:
            print(f"[-] Error processing job {job_id}: {str(e)}", flush=True)
            requests.post(
                f"{BACKEND_URL}/internal/jobs/{job_id}/complete",
                json={"status": "FAILED", "output": str(e)},
                timeout=10
            )

if __name__ == "__main__":
    main()
