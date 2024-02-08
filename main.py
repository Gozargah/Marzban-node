import os

import uvicorn
from rpyc.utils.authenticators import SSLAuthenticator
from rpyc.utils.server import ThreadedServer

import rest_service
import rpyc_service
from certificate import generate_certificate
from config import (SERVICE_PORT, SERVICE_PROTOCOL, SSL_CERT_FILE,
                    SSL_CLIENT_CERT_FILE, SSL_KEY_FILE)
from logger import logger


def generate_ssl_files():
    pems = generate_certificate()

    with open(SSL_KEY_FILE, 'w') as f:
        f.write(pems['key'])

    with open(SSL_CERT_FILE, 'w') as f:
        f.write(pems['cert'])


if __name__ == "__main__":
    if not all((os.path.isfile(SSL_CERT_FILE),
                os.path.isfile(SSL_KEY_FILE))):
        generate_ssl_files()

    if not SSL_CLIENT_CERT_FILE:
        logger.warning(
            "You are running node without SSL_CLIENT_CERT_FILE, be aware that everyone can connect to this node and this isn't secure!")

    if SSL_CLIENT_CERT_FILE and not os.path.isfile(SSL_CLIENT_CERT_FILE):
        logger.error("Client's certificate file specified on SSL_CLIENT_CERT_FILE is missing")
        exit(0)

    if SERVICE_PROTOCOL == 'rpyc':
        authenticator = SSLAuthenticator(keyfile=SSL_KEY_FILE,
                                         certfile=SSL_CERT_FILE,
                                         ca_certs=SSL_CLIENT_CERT_FILE or None)
        thread = ThreadedServer(rpyc_service.XrayService(),
                                port=SERVICE_PORT,
                                authenticator=authenticator)
        logger.info(f"Node service running on :{SERVICE_PORT}")
        thread.start()

    elif SERVICE_PROTOCOL == 'rest':
        if not SSL_CLIENT_CERT_FILE:
            logger.error("SSL_CLIENT_CERT_FILE is required for rest service.")
            exit(0)

        logger.info(f"Node service running on :{SERVICE_PORT}")
        uvicorn.run(
            rest_service.app,
            host="0.0.0.0",
            port=SERVICE_PORT,
            ssl_keyfile=SSL_KEY_FILE,
            ssl_certfile=SSL_CERT_FILE,
            ssl_ca_certs=SSL_CLIENT_CERT_FILE,
            ssl_cert_reqs=2
        )

    else:
        logger.error("SERVICE_PROTOCOL is not any of (rpyc, rest).")
        exit(0)
