# marzban_utils.py
import subprocess
import os
import time
import click


def update_marzban_node():
    click.echo("Updating Marzban-node...")
    marzban_node_directory = find_marzban_node_directory()

    if marzban_node_directory:
        try:
            os.chdir(marzban_node_directory)
            subprocess.run(['git', 'pull'])
            subprocess.run(['docker-compose', 'up', '-d'])
            click.echo("Marzban-node container is running.")
            click.echo("Please wait a few moments for it to fully initialize.")
            click.echo("You can check the status using 'docker-compose ps'.")
            time.sleep(5)  # Sleep for 5 seconds
        except Exception as e:
            click.echo(f"Error updating Marzban-node: {str(e)}")
    else:
        click.echo(
            "Marzban-node directory not found. You may need to clone it first or it's not installed system-wide.")

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

def get_certificate_key():
    click.echo("Getting the certificate key...")
    try:
        with open('/var/lib/marzban-node/ssl_cert.pem', 'r') as f:
            certificate_key = f.read()
        click.echo(certificate_key)
        time.sleep(1)  # Sleep for 1 second
    except Exception as e:
        click.echo(f"Error getting the certificate key: {str(e)}")