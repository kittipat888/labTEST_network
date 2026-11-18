import os
import time
from pathlib import Path
import paramiko

SECRET_PATH = "/run/secrets/router_ssh_password"
USERNAME = os.getenv("ROUTER_SSH_USERNAME", "kono")

def get_ssh_password() -> str:
    """อ่านรหัสผ่านจาก Docker Secret เพื่อความปลอดภัยตามเกณฑ์ Task 7"""
    p = Path(SECRET_PATH)
    if p.exists():
        return p.read_text().strip()
    local_p = Path("secrets/router_ssh_password")
    if local_p.exists():
        return local_p.read_text().strip()
    return "cisco"

def execute_config_via_ssh(ip: str, config_text: str) -> str:
    """
    Task 7: Paramiko SSH Deployment
    เชื่อมต่อไปยัง Router และส่งชุดคำสั่งคอนฟิก Cisco IOS CLI
    """
    password = get_ssh_password()
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    output = ""
    try:
        ssh.connect(
            hostname=ip,
            username=USERNAME,
            password=password,
            timeout=10,
            look_for_keys=False,
            allow_agent=False
        )
        channel = ssh.invoke_shell()
        time.sleep(1)

        # ส่งคำสั่งทีละบรรทัดเข้า Router
        for line in config_text.splitlines():
            line = line.strip()
            if line:
                channel.send(line + "\n")
                time.sleep(0.3)

        time.sleep(2)
        while channel.recv_ready():
            output += channel.recv(65535).decode("utf-8", errors="replace")
            time.sleep(0.2)

        ssh.close()
        return output
    except Exception as e:
        raise RuntimeError(f"SSH Deployment failed on {ip}: {str(e)}")

def verify_ospf_via_ssh(ip: str, device_id: str) -> dict:
    """
    Task 8: Automated OSPF Verification
    รันคำสั่ง show ip ospf neighbor, show ip route ospf, show ip protocols อัตโนมัติ
    """
    password = get_ssh_password()
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(
            hostname=ip,
            username=USERNAME,
            password=password,
            timeout=10,
            look_for_keys=False,
            allow_agent=False
        )
        channel = ssh.invoke_shell()
        time.sleep(1)
        channel.send("terminal length 0\n")
        time.sleep(0.5)

        def send_and_read(cmd):
            channel.send(cmd + "\n")
            time.sleep(1.5)
            buf = ""
            while channel.recv_ready():
                buf += channel.recv(65535).decode("utf-8", errors="replace")
                time.sleep(0.2)
            return buf

        neighbor_out = send_and_read("show ip ospf neighbor")
        route_out = send_and_read("show ip route ospf")
        protocols_out = send_and_read("show ip protocols")
        ssh.close()

        has_full = "FULL" in neighbor_out
        has_ospf_routes = "O " in route_out or "O    " in route_out

        return {
            "device_id": device_id,
            "ip": ip,
            "status": "PASS" if has_full else "INITIALIZING",
            "neighbor_state": "FULL" if has_full else "NOT_FULL",
            "remote_routes_learned": has_ospf_routes,
            "neighbor_output": neighbor_out,
            "route_output": route_out,
            "protocols_output": protocols_out
        }
    except Exception as e:
        return {
            "device_id": device_id,
            "ip": ip,
            "status": "ERROR",
            "error": str(e)
        }
