# Marzban Node

Marzban Node is a Python-based application that provides a service for managing an Xray core instance. It uses RPyC for remote procedure calls and Docker for containerization. The application is designed to be secure, using self-signed SSL certificates for communication between the service and its clients.

## Overview

The application consists of several Python scripts and configuration files:

- `build.yml`: A GitHub Actions workflow file for automating the process of building a Docker image and pushing it to Docker Hub and GitHub Container Registry.
- `certificate.py`: A Python script for generating a self-signed SSL certificate.
- `config.py`: A Python script for loading environment variables and providing default values for certain settings.
- `docker-compose.yml`: A Docker Compose file for defining and managing the application's services.
- `logger.py`: A Python script for setting up a logger for the application.
- `main.py`: The main entry point for the application. It sets up an SSL-authenticated RPyC server and starts it.
- `service.py`: A Python script that defines an RPyC service for managing an Xray core instance.
- `xray.py`: A Python script that defines a class for managing an Xray core instance.

## How to Use

1. Clone the repository to your local machine.

2. Install the necessary Python dependencies. These are not explicitly listed in the repository, but based on the import statements in the Python scripts, you will need the following packages:

   - `rpyc`
   - `OpenSSL`
   - `python-decouple`
   - `python-dotenv`
   - `logging`

   You can install these packages using pip:

   ```
   pip install rpyc pyOpenSSL python-decouple python-dotenv logging
   ```

3. Set up your environment variables in a `.env` file in the root directory of the project. The `config.py` script will load these variables when the application starts. The following variables are used:

   - `SERVICE_PORT`: The port that the service will listen on.
   - `XRAY_API_PORT`: The port that the Xray API will listen on.
   - `XRAY_EXECUTABLE_PATH`: The path to the Xray executable.
   - `XRAY_ASSETS_PATH`: The path to the Xray assets.
   - `SSL_CERT_FILE`: The path to the SSL certificate file.
   - `SSL_KEY_FILE`: The path to the SSL key file.
   - `DEBUG`: A boolean indicating whether the application is in debug mode.

4. Build the Docker image using the `docker-compose.yml` file:

   ```
   docker-compose up --build
   ```

5. Once the Docker image is built, you can start the application by running the `main.py` script:

   ```
   python main.py
   ```

   This will start the RPyC server and the Xray core instance.

6. Methods defined in the `service.py` script. These methods allow you to start, stop, and restart the Xray core instance, as well as fetch the Xray version.
