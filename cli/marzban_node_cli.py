#!/usr/bin/env python3
import click
import subprocess
import os
import time
import yaml

# Define DNS settings
DNS_PRIMARY = "185.51.200.2"
DNS_FALLBACK = "178.22.122.100"


@click.group()
def cli():
    pass


@cli.command()
def install():
    install_docker_and_compose()
    install_marzban_node()

@cli.command()
def add_container():
    marzban_node_dir = find_marzban_node_directory()
    if marzban_node_dir:
        used_ports = set()
        edit_docker_compose(marzban_node_dir, used_ports)
    else:
        print("Marzban-node directory not found.")

@cli.command()
def restart():
    marzban_node_dir = find_marzban_node_directory()
    if marzban_node_dir:
        compose_file = os.path.join(marzban_node_dir, "docker-compose.yml")
        if os.path.exists(compose_file):
            # Stop and remove containers
            subprocess.run(["docker-compose", "-f", compose_file, "down"], check=True)
            print("Containers stopped and removed successfully.")

            # Start containers
            subprocess.run(["docker-compose", "-f", compose_file, "up", "-d"], check=True)
            print("Containers started successfully.")
        else:
            print("docker-compose.yml file not found in Marzban-node directory.")
    else:
        print("Marzban-node directory not found.")


@cli.command()
def up():
    marzban_node_dir = find_marzban_node_directory()
    if marzban_node_dir:
        compose_file = os.path.join(marzban_node_dir, "docker-compose.yml")
        if os.path.exists(compose_file):
            subprocess.run(["docker-compose", "-f", compose_file, "up", "-d"], check=True)
            print("Containers started successfully.")
        else:
            print("docker-compose.yml file not found in Marzban-node directory.")
    else:
        print("Marzban-node directory not found.")


@cli.command()
def down():
    marzban_node_dir = find_marzban_node_directory()
    if marzban_node_dir:
        compose_file = os.path.join(marzban_node_dir, "docker-compose.yml")
        if os.path.exists(compose_file):
            subprocess.run(["docker-compose", "-f", compose_file, "down"], check=True)
            print("Containers stopped and removed successfully.")
        else:
            print("docker-compose.yml file not found in Marzban-node directory.")
    else:
        print("Marzban-node directory not found.")


@cli.command()
def update():
    find_marzban_node_directory()
    update_marzban_node()
    get_certificate_key()


@cli.command()
def dns():
    option = get_dns_configuration_option()

    if option == '1':
        modify_dns_settings(DNS_PRIMARY, DNS_FALLBACK)
    elif option == '2':
        modify_dns_settings("10.202.10.202", "10.202.10.102")
    elif option == '3':
        custom_dns_primary = click.prompt("Enter primary DNS server:")
        custom_dns_secondary = click.prompt("Enter secondary DNS server:")
        modify_dns_settings(custom_dns_primary, custom_dns_secondary)
    else:
        click.echo("Invalid option selected.")
    install_docker_and_compose()
    install_marzban_node()
    get_certificate_key()


@cli.command()
def certificate():
    get_certificate_key()


@cli.command()
@click.option('--option', type=click.Choice(['1', '2', '3']), default='1',
              prompt="Choose DNS configuration option for adjusting DNS settings:\n1. Use recommended DNS servers\n2. "
                     "Use predefined DNS servers\n3. Enter custom DNS servers")
def adjust_dns(option):
    if option == '1':
        modify_dns_settings(DNS_PRIMARY, DNS_FALLBACK)
    elif option == '2':
        modify_dns_settings("10.202.10.202", "10.202.10.102")
    elif option == '3':
        custom_dns_primary = click.prompt("Enter primary DNS server:")
        custom_dns_secondary = click.prompt("Enter secondary DNS server:")
        modify_dns_settings(custom_dns_primary, custom_dns_secondary)
    else:
        click.echo("Invalid option selected.")


@cli.command()
def tor():
    install_docker_with_tor()
    install_marzban_node()
    get_certificate_key()


@cli.command()
def help():
    show_help()


