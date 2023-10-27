import os

from rpyc.utils.authenticators import SSLAuthenticator
from rpyc.utils.server import ThreadedServer

from certificate import generate_certificate
from config import SERVICE_PORT, SSL_CERT_FILE, SSL_KEY_FILE, SSL_CLIENT_CERT_FILE
from logger import logger
from service import XrayService


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

    authenticator = SSLAuthenticator(keyfile=SSL_KEY_FILE,
                                     certfile=SSL_CERT_FILE,
                                     ca_certs=SSL_CLIENT_CERT_FILE or None)
    thread = ThreadedServer(XrayService(),
                            port=SERVICE_PORT,
                            authenticator=authenticator)

    logger.info(f"Node service running on :{SERVICE_PORT}")
    thread.start()
