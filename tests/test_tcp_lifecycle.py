"""Regression tests for TCP session cleanup and supervised recovery."""
import asyncio
import pytest

from airtouch2.common.NetClient import NetClient


async def wait_until(predicate, timeout=4):
    end = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() >= end:
            raise AssertionError("Expected TCP state change never happened")
        await asyncio.sleep(0.02)


class Payload:
    def to_bytes(self):
        return b"h"


@pytest.mark.asyncio
async def test_tcp_disconnect_recovers_without_second_supervisor():
    accepts = 0
    changes = []
    async def server_session(reader, writer):
        nonlocal accepts
        accepts += 1
        try:
            await reader.readexactly(1)
            if accepts == 1:
                writer.close()
                await writer.wait_closed()
            else:
                await reader.read()
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(server_session, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    client = None

    async def on_connect():
        changes.append("connected")
        await client.send(Payload())

    async def receive():
        await client.read_bytes(1)

    client = NetClient("127.0.0.1", port, on_connect, receive,
                       on_disconnect=lambda: changes.append("disconnected"))
    try:
        assert await client.connect()
        client.run()
        await wait_until(lambda: accepts >= 2)
        await wait_until(lambda: changes.count("connected") == 2)
        assert changes[:3] == ["connected", "disconnected", "connected"]
        assert not client._main_loop_task.done()
    finally:
        await client.stop()
        server.close()
        await server.wait_closed()
    assert client._writer is None and client._reader is None


@pytest.mark.asyncio
async def test_parser_failure_reopens_session():
    accepts = 0
    async def server_session(reader, writer):
        nonlocal accepts
        accepts += 1
        try:
            await reader.readexactly(1)
            if accepts == 1:
                writer.write(b"!")
                await writer.drain()
            await reader.read()
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(server_session, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    client = None
    async def on_connect():
        await client.send(Payload())
    async def receive():
        if await client.read_bytes(1) == b"!":
            raise ValueError("Malformed controller status")

    client = NetClient("127.0.0.1", port, on_connect, receive)
    try:
        assert await client.connect()
        client.run()
        await wait_until(lambda: accepts >= 2)
        assert not client._main_loop_task.done()
    finally:
        await client.stop()
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_failed_command_is_not_silently_retried():
    class BrokenWriter:
        def __init__(self):
            self.closed = False
        def is_closing(self):
            return False
        def write(self, value):
            raise OSError("Connection reset")
        def close(self):
            self.closed = True
        async def wait_closed(self):
            pass

    async def noop():
        pass
    client = NetClient("127.0.0.1", 9200, noop, noop)
    writer = BrokenWriter()
    client._writer = writer
    client._reader = object()
    with pytest.raises(ConnectionError, match="not retried"):
        await client.send(Payload())
    assert writer.closed
    assert client._writer is None


@pytest.mark.asyncio
async def test_stale_session_cannot_be_closed_by_old_sender():
    async def noop():
        pass
    client = NetClient("127.0.0.1", 9200, noop, noop)
    active_writer = object()
    client._writer = active_writer
    await client._close_connection(expected_writer=object())
    assert client._writer is active_writer


@pytest.mark.asyncio
async def test_connect_callback_failure_cleans_socket():
    connection_closed = asyncio.Event()
    async def server_session(reader, writer):
        try:
            await reader.read()
        finally:
            connection_closed.set()
            writer.close()
            await writer.wait_closed()
    server = await asyncio.start_server(server_session, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]

    async def broken_setup():
        raise OSError("Failed initial status request")
    async def receive():
        pass

    client = NetClient("127.0.0.1", port, broken_setup, receive)
    try:
        assert not await client.connect()
        assert client._writer is None
        await asyncio.wait_for(connection_closed.wait(), timeout=2)
    finally:
        await client.stop()
        server.close()
        await server.wait_closed()
