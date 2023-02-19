from decouple import config
from dotenv import load_dotenv

load_dotenv()


SERVICE_PORT = config('SERVICE_PORT', cast=int, default=62050)
XRAY_API_PORT = config('XRAY_API_PORT', cast=int, default=62051)
SSL_CERT_FILE = config("SSL_CERT_FILE", default="/var/lib/marzban-node/ssl_cert.pem")
SSL_KEY_FILE = config("SSL_KEY_FILE", default="/var/lib/marzban-node/ssl_key.pem")
