# port_utils.py
import yaml

def get_unused_ports(used_ports, existing_ports):
    while True:
        try:
            port = int(input("Enter port: "))
            api_port = int(input("Enter API port: "))
            config_port = int(input("Enter config port: "))

            if (
                    port not in used_ports
                    and api_port not in used_ports
                    and config_port not in used_ports
                    and port not in existing_ports
                    and api_port not in existing_ports
                    and config_port not in existing_ports
            ):
                used_ports.update([port, api_port, config_port])
                return port, api_port, config_port
            else:
                print(
                    "Port(s) already in use or exist in the docker-compose.yml file. Please choose other port numbers.")
        except ValueError:
            print("Invalid input. Please enter valid port numbers.")

def get_existing_ports(compose_file):
    existing_ports = set()
    with open(compose_file, "r") as f:
        data = yaml.safe_load(f)

    if "services" not in data:
        return existing_ports

    for service in data["services"].values():
        if "ports" in service:
            for port_mapping in service["ports"]:
                port = int(port_mapping.split(":")[0])
                existing_ports.add(port)

    return existing_ports