README.md
# AI-Driven Network Configuration and Automation Using OSPFv2
ระบบอัตโนมัติสำหรับวิเคราะห์แผนผังเครือข่ายด้วย AI Vision, สร้างคอนฟิก Cisco IOS OSPFv2 Area 0, ส่งงานผ่าน Apache Kafka และ Deploy ผ่าน Python Worker (Paramiko SSH)
## สถาปัตยกรรมระบบ
- **Frontend**: Nginx Dashboard (:8002)
- **Backend**: FastAPI (:8001) เชื่อมต่อ AI Vision และ Kafka Producer
- **Message Broker**: Apache Kafka (Topic: network-config-jobs)
- **Worker**: Python Consumer + Paramiko SSH สำหรับตั้งค่าและตรวจสอบ OSPF
## วิธีติดตั้งและรันระบบ
1. คัดลอกไฟล์ `.env.example` เป็น `.env`
2. สร้างโฟลเดอร์ `secrets/` และไฟล์ `secrets/router_ssh_password`
3. สั่งรันระบบ:
