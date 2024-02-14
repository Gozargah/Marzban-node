from dataclasses import dataclass
from pydantic import BaseModel
import psutil
from rest_service import scheduler


class NodeStats(BaseModel):
    mem_total: int
    mem_used: int
    cpu_cores: int
    cpu_usage: float
    incoming_bandwidth_speed: int
    outgoing_bandwidth_speed: int


@dataclass
class MemoryStat():
    total: int
    used: int
    free: int


@dataclass
class CPUStat():
    cores: int
    percent: float


def cpu_usage() -> CPUStat:
    return CPUStat(cores=psutil.cpu_count(), percent=psutil.cpu_percent())


def memory_usage() -> MemoryStat:
    mem = psutil.virtual_memory()
    return MemoryStat(total=mem.total, used=mem.used, free=mem.available)


@dataclass
class RealtimeBandwidth:
    def __post_init__(self):
        io = psutil.net_io_counters()
        self.bytes_recv = io.bytes_recv
        self.bytes_sent = io.bytes_sent
        self.packets_recv = io.packets_recv
        self.packet_sent = io.packets_sent

    incoming_bytes: int
    outgoing_bytes: int
    incoming_packets: int
    outgoing_packets: int

    bytes_recv: int = None
    bytes_sent: int = None
    packets_recv: int = None
    packet_sent: int = None


@dataclass
class RealtimeBandwidthStat:
    incoming_bytes: int
    outgoing_bytes: int
    incoming_packets: int
    outgoing_packets: int


rt_bw = RealtimeBandwidth(
    incoming_bytes=0, outgoing_bytes=0, incoming_packets=0, outgoing_packets=0)

@scheduler.scheduled_job('interval', seconds=1, coalesce=True, max_instances=1)
def record_realtime_bandwidth() -> None:
    io = psutil.net_io_counters()
    rt_bw.incoming_bytes, rt_bw.bytes_recv = io.bytes_recv - rt_bw.bytes_recv, io.bytes_recv
    rt_bw.outgoing_bytes, rt_bw.bytes_sent = io.bytes_sent - rt_bw.bytes_sent, io.bytes_sent
    rt_bw.incoming_packets, rt_bw.packets_recv = io.packets_recv - rt_bw.packets_recv, io.packets_recv
    rt_bw.outgoing_packets, rt_bw.packet_sent = io.packets_sent - rt_bw.packet_sent, io.packets_sent


def realtime_bandwidth() -> RealtimeBandwidthStat:
    return RealtimeBandwidthStat(
        incoming_bytes=rt_bw.incoming_bytes, outgoing_bytes=rt_bw.outgoing_bytes,
        incoming_packets=rt_bw.incoming_packets, outgoing_packets=rt_bw.outgoing_packets)
