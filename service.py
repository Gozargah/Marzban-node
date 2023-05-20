from socket import socket

import rpyc

from config import XRAY_ASSETS_PATH, XRAY_EXECUTABLE_PATH
from logger import logger
from xray import XRayConfig, XRayCore


@rpyc.service
class XrayService(rpyc.Service):
    def __init__(self):
        self.core = None
        self.connection = None
        self.pinging = False

    def on_connect(self, conn):
        if self.connection and not self.pinging:
            self.pinging = True
            connection = self.connection
            tries = 0
            while True:
                tries += 1
                try:
                    connection.ping(timeout=3)
                    self.pinging = False
                    break
                except Exception:
                    if tries <= 3:
                        continue

                    if connection is self.connection:
                        logger.warning(f'Previous connection lost, unable to connect to {connection.peer}')
                        if self.core is not None:
                            self.core.stop()
                        self.core = None
                        self.connection = None

                        try:
                            connection.close()
                        except Exception:
                            pass

                    self.pinging = False
                    break

        if self.connection:
            logger.warning(f'New connection rejected, already connected to {self.connection.peer}')
            return conn.close()

        peer, _ = socket.getpeername(conn._channel.stream.sock)
        self.connection = conn
        self.connection.peer = peer
        logger.warning(f'Connected to {self.connection.peer}')

    def on_disconnect(self, conn):
        if conn is self.connection:
            logger.warning(f'Disconnected from {self.connection.peer}')

            if self.core is not None:
                self.core.stop()

            self.core = None
            self.connection = None

    @rpyc.exposed
    def start(self, config: str):
        if self.core is not None:
            self.stop()

        try:
            config = XRayConfig(config)
            self.core = XRayCore(executable_path=XRAY_EXECUTABLE_PATH,
                                 assets_path=XRAY_ASSETS_PATH)

            if hasattr(self.connection.root, 'on_start'):
                @self.core.on_start
                def on_start():
                    try:
                        if self.connection:
                            self.connection.root.on_start()
                    except Exception as exc:
                        logger.debug('Peer on_start exception:', exc)
            else:
                logger.debug("Peer doesn't have on_start function on it's service, skipped")

            if hasattr(self.connection.root, 'on_stop'):
                @self.core.on_stop
                def on_stop():
                    try:
                        if self.connection:
                            self.connection.root.on_stop()
                    except Exception as exc:
                        logger.debug('Peer on_stop exception:', exc)
            else:
                logger.debug("Peer doesn't have on_stop function on it's service, skipped")

            self.core.start(config)
        except Exception as exc:
            logger.error(exc)
            raise exc

    @rpyc.exposed
    def stop(self):
        if self.core:
            try:
                self.core.stop()
            except RuntimeError:
                pass
        self.core = None

    @rpyc.exposed
    def restart(self, config: str):
        config = XRayConfig(config)
        self.core.restart(config)

    @rpyc.exposed
    def fetch_xray_version(self):
        if self.core is None:
            raise ProcessLookupError("Xray has not been started")

        return self.core.version

    @rpyc.exposed
    def fetch_logs(self):
        if self.core is None:
            raise ProcessLookupError("Xray has not been started")
        logs_tail = ""
        log_count = 0
        with xray.core.get_logs() as logs:
            if not logs:
                return ""

            while log_count < 10:
                log_count += 1
                log = logs.popleft()
                logs_tail += "\n" + log

        return logs_tail