def show_help():
    # Display help message
    click.secho("Marzban-node Installation Script", fg="blue", bold=True)
    click.echo("------------------------------------------------")
    click.echo("This script assists in installing Marzban-node.")
    click.echo("Available Commands:")
    click.secho("  install", fg="green", bold=True)
    click.echo("    - Install Docker and Marzban-node.")
    click.secho("  add-container", fg="green", bold=True)
    click.echo("    - Add a new container to the Marzban-node setup.")
    click.secho("  restart", fg="green", bold=True)
    click.echo("    - Restart the Marzban-node containers.")
    click.secho("  up", fg="green", bold=True)
    click.echo("    - Start the Marzban-node containers.")
    click.secho("  down", fg="green", bold=True)
    click.echo("    - Stop and remove Marzban-node containers.")
    click.secho("  update", fg="green", bold=True)
    click.echo("    - Update Marzban-node to the latest version.")
    click.secho("  dns", fg="green", bold=True)
    click.echo("    - Install marzban-node for Iranian servers with dns modification.")
    click.secho("  certificate", fg="green", bold=True)
    click.echo("    - Get the SSL certificate key.")
    click.secho("  adjust-dns", fg="green", bold=True)
    click.echo("    - Adjust DNS settings only (implies dns).")
    click.secho("  tor", fg="green", bold=True)
    click.echo("    - Install Docker with Tor and Marzban-node.")
    click.secho("  help", fg="green", bold=True)
    click.echo("    - Show this help message.")


def get_dns_configuration_option():
    option = click.prompt(
        "Choose DNS configuration option:\n1. Use recommended DNS servers\n2. Use predefined DNS servers\n3. Enter "
        "custom DNS servers",
        type=click.Choice(['1', '2', '3']))
    return option


def modify_dns_settings(primary_dns, fallback_dns):
    click.echo("Modifying DNS settings for Iranian server...")
    try:
        # Remove existing DNS and FallbackDNS lines
        subprocess.run(['sudo', 'sed', '-i', '/^DNS=/d', '/etc/systemd/resolved.conf'])
        subprocess.run(['sudo', 'sed', '-i', '/^FallbackDNS=/d', '/etc/systemd/resolved.conf'])

        # Add new DNS and FallbackDNS lines
        subprocess.run(['sudo', 'bash', '-c', f"echo 'DNS={primary_dns}' >> /etc/systemd/resolved.conf"])
        subprocess.run(['sudo', 'bash', '-c', f"echo 'FallbackDNS={fallback_dns}' >> /etc/systemd/resolved.conf"])

        # Restart systemd-resolved
        subprocess.run(['sudo', 'systemctl', 'daemon-reload'])  # Reload systemd
        subprocess.run(['sudo', 'systemctl', 'restart', 'systemd-resolved'])  # Restart systemd-resolved

        click.echo("DNS settings modified successfully.")
        time.sleep(5)  # Sleep for 5 seconds
    except Exception as e:
        click.echo(f"Error modifying DNS settings: {str(e)}")


def install_docker_with_tor():
    # Step 1: Modify DNS
    with open('/etc/resolv.conf', 'w') as resolv_conf:
        resolv_conf.write("nameserver 4.2.2.4\nnameserver 8.8.8.8\n")

    # Step 2: Install Tor
    os.system("sudo apt update && sudo add-apt-repository ppa:micahflee/ppa -y && sudo apt install tor obfs4proxy -y")
    os.system("sudo systemctl start tor && sudo systemctl enable tor && sudo systemctl status tor")

    # Step 3: Install Docker
    os.system("curl -fsSL https://get.docker.com | sh")

    # Step 4: Install Docker Compose
    os.system("sudo apt install docker-compose -y")

    # Step 5: Configure Docker for faster downloads
    os.system(
        "sudo bash -c 'cat > /etc/docker/daemon.json <<EOF\n{\n\"insecure-registries\" : [\"https://docker.arvancloud.ir\"],\n\"registry-mirrors\": [\"https://docker.arvancloud.ir\"]\n}\nEOF'")

    # Step 6: Apply Docker changes
    os.system("docker logout")
    os.system("sudo systemctl restart docker")


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


