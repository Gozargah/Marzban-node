import asyncio
import json
from uuid import UUID, uuid4

from fastapi import (APIRouter, Body, FastAPI, HTTPException, Request,
                     WebSocket, status)
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.websockets import WebSocketDisconnect, WebSocketState

from config import XRAY_ASSETS_PATH, XRAY_EXECUTABLE_PATH
from logger import logger
from xray import XRayConfig, XRayCore

app = FastAPI()


@app.exception_handler(RequestValidationError)
def validation_exception_handler(request: Request, exc: RequestValidationError):
    details = {}
    for error in exc.errors():
        details[error["loc"][-1]] = error.get("msg")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=jsonable_encoder({"detail": details}),
    )

@app.on_event("shutdown")
async def shutdown_event():
    if service.core.started:
        await service.core.stop()

class Service(object):
    def __init__(self):
        self.router = APIRouter()

        self.connected = False
        self.client_ip = None
        self.session_id = None
        self._conn_lock = asyncio.Lock()
        self._core_lock = asyncio.Lock()
        self.core = XRayCore(
            executable_path=XRAY_EXECUTABLE_PATH,
            assets_path=XRAY_ASSETS_PATH
        )
        self.core_version = self.core.get_version()
        self.config = None

        self.router.add_api_route("/", self.base, methods=["POST"])
        self.router.add_api_route("/ping", self.ping, methods=["POST"])
        self.router.add_api_route("/connect", self.connect, methods=["POST"])
        self.router.add_api_route("/disconnect", self.disconnect, methods=["POST"])
        self.router.add_api_route("/start", self.start, methods=["POST"])
        self.router.add_api_route("/stop", self.stop, methods=["POST"])
        self.router.add_api_route("/restart", self.restart, methods=["POST"])

        self.router.add_websocket_route("/logs", self.logs)

    async def match_session_id(self, session_id: UUID):
        async with self._conn_lock:
            if session_id != self.session_id:
                raise HTTPException(
                    status_code=403,
                    detail="Session ID mismatch."
                )
        return True

    async def response(self, **kwargs):
        async with self._conn_lock:
            return {
                "connected": self.connected,
                "started": self.core.started,
                "core_version": self.core_version,
                **kwargs
            }

    def base(self):
        return self.response()

    async def connect(self, request: Request):
        async with self._conn_lock:
            self.session_id = uuid4()
            self.client_ip = request.client.host

            if self.connected:
                logger.warning(
                    f'New connection from {self.client_ip}, Core control access was taken away from previous client.')
                if self.core.started:
                    try:
                        await self.core.stop()
                    except RuntimeError:
                        pass

            self.connected = True
            logger.info(f'{self.client_ip} connected, Session ID = "{self.session_id}".')

            return self.response(
                session_id=self.session_id
            )

    async def disconnect(self):
        async with self._conn_lock:
            if self.connected:
                logger.info(f'{self.client_ip} disconnected, Session ID = "{self.session_id}".')

            self.session_id = None
            self.client_ip = None

            if self.core.started:
                try:
                    await self.core.stop()
                    self.connected = False
                except RuntimeError:
                    pass
            return self.response()

    async def ping(self, session_id: UUID = Body(embed=True)):
        await self.match_session_id(session_id)
        return {}

    async def start(self, session_id: UUID = Body(embed=True), config: str = Body(embed=True)):
        await self.match_session_id(session_id)

        try:
            config = XRayConfig(config, self.client_ip)
        except json.decoder.JSONDecodeError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "config": f'Failed to decode config: {exc}'
                }
            )
        async with self._core_lock:
            try:
                await self.core.start(config)
            except Exception as exc:
                logger.error(f"Failed to start core with: {exc}")
                raise HTTPException(
                    status_code=503,
                    detail=str(exc)
                )

            if not self.core.started:
                raise HTTPException(
                    status_code=503,
                    detail="Xray core did not start properly."
                )

        return self.response()

    async def stop(self, session_id: UUID = Body(embed=True)):
        await self.match_session_id(session_id)
        async with self._core_lock:
            try:
                await self.core.stop()

            except RuntimeError:
                pass

        return self.response()

    async def restart(self, session_id: UUID = Body(embed=True), config: str = Body(embed=True)):
        await self.match_session_id(session_id)

        try:
            config = XRayConfig(config, self.client_ip)
        except json.decoder.JSONDecodeError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "config": f'Failed to decode config: {exc}'
                }
            )
        async with self._core_lock:
            try:
                await self.core.restart(config)
            except Exception as exc:
                logger.error(f"Failed to restart core with: {exc}")
                raise HTTPException(
                    status_code=503,
                    detail=str(exc)
                )

            if not self.core.started:
                raise HTTPException(
                    status_code=503,
                    detail="Xray core did not restart properly"
                )

        return self.response()

    async def logs(self, websocket: WebSocket):
        try:
            session_id = UUID(websocket.query_params.get('session_id'))
        except (TypeError, ValueError):
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        if session_id != self.session_id:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        try:
            interval = float(websocket.query_params.get('interval', 0))
        except ValueError:
            await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
            return

        if not (0 <= interval <= 10):
            await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
            return

        await websocket.accept()
        batch_logs = []

        try:
            async with self.core.get_logs() as log_queue:
                while True:
                    async with self._conn_lock:
                        if not self.connected:
                            break
                    try:
                        if interval > 0:
                            await asyncio.sleep(interval)
                            batch_logs.clear()

                            while len(batch_logs) < 100:
                                try:
                                    log = log_queue.get_nowait()
                                    batch_logs.append(log)
                                except asyncio.QueueEmpty:
                                    break
                            if batch_logs:
                                await websocket.send_text('\n'.join(batch_logs))
                        else:
                            try:
                                log = await asyncio.wait_for(log_queue.get(), timeout=1.0)
                                await websocket.send_text(log)
                            except asyncio.TimeoutError:
                                continue
                    except WebSocketDisconnect:
                        logger.info("WebSocket disconnected normally")
                        break
                    except Exception as e:
                        logger.error(f"WebSocket error: {e}")
                        break

        except Exception as e:
            logger.error(f"Error in WebSocket connection: {e}")
        finally:
            try:
                await websocket.close()
            except Exception as e:
                logger.error(f"Error closing WebSocket: {e}")


service = Service()
app.include_router(service.router)
