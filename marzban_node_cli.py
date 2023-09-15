import click
import os
import subprocess
import time

@click.command()
@click.option('--iran', is_flag=True, help='Install for Iranian server with DNS modification.')
@click.option('--international', is_flag=True, help='Install for international server without DNS modification.')
@click.option('--certificate-key', is_flag=True, help='Get the certificate key.')
@click.option('--auto', is_flag=True, help='Auto mode, user selects options by number.')
def install_marzban_node(iran, international, certificate_key, auto):
    """Marzban-node Installation Script"""

    click.echo("Welcome to the Marzban-node Installation Script")
    click.echo("----------------------------------------------")
    click.echo("Script created by dry-stan Nex")
    click.echo("This script will help you install Marzban-node.")
    time.sleep(3)

    if not iran and not international and not certificate_key:
        if auto:
            choice = auto_select()
        else:
            choice = manual_select()

        if choice == 1:
            iran = True
        elif choice == 2:
            international = True
        elif choice == 3:
            certificate_key = True

    if iran:
        modify_dns_settings()
    install_docker_and_compose()
    install_git()
    install_marzban_node_internal()

    if certificate_key:
        time.sleep(5)  # Wait for 5 seconds
        clear_terminal()
        get_certificate_key()

    click.echo("Script execution complete.")

def auto_select():
    """Automatically select an option based on user input."""
    try:
        click.echo("Choose an installation option:")
        click.echo("1. Install for Iranian server (with DNS modification)")
        click.echo("2. Install for international server (without DNS modification)")
        click.echo("3. Get the certificate key")
        choice = click.prompt("Enter the number of your choice (1/2/3):", type=int)
        if choice not in [1, 2, 3]:
            raise click.ClickException("Invalid choice. Please select 1, 2, or 3.")
        return choice
    except click.exceptions.Abort:
        click.echo("Aborted. Exiting...")
        raise SystemExit(1)

def manual_select():
    """Manually select an option based on user input."""
    while True:
        click.echo("Choose an installation option:")
        click.echo("1. Install for Iranian server (with DNS modification)")
        click.echo("2. Install for international server (without DNS modification)")
        click.echo("3. Get the certificate key")
        choice = click.prompt("Enter your choice (1/2/3):", type=int)
        if choice in [1, 2, 3]:
            return choice
        else:
            click.echo("Invalid choice. Please select 1, 2, or 3.")

def modify_dns_settings():
    """Modify DNS settings for Iranian server"""
    click.echo("Modifying DNS settings for Iranian server...")
    try:
        with open("/etc/systemd/resolved.conf", "r") as resolved_conf_file:
            lines = resolved_conf_file.readlines()

        with open("/etc/systemd/resolved.conf", "w") as resolved_conf_file:
            for line in lines:
                if line.startswith("DNS="):
                    resolved_conf_file.write("DNS=185.51.200.2\n")
                elif line.startswith("FallbackDNS="):
                    resolved_conf_file.write("FallbackDNS=178.22.122.100\n")
                else:
                    resolved_conf_file.write(line)

        subprocess.run(["sudo", "systemctl", "restart", "systemd-resolved"], check=True)
        click.echo("DNS settings modified successfully.")
    except Exception as e:
        click.echo(f"Failed to modify DNS settings: {str(e)}")

def install_docker_and_compose():
    """Install Docker and Docker Compose"""
    click.echo("Installing Docker and Docker Compose...")
    try:
        subprocess.run(["curl", "-fsSL", "https://get.docker.com", "-o", "get-docker.sh"], check=True)
        subprocess.run(["sh", "get-docker.sh"], check=True)
        subprocess.run(["rm", "get-docker.sh"], check=True)

        subprocess.run(
            [
                "curl",
                "-L",
                f"https://github.com/docker/compose/releases/latest/download/docker-compose-{os.uname().sysname.lower()}-{os.uname().machine.lower()}",
                "-o",
                "/usr/local/bin/docker-compose",
            ],
            check=True,
        )
        subprocess.run(["chmod", "+x", "/usr/local/bin/docker-compose"], check=True)
        click.echo("Docker and Docker Compose installed successfully.")
    except Exception as e:
        click.echo(f"Failed to install Docker and Docker Compose: {str(e)}")

def install_git():
    """Install Git"""
    click.echo("Installing Git...")
    try:
        subprocess.run(["sudo", "apt-get", "install", "-y", "git"], check=True)
    except Exception as e:
        click.echo(f"Failed to install Git: {str(e)}")

def install_marzban_node_internal():
    """Install Marzban-node"""
    click.echo("Cloning Marzban-node repository...")
    try:
        subprocess.run(["git", "clone", "https://github.com/Gozargah/Marzban-node"], check=True)
        os.chdir("Marzban-node")
        click.echo("Lifting Marzban-node container...")
        subprocess.run(["docker-compose", "up", "-d"], check=True)
        time.sleep(5)
    except Exception as e:
        click.echo(f"Failed to clone and install Marzban-node: {str(e)}")

def get_certificate_key():
    """Get the certificate key"""
    click.echo("Getting the certificate key...")
    try:
        with open("/var/lib/marzban-node/ssl_cert.pem", "r") as cert_file:
            click.echo(cert_file.read())
    except Exception as e:
        click.echo(f"Failed to get the certificate key: {str(e)}")

def clear_terminal():
    """Clear the terminal"""
    if os.name == 'posix':
        subprocess.run(['clear'])
    elif os.name == 'nt':
        subprocess.run(['cls'])

if __name__ == "__main__":
    install_marzban_node()



