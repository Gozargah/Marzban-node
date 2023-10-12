# network_utils.py
import subprocess
import click
import os
import time

# Define DNS settings
DNS_PRIMARY = "185.51.200.2"
DNS_FALLBACK = "178.22.122.100"


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


def get_dns_configuration_option():
    option = click.prompt(
        "Choose DNS configuration option:\n1. Use recommended DNS servers\n2. Use predefined DNS servers\n3. Enter "
        "custom DNS servers",
        type=click.Choice(['1', '2', '3']))
    return option


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
        "sudo bash -c 'cat > /etc/docker/daemon.json <<EOF\n{\n\"insecure-registries\" : ["
        "\"https://docker.arvancloud.ir\"],\n\"registry-mirrors\": [\"https://docker.arvancloud.ir\"]\n}\nEOF'")

    # Step 6: Apply Docker changes
    os.system("docker logout")
    os.system("sudo systemctl restart docker")
