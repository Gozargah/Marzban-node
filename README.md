# Marzban Node

Marzban Node is a Python-based application that uses Docker for containerization and GitHub Actions for CI/CD. It leverages the RPyC library for remote procedure calls and Xray for network analysis. The application is designed to be run as a service, with configuration options provided through environment variables.

## Overview

The application consists of several Python scripts and a Docker configuration:

- `build.yml`: A GitHub Actions workflow that builds and pushes Docker images to Docker Hub and GitHub Container Registry when a new tag is pushed to the repository.
- `certificate.py`: Generates a self-signed SSL certificate.
- `config.py`: Loads environment variables for configuration.
- `docker-compose.yml`: Defines the Docker service for the application.
- `logger.py`: Sets up a logger with color-coded output.
- `main.py`: The entry point for the application. It generates SSL files if they don't exist, sets up an SSL authenticator, and starts the service.
- `service.py`: Defines the XrayService class, which is exposed over RPyC.
- `xray.py`: Manages the Xray core, including starting, stopping, and restarting it.

## How to Use

### Prerequisites

- Docker
- Python 3.6 or higher
- GitHub account (for CI/CD)

### Steps

1. Clone the repository to your local machine.
2. Set the necessary environment variables in a `.env` file in the root directory of the project. The following variables are used:

```
SERVICE_PORT=62050
XRAY_API_PORT=62051
XRAY_EXECUTABLE_PATH=/usr/local/bin/xray
XRAY_ASSETS_PATH=/usr/local/share/xray
SSL_CERT_FILE=/var/lib/marzban-node/ssl_cert.pem
SSL_KEY_FILE=/var/lib/marzban-node/ssl_key.pem
DEBUG=False
```

3. Build the Docker image using the command `docker-compose build`.
4. Run the Docker container using the command `docker-compose up`.

## CI/CD

The application uses GitHub Actions for CI/CD. When a new tag is pushed to the repository, the `build.yml` workflow is triggered. This workflow builds a new Docker image and pushes it to Docker Hub and GitHub Container Registry.

## SSL

The application uses SSL for secure communication. The `certificate.py` script generates a self-signed SSL certificate if one does not already exist.

## Logging

The application uses a custom logger defined in `logger.py`. The logger outputs color-coded messages to the console.

## Xray Service

The application exposes an XrayService over RPyC. This service allows remote clients to start, stop, and restart the Xray core, as well as fetch the Xray version.

## Xray Core

The Xray core is managed by the `xray.py` script. This script starts, stops, and restarts the Xray core, and also provides hooks for functions to be run when the core is started or stopped.
