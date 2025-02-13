import asyncio
import json
import re
import subprocess
from contextlib import asynccontextmanager
from weakref import WeakValueDictionary

from config import DEBUG, SSL_CERT_FILE, SSL_KEY_FILE, XRAY_API_HOST, XRAY_API_PORT
from logger import logger


class XRayConfig(dict):
    """
    Loads Xray config json
    config must contain an inbound with the API_INBOUND tag name which handles API requests
    """

    def __init__(self, config: str, peer_ip: str):
        config = json.loads(config)

        self.api_host = XRAY_API_HOST
        self.api_port = XRAY_API_PORT
        self.ssl_cert = SSL_CERT_FILE
        self.ssl_key = SSL_KEY_FILE
        self.peer_ip = peer_ip

        super().__init__(config)
        self._apply_api()

    def to_json(self, **json_kwargs):
        return json.dumps(self, **json_kwargs)

    def _apply_api(self):
        self["inbounds"] = [
            inbound for inbound in self.get('inbounds', [])
            if not (
                inbound.get('protocol') == 'dokodemo-door' and
                inbound.get('tag') == 'API_INBOUND'
            )
        ]

        routing = self.get('routing', {})
        rules = routing.get("rules", [])
        api_tag = self.get('api', {}).get('tag')
        if api_tag:
            new_rules = [
                rule for rule in rules
                if rule.get('outboundTag') != api_tag
            ]
            self['routing']['rules'] = new_rules
        else:
            self['routing']['rules'] = []


        self["api"] = {
            "services": [
                "HandlerService",
                "StatsService",
                "LoggerService"
            ],
            "tag": "API"
        }
        self["stats"] = {}
        inbound = {
            "listen": self.api_host,
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
            "source": [
                "127.0.0.1",
                self.peer_ip
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
                 executable_path: str = "/usr/bin/xray",
                 assets_path: str = "/usr/share/xray"):
        self.executable_path = executable_path
        self.assets_path = assets_path

        self.version = self.get_version()
        self.process = None
        self.restarting = False
        self._start_event = asyncio.Event()
        self._really_started = False

        self._logs_queue = asyncio.Queue(maxsize=100)
        self._client_queues = WeakValueDictionary()
        self._queue_lock = asyncio.Lock()


        self._on_start_funcs = []
        self._on_stop_funcs = []
        self._env = {
            "XRAY_LOCATION_ASSET": assets_path
        }

        self._log_processor_task = None
        self._is_shutting_down = False



    def get_version(self):
        cmd = [self.executable_path, "version"]
        try:
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode('utf-8')
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.error(f"Failed to get Xray version: {e}")
            return None
        m = re.match(r'^Xray (\d+\.\d+\.\d+)', output)
        if m:
            return m.group(1)
        logger.error(f"Xray version not found in output: {output}")
        return None

    async def __capture_process_logs(self):
        while self.process and self.started and not self._is_shutting_down:
            try:
                line = await asyncio.wait_for(self.process.stdout.readline(), timeout=1.0)
                if not line:
                    if self.process.poll() is not None:
                        logger.warning("Process ended unexpectedly")
                        break
                    continue

                output = line.decode('utf-8').strip()
                if not output:
                    continue

                try:
                    if not self._is_shutting_down:
                        await self._logs_queue.put(output)
                        if DEBUG:
                            logger.debug(output)
                        if f"Xray {self.version} started" in output:
                            self._start_event.set()
                except asyncio.QueueFull:
                    try:
                        await self._logs_queue.get()
                        await self._logs_queue.put(output)
                    except Exception as e:
                        logger.error(f"Error managing queue: {e}")

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error capturing logs: {e}")
                if not self._is_shutting_down:
                    await asyncio.sleep(0.1)

    async def _process_logs(self):
        while not self._is_shutting_down:
            try:
                try:
                    log = await asyncio.wait_for(self._logs_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                async with self._queue_lock:
                    current_queues = list(self._client_queues.items())

                for queue_id, queue in current_queues:
                    if queue_id not in self._client_queues:
                        continue
                    try:
                        await asyncio.wait_for(queue.put(log), timeout=0.1)
                    except asyncio.QueueFull:
                        try:
                            await queue.get()
                            await queue.put(log)
                        except Exception as e:
                            logger.error(f"Error managing client queue {queue_id}: {e}")
                    except asyncio.TimeoutError:
                        logger.warning(f"Timeout sending log to client {queue_id}")
                    except Exception as e:
                        logger.error(f"Error processing logs for client {queue_id}: {e}")

            except Exception as e:
                logger.error(f"Error in log processor: {e}")
                await asyncio.sleep(0.1)

    @asynccontextmanager
    async def get_logs(self):
        client_queue = asyncio.Queue(maxsize=100)
        queue_id = id(client_queue)

        async with self._queue_lock:
            self._client_queues[queue_id] = client_queue

        try:
            yield client_queue
        finally:
            async with self._queue_lock:
                self._client_queues.pop(queue_id, None)

    @property
    def started(self):
        if not self.process:
            return False

        return self._really_started

    async def start(self, config: XRayConfig):
        if self.started is True:
            raise RuntimeError("Xray is started already")

        self._is_shutting_down = False

        if config.get('log', {}).get('logLevel') in ('none', 'error'):
            config['log']['logLevel'] = 'warning'

        cmd = [
            self.executable_path,
            "run",
            '-config',
            'stdin:'
        ]

        self._start_event.clear()
        self._really_started = False
        try:
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                env=self._env,
                stdin=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
            )
        except Exception as e:
            logger.error(f"Failed to start process: {e}")
            raise RuntimeError(f"Failed to start Xray: {e}")

        config_json = config.to_json()
        try:
            self.process.stdin.write(config_json.encode('utf-8'))
            await self.process.stdin.drain()
            self.process.stdin.close()
            await self.process.stdin.wait_closed()
        except Exception as e:
            await self.stop()
            raise RuntimeError(f"Failed to write config: {e}")

        asyncio.create_task(self.__capture_process_logs())
        self._log_processor_task = asyncio.create_task(self._process_logs())

        try:
            await asyncio.wait_for(self._start_event.wait(), timeout=5)
            self._really_started = True
        except asyncio.TimeoutError:
            await self.stop()
            raise RuntimeError("Timeout waiting for Xray to start")

        for func in self._on_start_funcs:
            asyncio.create_task(func())

    async def stop(self):
        if not self.started and not self.process:
            return

        self._is_shutting_down = True

        if self._log_processor_task:
            self._log_processor_task.cancel()
            try:
                await self._log_processor_task
            except asyncio.CancelledError:
                pass

        if self.process:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5)
            except asyncio.TimeoutError:
                logger.warning("Xray process did not terminate gracefully, forcing kill")
                self.process.kill()
                await self.process.wait()

        self.process = None
        logger.warning("Xray core stopped")

        async with self._queue_lock:
            self._logs_queue = asyncio.Queue(maxsize=100)
            self._client_queues.clear()

        for func in self._on_stop_funcs:
            try:
                asyncio.create_task(func())
            except Exception as e:
                logger.error(f"Error executing stop function: {e}")

    async def restart(self, config: XRayConfig):
        if self.restarting is True:
            return

        self.restarting = True
        try:
            logger.warning("Restarting Xray core...")
            await self.stop()
            await self.start(config)
        finally:
            self.restarting = False

    def on_start(self, func: callable):
        self._on_start_funcs.append(func)
        return func

    def on_stop(self, func: callable):
        self._on_stop_funcs.append(func)
        return func
