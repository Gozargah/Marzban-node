from decouple import config
from dotenv import load_dotenv

load_dotenv()

SERVICE_HOST = config("SERVICE_HOST", default="0.0.0.0")
SERVICE_PORT = config('SERVICE_PORT', cast=int, default=62050)

XRAY_API_HOST = config("XRAY_API_HOST", default="0.0.0.0")
XRAY_API_PORT = config('XRAY_API_PORT', cast=int, default=62051)
XRAY_EXECUTABLE_PATH = config("XRAY_EXECUTABLE_PATH", default="/usr/local/bin/xray")
XRAY_ASSETS_PATH = config("XRAY_ASSETS_PATH", default="/usr/local/share/xray")

SSL_CERT_FILE = config("SSL_CERT_FILE", default="/var/lib/marzban-node/ssl_cert.pem")
SSL_KEY_FILE = config("SSL_KEY_FILE", default="/var/lib/marzban-node/ssl_key.pem")
SSL_CLIENT_CERT_FILE = config("SSL_CLIENT_CERT_FILE", default="")

DEBUG = config("DEBUG", cast=bool, default=False)

SERVICE_PROTOCOL = config('SERVICE_PROTOCOL', cast=str, default='rest')

INBOUNDS = config("INBOUNDS", cast=lambda v: [x.strip() for x in v.split(',')] if v else [], default="")

# MTProto (Telemt sidecar on selected node)
MTPROTO_ENABLED = config("MTPROTO_ENABLED", cast=bool, default=False)
MTPROTO_DOMAIN = config("MTPROTO_DOMAIN", default="")
MTPROTO_PORT = config("MTPROTO_PORT", cast=int, default=1443)
MTPROTO_MODE = config("MTPROTO_MODE", default="dd").strip().lower()
MTPROTO_TLS_DOMAIN = config("MTPROTO_TLS_DOMAIN", default="")
MTPROTO_USE_MIDDLE_PROXY = config("MTPROTO_USE_MIDDLE_PROXY", cast=bool, default=False)
MTPROTO_LISTEN_ADDR_IPV4 = config("MTPROTO_LISTEN_ADDR_IPV4", default="0.0.0.0")
MTPROTO_IPV6_ENABLED = config("MTPROTO_IPV6_ENABLED", cast=bool, default=False)
MTPROTO_NETWORK_PREFER = config("MTPROTO_NETWORK_PREFER", cast=int, default=4)
MTPROTO_SHOW_LINKS = config("MTPROTO_SHOW_LINKS", cast=bool, default=False)
MTPROTO_LOG_LEVEL = config("MTPROTO_LOG_LEVEL", default="normal").strip().lower()
MTPROTO_RUST_LOG = config("MTPROTO_RUST_LOG", default="info,telemt::links=warn")
MTPROTO_RELOAD_INTERVAL = config("MTPROTO_RELOAD_INTERVAL", cast=int, default=5)
MTPROTO_CLIENT_HANDSHAKE_TIMEOUT = config(
    "MTPROTO_CLIENT_HANDSHAKE_TIMEOUT", cast=int, default=15
)
MTPROTO_TG_CONNECT_TIMEOUT = config(
    "MTPROTO_TG_CONNECT_TIMEOUT", cast=int, default=10
)
MTPROTO_CLIENT_KEEPALIVE_TIMEOUT = config(
    "MTPROTO_CLIENT_KEEPALIVE_TIMEOUT", cast=int, default=60
)
MTPROTO_CLIENT_ACK_TIMEOUT = config(
    "MTPROTO_CLIENT_ACK_TIMEOUT", cast=int, default=300
)
MTPROTO_CONFIG_PATH = config(
    "MTPROTO_CONFIG_PATH",
    default="/var/lib/marzban-node/mtproto/telemt.toml",
)

# Hysteria2 (external hysteriad sidecar)
# Set HYSTERIA2_ENABLED=true to start hysteriad alongside this node
HYSTERIA2_ENABLED = config("HYSTERIA2_ENABLED", cast=bool, default=False)
HYSTERIA2_PORT = config("HYSTERIA2_PORT", cast=int, default=2083)
# URL of the MAIN Marzban server auth endpoint (not this node)
HYSTERIA2_MARZBAN_URL = config("HYSTERIA2_MARZBAN_URL", default="")
# Must match HYSTERIA2_HOOK_TOKEN in main Marzban .env
HYSTERIA2_HOOK_TOKEN = config("HYSTERIA2_HOOK_TOKEN", default="")
HYSTERIA2_TRAFFIC_SECRET = config("HYSTERIA2_TRAFFIC_SECRET", default="")
# Must bind 0.0.0.0 so the main Marzban panel can poll /traffic (127.0.0.1 is only for local hysteria on the panel host).
HYSTERIA2_TRAFFIC_LISTEN = config("HYSTERIA2_TRAFFIC_LISTEN", default="0.0.0.0:9999")
HYSTERIA2_UP_MBPS = config("HYSTERIA2_UP_MBPS", cast=int, default=500)
HYSTERIA2_DOWN_MBPS = config("HYSTERIA2_DOWN_MBPS", cast=int, default=500)
# TLS cert for hysteriad — defaults to the node's own SSL cert
HYSTERIA2_CERT_FILE = config("HYSTERIA2_CERT_FILE", default=SSL_CERT_FILE)
HYSTERIA2_KEY_FILE = config("HYSTERIA2_KEY_FILE", default=SSL_KEY_FILE)
