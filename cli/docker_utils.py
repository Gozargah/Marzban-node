import os
import subprocess
import time
import yaml
import port_utils
import click


def install_docker_and_compose():
    click.echo("Installing Docker and Docker Compose...")
    try:
        # Install Docker
        subprocess.run(["curl", "-fsSL", "https://get.docker.com", "-o", "get-docker.sh"], check=True)
        subprocess.run(["sh", "get-docker.sh"], check=True)
        subprocess.run(["rm", "get-docker.sh"], check=True)
        click.echo("Docker installed successfully.")
        time.sleep(2)  # Sleep for 2 seconds
    except Exception as e:
        click.echo(f"Error installing Docker: {str(e)}")

    click.echo("Docker is already installed.")

    try:
        # Install Docker Compose
        subprocess.run(['curl', '-L',
                        f"https://github.com/docker/compose/releases/latest/download/docker-compose-{os.uname().sysname.lower()}-{os.uname().machine}",
                        '-o', '/usr/local/bin/docker-compose'])
        subprocess.run(['chmod', '+x', '/usr/local/bin/docker-compose'])
        click.echo("Docker Compose installed successfully.")
        time.sleep(2)  # Sleep for 2 seconds
    except Exception as e:
        click.echo(f"Error installing Docker Compose: {str(e)}")

    click.echo("Docker Compose is already installed.")


def edit_docker_compose(directory, used_ports):
    compose_file = os.path.join(directory, "docker-compose.yml")

    # Check if the docker-compose file exists
    if not os.path.exists(compose_file):
        print("docker-compose.yml file not found in Marzban-node directory.")
        return

    existing_ports = port_utils.get_existing_ports(compose_file)

    with open(compose_file, "r") as f:
        data = yaml.safe_load(f)

    # Ensure the "version" and "services" keys exist at the top
    if "version" not in data:
        data["version"] = "3"  # Set your desired version here
    if "services" not in data:
        data["services"] = {}

    # Ask the user if they want to delete and replace the contents
    replace_contents = input("Do you want to replace the existing contents? (y/n): ").strip().lower()
    if replace_contents != "y":
        return

    # Determine the container name based on existing services
    container_number = 1
    while f"node-{container_number}" in data["services"]:
        container_number += 1
    container_name = f"node-{container_number}"

    # Ask for port, api port, and config port
    port, api_port, config_port = port_utils.get_unused_ports(used_ports, existing_ports)

    # Add the new container section with ports
    data["services"][container_name] = {
        "image": "gozargah/marzban-node:latest",
        "restart": "always",
        "volumes": [
            "/var/lib/marzban-node:/var/lib/marzban-node"
        ],
        "ports": [
            f"{port}:62050",
            f"{api_port}:62051",
            f"{config_port}:{config_port}"
        ]
    }

    # Write the modified data back to the docker-compose file
    with open(compose_file, "w") as f:
        yaml.dump(data, f, default_flow_style=False)

    print(f"Container '{container_name}' added to docker-compose.yml")

    # Run docker-compose up -d
    subprocess.run(["docker-compose", "-f", compose_file, "up", "-d"], check=True)
