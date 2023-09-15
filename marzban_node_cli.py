#!/usr/bin/env python3
import click
import subprocess
import os
import time

# Define DNS settings
DNS_PRIMARY = "185.51.200.2"
DNS_FALLBACK = "178.22.122.100"
@click.command()
@click.option('--dns', is_flag=True, help='Install for Iranian server (with DNS modification)')
@click.option('--certificate', is_flag=True, help='Get the certificate key')
@click.option('--certificate-key', is_flag=True, help='Show the certificate key (implies --certificate)')
@click.option('--help', is_flag=True, help='Show professional help message')
@click.option('--adjust-dns', is_flag=True, help='Adjust DNS settings only (implies --dns)')
def main(dns, certificate, certificate_key, help, adjust_dns):
    if help:
        show_help()
        return

    if certificate_key:
        get_certificate_key()
        return

    if adjust_dns:
        modify_dns_settings()
        return

    click.echo("Welcome to the Marzban-node Installation Script")
    click.echo("----------------------------------------------")
    click.echo("Script created by dry-stan Nex")
    click.echo("This script will help you install Marzban-node.")
    click.echo("Please wait while the installation proceeds...")

    try:
        if dns:
            install_docker_and_compose()
            install_git()
            install_marzban_node()
            modify_dns_settings()
        if not dns or certificate:
            get_certificate_key()  # Always run get_certificate_key if not DNS or explicitly specified
        click.echo("Installation complete.")
    except KeyboardInterrupt:
        click.echo("\nInstallation aborted.")


def show_help():
    # Display help message
    click.echo("Marzban-node Installation Script")
    click.echo("--------------------------------")
    click.echo("This script assists in installing Marzban-node.")
    click.echo("Options:")
    click.echo("  --dns: Install for Iranian server with DNS modification.")
    click.echo("  --certificate: Get the certificate key.")
    click.echo("  --certificate-key: Show the certificate key (implies --certificate).")
    click.echo("  --adjust-dns: Adjust DNS settings only (implies --dns).")
    click.echo("  --help: Show the help message.")

def modify_dns_settings():
    click.echo("Modifying DNS settings for Iranian server...")
    try:
        # Modify DNS settings
        subprocess.run(['sudo', 'sed', '-i', '/DNS=/c\DNS=' + DNS_PRIMARY, '/etc/systemd/resolved.conf'])
        subprocess.run(
            ['sudo', 'sed', '-i', '/FallbackDNS=/c\FallbackDNS=' + DNS_FALLBACK, '/etc/systemd/resolved.conf'])
        subprocess.run(['sudo', 'systemctl', 'daemon-reload'])  # Reload systemd
        subprocess.run(['sudo', 'systemctl', 'restart', 'systemd-resolved'])  # Restart systemd-resolved
        click.echo("DNS settings modified successfully.")
        time.sleep(5)  # Sleep for 5 seconds
    except Exception as e:
        click.echo(f"Error modifying DNS settings: {str(e)}")

def install_docker_and_compose():
    click.echo("Installing Docker and Docker Compose...")
    try:
        # Install Docker using provided commands
        subprocess.run(["curl", "-fsSL", "https://get.docker.com", "-o", "get-docker.sh"], check=True)
        subprocess.run(["sh", "get-docker.sh"], check=True)
        subprocess.run(["rm", "get-docker.sh"], check=True)

        # Install Docker Compose
        subprocess.run(['curl', '-L', f"https://github.com/docker/compose/releases/latest/download/docker-compose-{os.uname().sysname.lower()}-{os.uname().machine}", '-o', '/usr/local/bin/docker-compose'])
        subprocess.run(['chmod', '+x', '/usr/local/bin/docker-compose'])

        click.echo("Docker and Docker Compose installed successfully.")
        time.sleep(2)  # Sleep for 2 seconds
    except Exception as e:
        click.echo(f"Error installing Docker and Docker Compose: {str(e)}")

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

def get_certificate_key():
    click.echo("Getting the certificate key...")
    try:
        with open('/var/lib/marzban-node/ssl_cert.pem', 'r') as f:
            certificate_key = f.read()
        click.echo(certificate_key)
        time.sleep(1)  # Sleep for 1 second
    except Exception as e:
        click.echo(f"Error getting the certificate key: {str(e)}")

if __name__ == "__main__":
    main()




