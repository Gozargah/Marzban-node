import click
import subprocess
import os
import network_utils
import docker_utils
import marzban_utils



# Define DNS settings
DNS_PRIMARY = "185.51.200.2"
DNS_FALLBACK = "178.22.122.100"


@click.group()
def cli():
    pass

@cli.command()
def install():
    docker_utils.install_docker_and_compose()
    marzban_utils.install_marzban_node()



@cli.command()
def add_container():
    marzban_node_dir = marzban_utils.find_marzban_node_directory()
    if marzban_node_dir:
        used_ports = set()
        docker_utils.edit_docker_compose(marzban_node_dir, used_ports)
    else:
        print("Marzban-node directory not found.")


@cli.command()
def up():
    marzban_node_dir = marzban_utils.find_marzban_node_directory()
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
    marzban_node_dir = marzban_utils.find_marzban_node_directory()
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
    marzban_utils.find_marzban_node_directory()
    marzban_utils.update_marzban_node()
    marzban_utils.get_certificate_key()


@cli.command()
def dns():
    option = network_utils.get_dns_configuration_option()

    if option == '1':
        network_utils.modify_dns_settings(DNS_PRIMARY, DNS_FALLBACK)
    elif option == '2':
        network_utils.modify_dns_settings("10.202.10.202", "10.202.10.102")
    elif option == '3':
        custom_dns_primary = click.prompt("Enter primary DNS server:")
        custom_dns_secondary = click.prompt("Enter secondary DNS server:")
        network_utils.modify_dns_settings(custom_dns_primary, custom_dns_secondary)
    else:
        click.echo("Invalid option selected.")
    docker_utils.install_docker_and_compose()
    marzban_utils.install_marzban_node()
    marzban_utils.get_certificate_key()
    marzban_utils.install_git()


@cli.command()
def certificate():
    marzban_utils.get_certificate_key()


@cli.command()
@click.option('--option', type=click.Choice(['1', '2', '3']), default='1',
              prompt="Choose DNS configuration option for adjusting DNS settings:\n1. Use recommended DNS servers\n2. "
                     "Use predefined DNS servers\n3. Enter custom DNS servers")
def adjust_dns(option):
    if option == '1':
        network_utils.modify_dns_settings(DNS_PRIMARY, DNS_FALLBACK)
    elif option == '2':
        network_utils.modify_dns_settings("10.202.10.202", "10.202.10.102")
    elif option == '3':
        custom_dns_primary = click.prompt("Enter primary DNS server:")
        custom_dns_secondary = click.prompt("Enter secondary DNS server:")
        network_utils.modify_dns_settings(custom_dns_primary, custom_dns_secondary)
    else:
        click.echo("Invalid option selected.")


@cli.command()
def tor():
    network_utils.install_docker_with_tor()
    marzban_utils.install_marzban_node()
    marzban_utils.get_certificate_key()


@cli.command()
def help():
    show_help()


def show_help():
    # Display help message
    click.echo("Marzban-node Installation Script")
    click.echo("--------------------------------")
    click.echo("This script assists in installing Marzban-node.")
    click.echo("Commands:")
    click.echo("  dns: Install for Iranian server with DNS modification.")
    click.echo("  certificate: Get the certificate key.")
    click.echo("  update: Update latest version.")
    click.echo("  adjust-dns: Adjust DNS settings only (implies dns).")
    click.echo("  help: Show the help message.")


if __name__ == '__main__':
    cli()
