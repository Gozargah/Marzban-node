import atexit
import json
import re
import subprocess
import threading
from collections import deque
from contextlib import contextmanager

from node_ip import NodeIP
from config import DEBUG, SSL_CERT_FILE, SSL_KEY_FILE, XRAY_API_PORT, NODE_IP_SAVE_PATH
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
        current_node_ip = NodeIP(logger, save_path=NODE_IP_SAVE_PATH).get_node_ip(3)
        current_node_inbounds = []

        for inbound in self.get("inbounds", []):
            if inbound.get("protocol") == "dokodemo-door":
                self["inbounds"].remove(inbound)

            node_ips_obj = inbound.get("node_ips")
            if node_ips_obj is None:
                pass
            elif type(node_ips_obj) is not list:
                raise ValueError(
                    f"'node_ips' Must be a 'list' not {type(node_ips_obj)}!"
                )
            else:
                for received_ip in node_ips_obj:
                    if received_ip == current_node_ip:
                        # if received_ip was matched : only these inbounds will be placed in xray inbounds
                        current_node_inbounds.append(inbound)
                        break

        if len(current_node_inbounds) == 0:
            # if no node_ip was matched or admin didn't use the feature : add all inbound like before.
            current_node_inbounds = self["inbounds"]

        for rule in self.get("routing", {}).get("rules", []):
            api_tag = self.get("api", {}).get("tag")
            if api_tag and rule.get("outboundTag") == api_tag:
                self["routing"]["rules"].remove(rule)

        self["api"] = {
            "services": [
                "HandlerService",
                "StatsService",
                "LoggerService",
            ],
            "tag": "API",
        }
        self["stats"] = {}
        self["policy"] = {
            "levels": {
                "0": {
                    "statsUserUplink": True,
                    "statsUserDownlink": True,
                },
            },
            "system": {
                "statsInboundDownlink": False,
                "statsInboundUplink": False,
                "statsOutboundDownlink": True,
                "statsOutboundUplink": True,
            },
        }
        api_inbound = {
            "listen": "0.0.0.0",
            "port": self.api_port,
            "protocol": "dokodemo-door",
            "settings": {"address": "127.0.0.1"},
            "streamSettings": {
                "security": "tls",
                "tlsSettings": {
                    "certificates": [
                        {"certificateFile": self.ssl_cert, "keyFile": self.ssl_key}
                    ]
                },
            },
            "tag": "API_INBOUND",
        }
        try:
            current_node_inbounds.insert(0, api_inbound)
        except KeyError:
            current_node_inbounds = []
            current_node_inbounds.insert(0, api_inbound)

        self["inbounds"] = current_node_inbounds

        api_rule = {
            "inboundTag": ["API_INBOUND"],
            "outboundTag": "API",
            "type": "field",
        }
        try:
            self["routing"]["rules"].insert(0, api_rule)
        except KeyError:
            self["routing"] = {"rules": []}
            self["routing"]["rules"].insert(0, api_rule)


class XRayCore:
    def __init__(
        self,
        executable_path: str = "/usr/bin/xray",
        assets_path: str = "/usr/share/xray",
    ):
        self.executable_path = executable_path
        self.assets_path = assets_path

        self.version = self.get_version()
        self.process = None
        self.restarting = False

        self._logs_buffer = deque(maxlen=100)
        self._temp_log_buffers = []
        self._on_start_funcs = []
        self._on_stop_funcs = []
        self._env = {"XRAY_LOCATION_ASSET": assets_path}

        atexit.register(lambda: self.stop() if self.started else None)

    def get_version(self):
        cmd = [self.executable_path, "version"]
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode("utf-8")
        m = re.match(r"^Xray (\d+\.\d+\.\d+)", output)
        if m:
            return m.groups()[0]

    def __capture_process_logs(self):
        def capture_and_debug_log():
            while self.process:
                output = self.process.stdout.readline()
                if output:
                    output = output.strip()
                    self._logs_buffer.append(output)
                    for buf in self._temp_log_buffers:
                        buf.append(output)
                    logger.debug(output)

                elif not self.process or self.process.poll() is not None:
                    break

        def capture_only():
            while self.process:
                output = self.process.stdout.readline()
                if output:
                    output = output.strip()
                    self._logs_buffer.append(output)
                    for buf in self._temp_log_buffers:
                        buf.append(output)

                elif not self.process or self.process.poll() is not None:
                    break

        if DEBUG:
            threading.Thread(target=capture_and_debug_log).start()
        else:
            threading.Thread(target=capture_only).start()

    @contextmanager
    def get_logs(self):
        buf = deque(self._logs_buffer, maxlen=100)
        try:
            self._temp_log_buffers.append(buf)
            yield buf
        except (EOFError, TimeoutError):
            pass
        finally:
            self._temp_log_buffers.remove(buf)

    @property
    def started(self):
        if not self.process:
            return False

        if self.process.poll() is None:
            return True

        return False

    def start(self, config: XRayConfig):
        if self.started is True:
            raise RuntimeError("Xray is started already")

        if config.get("log", {}).get("logLevel") in ("none", "error"):
            config["log"]["logLevel"] = "warning"

        cmd = [self.executable_path, "run", "-config", "stdin:"]
        self.process = subprocess.Popen(
            cmd,
            env=self._env,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            universal_newlines=True,
        )
        self.process.stdin.write(config.to_json())
        self.process.stdin.flush()
        self.process.stdin.close()

        self.__capture_process_logs()

        # execute on start functions
        for func in self._on_start_funcs:
            threading.Thread(target=func).start()

    def stop(self):
        if not self.started:
            return

        self.process.terminate()
        self.process = None
        logger.warning("Xray core stopped")

        # execute on stop functions
        for func in self._on_stop_funcs:
            threading.Thread(target=func).start()

    def restart(self, config: XRayConfig):
        if self.restarting is True:
            return

        self.restarting = True
        try:
            logger.warning("Restarting Xray core...")
            self.stop()
            self.start(config)
        finally:
            self.restarting = False

    def on_start(self, func: callable):
        self._on_start_funcs.append(func)
        return func

    def on_stop(self, func: callable):
        self._on_stop_funcs.append(func)
        return func