def edit_docker_compose(directory, used_ports):
    compose_file = os.path.join(directory, "docker-compose.yml")

    # Check if the docker-compose file exists
    if not os.path.exists(compose_file):
        print("docker-compose.yml file not found in Marzban-node directory.")
        return

    existing_ports = get_existing_ports(compose_file)

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
    port, api_port, config_port = get_unused_ports(used_ports, existing_ports)

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


def install_git():
    click.echo("Installing git...")
    try:
        subprocess.run(['sudo', 'apt-get', 'install', '-y', 'git'])
        click.echo("Git installed successfully.")
        time.sleep(1)  # Sleep for 1 second
    except Exception as e:
        click.echo(f"Error installing git: {str(e)}")


def install_marzban_node():
    click.echo("Installing Marzban-node...")
    try:
        if not os.path.exists("Marzban-node"):
            subprocess.run(['git', 'clone', 'https://github.com/Gozargah/Marzban-node'])
        os.chdir("Marzban-node")
        subprocess.run(['docker-compose', 'up', '-d'])
        click.echo("Marzban-node container is running.")
        click.echo("Please wait a few moments for it to fully initialize.")
        click.echo("You can check the status using 'docker-compose ps'.")
        time.sleep(5)  # Sleep for 5 seconds
    except Exception as e:
        click.echo(f"Error installing Marzban-node: {str(e)}")


def find_marzban_node_directory():
    # Check if the "Marzban-node" directory exists in /opt
    if os.path.exists("/opt/Marzban-node"):
        return "/opt/Marzban-node"

    # If not found in /opt, search system-wide for the directory
    for root, dirs, files in os.walk("/"):
        if "Marzban-node" in dirs:
            return os.path.join(root, "Marzban-node")

    return None  # Return None if not found anywhere


def update_marzban_node():
    click.echo("Updating Marzban-node...")

    # Step 1: Update the Git repository
    marzban_node_directory = find_marzban_node_directory()
    if marzban_node_directory:
        try:
            os.chdir(marzban_node_directory)
            subprocess.run(['git', 'pull'])
            click.echo("Git repository updated successfully.")
        except Exception as e:
            click.echo(f"Error updating Git repository: {str(e)}")
    else:
        click.echo(
            "Marzban-node directory not found. You may need to clone it first or it's not installed system-wide.")

    # Step 2: Pull the latest Docker image
    try:
        subprocess.run(['docker', 'pull', 'gozargah/marzban-node:latest'], check=True)
        click.echo("Latest Docker image pulled successfully.")
    except Exception as e:
        click.echo(f"Error pulling the latest Docker image: {str(e)}")

    if marzban_node_directory:
        # Step 3: Bring down all containers
        try:
            compose_file = os.path.join(marzban_node_directory, "docker-compose.yml")
            if os.path.exists(compose_file):
                subprocess.run(["docker-compose", "-f", compose_file, "down"], check=True)
                click.echo("Containers stopped and removed successfully.")
            else:
                click.echo("docker-compose.yml file not found in Marzban-node directory.")
        except Exception as e:
            click.echo(f"Error bringing down containers: {str(e)}")

        # Step 4: Bring up all containers
        try:
            if os.path.exists(compose_file):
                subprocess.run(["docker-compose", "-f", compose_file, "up", "-d"], check=True)
                click.echo("Containers started successfully.")
            else:
                click.echo("docker-compose.yml file not found in Marzban-node directory.")
        except Exception as e:
            click.echo(f"Error bringing up containers: {str(e)}")
    else:
        click.echo(
            "Marzban-node directory not found. You may need to clone it first or it's not installed system-wide.")


def get_certificate_key():
    click.echo("Getting the certificate key...")
    try:
        with open('/var/lib/marzban-node/ssl_cert.pem', 'r') as f:
            certificate_key = f.read()
        click.echo(certificate_key)
        time.sleep(1)  # Sleep for 1 second
    except Exception as e:
        click.echo(f"Error getting the certificate key: {str(e)}")


if __name__ == '__main__':
    cli()
