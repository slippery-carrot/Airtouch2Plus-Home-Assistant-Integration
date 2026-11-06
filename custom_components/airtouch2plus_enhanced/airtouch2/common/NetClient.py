"""Maintain one TCP session with supervised reads and coordinated reconnects."""

import asyncio
import logging
from typing import Callable

from airtouch2.common.interfaces import Callback, CoroCallback, Serializable, TaskCreator

_LOGGER = logging.getLogger(__name__)

CONNECT_TIMEOUT_SECONDS = 10
WRITE_TIMEOUT_SECONDS = 10
CLOSE_TIMEOUT_SECONDS = 3
RECONNECT_MAX_DELAY_SECONDS = 10


class NetClient:
    """TCP transport: the read supervisor alone owns reconnect attempts."""

    def __init__(
        self,
        host: str,
        port: int,
        on_connect: CoroCallback,
        handle_message: CoroCallback,
        task_creator: TaskCreator = asyncio.create_task,
        on_disconnect: Callback | None = None,
    ):
        self._host_ip = host
        self._host_port = port
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._task_creator: Callable = task_creator
        self._main_loop_task: asyncio.Task[None] | None = None
        self._stop = False
        self._write_lock = asyncio.Lock()
        self._on_connect = on_connect
        self._handle_message = handle_message
        self._on_disconnect = on_disconnect

    async def connect(self) -> bool:
        """Establish a session; return False for a failed connection attempt."""
        if self._writer is not None:
            raise RuntimeError("TCP connection already established")

        _LOGGER.debug("Connecting to %s:%s", self._host_ip, self._host_port)
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self._host_ip, self._host_port),
                timeout=CONNECT_TIMEOUT_SECONDS,
            )
            # Request initial controller status through the new session.
            await self._on_connect()
            return True
        except asyncio.CancelledError:
            await self._close_connection()
            raise
        except (OSError, asyncio.TimeoutError, ConnectionError) as exc:
            _LOGGER.warning("AirTouch TCP connect failed: %s", exc)
            await self._close_connection()
            return False
        except Exception:
            await self._close_connection()
            raise

    def run(self) -> None:
        """Start the supervised read loop, after the initial connection."""
        if self._main_loop_task is not None and not self._main_loop_task.done():
            raise RuntimeError("TCP listener already running")
        self._stop = False
        self._main_loop_task = self._task_creator(
            self._main(), name="AirTouch TCP supervisor"
        )
        self._main_loop_task.add_done_callback(self._on_main_task_done)

    def _on_main_task_done(self, task: asyncio.Task) -> None:
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            _LOGGER.error("TCP supervisor stopped unexpectedly: %r", error)
        elif not self._stop:
            _LOGGER.error("TCP supervisor exited unexpectedly")

    async def stop(self) -> None:
        """Stop retries and processing, then close the TCP socket."""
        self._stop = True
        task = self._main_loop_task
        self._main_loop_task = None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        await self._close_connection()

    async def send(self, message: Serializable) -> None:
        """Write once or raise; never replay a possibly-executed AC command."""
        data = message.to_bytes()
        async with self._write_lock:
            writer = self._writer
            if writer is None or writer.is_closing():
                raise ConnectionError("AirTouch TCP session is disconnected")
            try:
                _LOGGER.debug("Sending %s: %s", type(message).__name__, data.hex(":"))
                writer.write(data)
                await asyncio.wait_for(writer.drain(), timeout=WRITE_TIMEOUT_SECONDS)
                if self._writer is not writer:
                    raise ConnectionError("TCP session changed during send")
            except (OSError, asyncio.TimeoutError, ConnectionError) as exc:
                # Closing wakes the read supervisor, which alone reconnects.
                # A failed drain cannot establish whether the command arrived.
                await self._close_connection(expected_writer=writer)
                raise ConnectionError(
                    "AirTouch TCP write failed; command was not retried"
                ) from exc

    async def read_bytes(self, size: int) -> bytes:
        """Read a frame fragment; let the supervisor handle failed reads."""
        reader = self._reader
        if reader is None:
            raise ConnectionError("AirTouch TCP session is disconnected")
        try:
            return await reader.readexactly(size)
        except (asyncio.IncompleteReadError, OSError) as exc:
            raise ConnectionError("AirTouch TCP read interrupted") from exc

    async def _main(self) -> None:
        """Recover from socket errors and unexpected message-parser failures."""
        while not self._stop:
            try:
                if self._writer is None:
                    await self._reconnect()
                    continue
                await self._handle_message()
            except asyncio.CancelledError:
                raise
            except Exception:
                _LOGGER.exception("AirTouch TCP reader failed; resetting session")
                await self._close_connection()
                if not self._stop:
                    await asyncio.sleep(1)

    async def _reconnect(self) -> None:
        """Keep retrying with bounded backoff; only one task performs retries."""
        retry = 0
        while not self._stop and self._writer is None:
            try:
                if await self.connect():
                    _LOGGER.info("AirTouch TCP connection restored")
                    return
            except asyncio.CancelledError:
                raise
            except Exception:
                _LOGGER.exception("AirTouch TCP reconnect setup failed")
            retry += 1
            if retry == 1 or retry % 6 == 0:
                _LOGGER.warning("AirTouch TCP reconnect attempt %d failed", retry)
            await asyncio.sleep(min(2 ** min(retry - 1, 4), RECONNECT_MAX_DELAY_SECONDS))

    async def _close_connection(
        self, expected_writer: asyncio.StreamWriter | None = None
    ) -> None:
        """Close the correct session; stale senders cannot close replacements."""
        if expected_writer is not None and self._writer is not expected_writer:
            return
        writer = self._writer
        self._writer = None
        self._reader = None
        if writer is None:
            return

        # Notify HA immediately instead of waiting for the socket to close.
        if self._on_disconnect is not None:
            try:
                self._on_disconnect()
            except Exception:
                _LOGGER.exception("AirTouch disconnect callback failed")

        try:
            writer.close()
            await asyncio.wait_for(
                writer.wait_closed(), timeout=CLOSE_TIMEOUT_SECONDS
            )
        except (OSError, asyncio.TimeoutError):
            _LOGGER.debug("Timed out or failed closing old AirTouch TCP socket")
