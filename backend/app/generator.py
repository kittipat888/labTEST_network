import ipaddress

def generate_cisco_ospf_config(device_id: str, router_id: str, lan_ip: str, lan_mask: str, 
                               transit_ip: str, transit_mask: str) -> str:
    lan_net = ipaddress.IPv4Interface(f"{lan_ip}/{lan_mask}").network
    transit_net = ipaddress.IPv4Interface(f"{transit_ip}/{transit_mask}").network

    # กำหนดพอร์ตให้ตรงกับสายที่ต่อจริงใน GNS3 ของคุณ
    lan_iface = "FastEthernet1/1"
    transit_iface = "FastEthernet1/0"

    lines = [
        "configure terminal",
        f"interface {lan_iface}",
        f" ip address {lan_ip} {lan_mask}",
        " no shutdown",
        " exit",
        f"interface {transit_iface}",
        f" ip address {transit_ip} {transit_mask}",
        " no shutdown",
        " exit",
        "router ospf 1",
        f" router-id {router_id}",
        " passive-interface default",
        f" no passive-interface {transit_iface}",
        f" network {lan_net.network_address} {lan_net.hostmask} area 0",
        f" network {transit_net.network_address} {transit_net.hostmask} area 0",
        " exit",
        "end"
    ]
    return "\n".join(lines) + "\n"
