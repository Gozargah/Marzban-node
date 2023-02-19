from socket import socket

import rpyc

from logger import logger
from xray import XRayConfig, XRayCore


class XrayService(rpyc.Service):
    def __init__(self):
        self.core = None
        self.connection = None

    def on_connect(self, conn):
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

    def exposed_start(self, config: str):
        if self.core is not None:
            raise RuntimeError("Xray is started already")

        try:
            config = XRayConfig(config)
            self.core = XRayCore(config)

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

            self.core.start()
        except Exception as exc:
            logger.error(exc)
            raise exc

    def exposed_stop(self):
        if self.core is None:
            raise ProcessLookupError("Xray has not been started")
        self.core.stop()

    def exposed_restart(self):
        if self.core is None:
            raise ProcessLookupError("Xray has not been started")
        self.core.restart()
