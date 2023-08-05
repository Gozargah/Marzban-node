from decouple import config
from dotenv import load_dotenv
import pathlib

load_dotenv()


SERVICE_PORT = config("SERVICE_PORT", cast=int, default=62050)

XRAY_API_PORT = config("XRAY_API_PORT", cast=int, default=62051)
XRAY_EXECUTABLE_PATH = config("XRAY_EXECUTABLE_PATH", default="/usr/local/bin/xray")
XRAY_ASSETS_PATH = config("XRAY_ASSETS_PATH", default="/usr/local/share/xray")

SSL_CERT_FILE = config("SSL_CERT_FILE", default="/var/lib/marzban-node/ssl_cert.pem")
SSL_KEY_FILE = config("SSL_KEY_FILE", default="/var/lib/marzban-node/ssl_key.pem")
NODE_IP_SAVE_PATH = config("NODE_IP_SAVE_PATH", default="/var/lib/marzban-node/node_ip.txt")

DEBUG = config("DEBUG", cast=bool, default=False)
