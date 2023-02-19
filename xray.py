import atexit
import json
import subprocess

from config import SSL_CERT_FILE, SSL_KEY_FILE, XRAY_API_PORT

from logger import logger


class XRayConfig(dict):
    """
    Loads Xray config json
    config must contain an inbound with the API_INBOUND tag name which handles API requests
    """

    def __init__(self, config: str):
        config = json.loads(config)

        self.api_port = XRAY_API_PORT
        self.ssl_cert = SSL_CERT_FILE
        self.ssl_key = SSL_KEY_FILE

        super().__init__(config)
        self._apply_api()

    def to_json(self, **json_kwargs):
        return json.dumps(self, **json_kwargs)

    def _apply_api(self):
        for inbound in self.get('inbounds', []):
            if inbound.get('protocol') == 'dokodemo-door':
                self['inbounds'].remove(inbound)

        for rule in self.get('routing', {}).get("rules", []):
            api_tag = self.get('api', {}).get('tag')
            if api_tag and rule.get('outboundTag') == api_tag:
                self['routing']['rules'].remove(rule)

        self["api"] = {
            "services": [
                "HandlerService",
                "StatsService",
                "LoggerService"
            ],
            "tag": "API"
        }
        self["stats"] = {}
        self["policy"] = {
            "levels": {
                "0": {
                    "statsUserUplink": True,
                    "statsUserDownlink": True
                }
            },
            "system": {
                "statsInboundDownlink": False,
                "statsInboundUplink": False,
                "statsOutboundDownlink": True,
                "statsOutboundUplink": True
            }
        }
        inbound = {
            "listen": "0.0.0.0",
            "port": self.api_port,
            "protocol": "dokodemo-door",
            "settings": {
                "address": "127.0.0.1"
            },
            "streamSettings": {
                "security": "tls",
                "tlsSettings": {
                    "certificates": [
                        {
                            "certificateFile": self.ssl_cert,
                            "keyFile": self.ssl_key
                        }
                    ]
                }
            },
            "tag": "API_INBOUND"
        }
        try:
            self["inbounds"].insert(0, inbound)
        except KeyError:
            self["inbounds"] = []
            self["inbounds"].insert(0, inbound)

        rule = {
            "inboundTag": [
                "API_INBOUND"
            ],
            "outboundTag": "API",
            "type": "field"
        }
        try:
            self["routing"]["rules"].insert(0, rule)
        except KeyError:
            self["routing"] = {"rules": []}
            self["routing"]["rules"].insert(0, rule)


class XRayCore:
    def __init__(self,
                 config: XRayConfig,
                 executable_path: str = "/usr/local/bin/xray",
                 assets_path: str = "/usr/local/share/xray"):
        self.executable_path = executable_path
        self.assets_path = assets_path
        self.started = False
        self.config = config
        self._process = None
        self._on_start_funcs = []
        self._on_stop_funcs = []
        self._env = {
            "XRAY_LOCATION_ASSET": assets_path
        }

        @atexit.register
        def stop_core():
            if self.started:
                self.stop()

    @property
    def process(self):
        if self._process is None:
            raise ProcessLookupError("Xray has not been started")
        return self._process

    def start(self):
        if self.started is True:
            raise RuntimeError("Xray is started already")

        if self.config.get('log', {}).get('logLevel') in ('none', 'error'):
            self.config['log']['logLevel'] = 'warning'

        cmd = [
            self.executable_path,
            "run",
            '-config',
            'stdin:'
        ]
        self._process = subprocess.Popen(
            cmd,
            env=self._env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE
        )
        self._process.stdin.write(
            self.config.to_json().encode()
        )
        self._process.stdin.flush()
        self._process.stdin.close()

        # Wait for XRay to get started
        while _ := self._process.stdout.readline().decode().strip('\n'):
            log = _
            logger.debug(log)
            if 'core: Xray' in log and 'started' in log:
                logger.warning(log)
                self.started = True
                break

        if not self.started:
            raise RuntimeError("Failed to run XRay", log)

        # execute on start functions
        for func in self._on_start_funcs:
            func()

    def stop(self):
        self.process.terminate()
        self.started = False
        self._process = None
        logger.warning("Xray stopped")

        # execute on stop functions
        for func in self._on_stop_funcs:
            func()

    def restart(self):
        self.stop()
        self.start()

    def on_start(self, func: callable):
        self._on_start_funcs.append(func)
        return func

    def on_stop(self, func: callable):
        self._on_stop_funcs.append(func)
        return func
