import json
import os
import uuid
from kafka import KafkaProducer

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
TOPIC_NAME = "network-config-jobs"

def get_kafka_producer():
    return KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        request_timeout_ms=10000
    )

def send_config_job(device_id: str, bundle_id: str, config_hash: str, mode: str = "DEPLOY") -> str:
    """
    Task 5: Kafka Producer
    ส่ง Job การคอนฟิกเข้า Kafka Topic พร้อม unique job ID, device ID และ config hash
    """
    job_id = str(uuid.uuid4())
    job_payload = {
        "job_id": job_id,
        "bundle_id": bundle_id,
        "device_id": device_id,
        "config_hash": config_hash,
        "mode": mode
    }

    producer = get_kafka_producer()
    producer.send(TOPIC_NAME, job_payload)
    producer.flush()
    producer.close()
    return job_id
