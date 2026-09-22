#!/usr/bin/env python3
"""
pcap_dh_validator.py

TCP DH64 handshake 구조를 PCAP에서 1차 검증한다.

현재 버전:
- 표준 라이브러리만 사용
- classic PCAP(libpcap) 파일 직접 읽기
- Ethernet + IPv4 + TCP payload 추출
- 기존에 확인된 server handshake 값 검색
- client handshake 후보 검색
- private key가 제공되면 public/secret/session key 계산

사용 예:
  python pcap_dh_validator.py capture.pcap
  python pcap_dh_validator.py capture.pcap --server-public1 ca4d30dba4429f27 --server-public2 7164b27b3d91d781
  python pcap_dh_validator.py capture.pcap --private1 0x... --private2 0x...

주의:
- 첫 버전은 TCP stream reassembly를 하지 않는다.
- 따라서 handshake가 여러 TCP segment로 분할된 경우 후보를 놓칠 수 있다.
- 실제 PCAP 구조 확인 후 reassembly를 추가한다.
"""

from __future__ import annotations

import argparse
import struct
from dataclasses import dataclass
from pathlib import Path


P = 0xFFFFFFFFFFFFFFC5
G = 5

DEFAULT_SERVER_PUBLIC1 = 0xCA4D30DBA4429F27
DEFAULT_SERVER_PUBLIC2 = 0x7164B27B3D91D781
DEFAULT_CONV_ID = 0x632


@dataclass
class Packet:
    index: int
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    payload: bytes


def u16be(b: bytes) -> int:
    return struct.unpack(">H", b)[0]


def u32be(b: bytes) -> int:
    return struct.unpack(">I", b)[0]


def u64le(b: bytes) -> int:
    return int.from_bytes(b, "little")


def ip_text(b: bytes) -> str:
    return ".".join(str(x) for x in b)


def read_pcap(path: Path):
    data = path.read_bytes()
    if len(data) < 24:
        raise ValueError("파일이 classic PCAP 헤더보다 짧습니다.")

    magic = data[:4]
    if magic == b"\xd4\xc3\xb2\xa1":
        endian = "<"
    elif magic == b"\xa1\xb2\xc3\xd4":
        endian = ">"
    elif magic == b"\x4d\x3c\xb2\xa1":
        endian = "<"
    elif magic == b"\xa1\xb2\x3c\x4d":
        endian = ">"
    else:
        raise ValueError(
            "classic PCAP이 아닙니다. pcapng이면 tshark/pyshark 또는 "
            "pcapng parser를 별도로 사용해야 합니다."
        )

    _, _, _, _, _, network = struct.unpack(endian + "IHHIIII", data[:24])
    if network != 1:
        raise ValueError(
            f"현재 버전은 Ethernet linktype만 지원합니다. linktype={network}"
        )

    offset = 24
    index = 0

    while offset + 16 <= len(data):
        ts_sec, ts_usec, incl_len, orig_len = struct.unpack(
            endian + "IIII", data[offset:offset + 16]
        )
        offset += 16

        if offset + incl_len > len(data):
            break

        frame = data[offset:offset + incl_len]
        offset += incl_len
        index += 1

        pkt = parse_ethernet_ipv4_tcp(index, frame)
        if pkt:
            yield pkt


def parse_ethernet_ipv4_tcp(index: int, frame: bytes):
    if len(frame) < 14:
        return None

    eth_type = u16be(frame[12:14])
    if eth_type != 0x0800:
        return None

    ip = frame[14:]
    if len(ip) < 20:
        return None

    version = ip[0] >> 4
    ihl = (ip[0] & 0x0F) * 4
    if version != 4 or ihl < 20 or len(ip) < ihl:
        return None

    protocol = ip[9]
    if protocol != 6:
        return None

    src_ip = ip_text(ip[12:16])
    dst_ip = ip_text(ip[16:20])

    tcp = ip[ihl:]
    if len(tcp) < 20:
        return None

    src_port = u16be(tcp[0:2])
    dst_port = u16be(tcp[2:4])
    tcp_hlen = ((tcp[12] >> 4) & 0x0F) * 4
    if tcp_hlen < 20 or len(tcp) < tcp_hlen:
        return None

    return Packet(
        index=index,
        src_ip=src_ip,
        dst_ip=dst_ip,
        src_port=src_port,
        dst_port=dst_port,
        payload=tcp[tcp_hlen:],
    )


def find_server_candidates(pkt: Packet, pub1: int, pub2: int, conv_id: int):
    payload = pkt.payload
    p1 = pub1.to_bytes(8, "little")
    p2 = pub2.to_bytes(8, "little")
    cid = conv_id.to_bytes(8, "little")

    hits = []
    start = 0
    while True:
        pos = payload.find(p1, start)
        if pos < 0:
            break

        # 구조상 pos는 +0x15일 가능성이 가장 높다.
        base = pos - 0x15
        if base >= 0 and base + 0x25 <= len(payload):
            candidate = payload[base:base + 0x25]
            length = int.from_bytes(candidate[8:12], "little")
            marker = candidate[12]
            got_cid = u64le(candidate[13:21])
            got_p2 = u64le(candidate[0x1D:0x25])

            if length == 0x19 and marker == 1 and got_p2 == pub2:
                hits.append((base, length, marker, got_cid, got_p2))
        start = pos + 1

    return hits


def find_client_candidates(pkt: Packet):
    payload = pkt.payload
    hits = []

    # 첫 8바이트 zero + public1/public2라는 알려진 형태를
    # 너무 공격적으로 가정하지 않고 zero prefix만 후보로 사용한다.
    for base in range(max(0, len(payload) - 0x18 + 1)):
        if base + 0x18 > len(payload):
            break
        if payload[base:base + 8] != b"\x00" * 8:
            continue

        pub1 = u64le(payload[base + 8:base + 16])
        pub2 = u64le(payload[base + 16:base + 24])

        # 0/1/작은 값은 handshake public 후보에서 제외한다.
        if pub1 <= 1 or pub2 <= 1:
            continue

        hits.append((base, pub1, pub2, len(payload) - base))

    return hits


def parse_int(s: str) -> int:
    return int(s, 0)


def print_packet(pkt: Packet):
    print(
        f"packet={pkt.index} "
        f"{pkt.src_ip}:{pkt.src_port} -> {pkt.dst_ip}:{pkt.dst_port} "
        f"payload={len(pkt.payload)}"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pcap", type=Path)
    ap.add_argument("--server-public1", type=parse_int, default=DEFAULT_SERVER_PUBLIC1)
    ap.add_argument("--server-public2", type=parse_int, default=DEFAULT_SERVER_PUBLIC2)
    ap.add_argument("--conv-id", type=parse_int, default=DEFAULT_CONV_ID)
    ap.add_argument("--private1", type=parse_int)
    ap.add_argument("--private2", type=parse_int)
    args = ap.parse_args()

    packets = list(read_pcap(args.pcap))

    print(f"[+] TCP packets with payload: {len([p for p in packets if p.payload])}")

    server_hits = []
    client_candidates = []

    for pkt in packets:
        if not pkt.payload:
            continue

        hits = find_server_candidates(
            pkt,
            args.server_public1,
            args.server_public2,
            args.conv_id,
        )
        for hit in hits:
            server_hits.append((pkt, hit))

        for hit in find_client_candidates(pkt):
            client_candidates.append((pkt, hit))

    print()
    print("[SERVER HANDSHAKE]")
    if not server_hits:
        print("  후보를 찾지 못했습니다.")
    else:
        for pkt, (base, length, marker, cid, p2) in server_hits:
            print_packet(pkt)
            print(f"  offset      = 0x{base:x}")
            print(f"  length      = 0x{length:x}")
            print(f"  marker      = {marker}")
            print(f"  TCPConvID   = 0x{cid:x}")
            print(f"  serverPub1  = 0x{args.server_public1:016x}")
            print(f"  serverPub2  = 0x{p2:016x}")

    print()
    print("[CLIENT HANDSHAKE CANDIDATES]")
    if not client_candidates:
        print("  후보를 찾지 못했습니다.")
    else:
        # 동일 payload 안의 너무 많은 후보를 줄이기 위해 앞쪽 후보부터 출력
        for pkt, (base, pub1, pub2, remaining) in client_candidates[:50]:
            print_packet(pkt)
            print(f"  offset      = 0x{base:x}")
            print(f"  clientPub1  = 0x{pub1:016x}")
            print(f"  clientPub2  = 0x{pub2:016x}")
            print(f"  remaining   = {remaining}")

    if args.private1 is not None or args.private2 is not None:
        if args.private1 is None or args.private2 is None:
            raise SystemExit("--private1과 --private2를 함께 지정해야 합니다.")

        pub1 = pow(G, args.private1, P)
        pub2 = pow(G, args.private2, P)

        print()
        print("[DH PRIVATE/PUBLIC VALIDATION]")
        print(f"  private1 = 0x{args.private1:016x}")
        print(f"  public1  = 0x{pub1:016x}")
        print(f"  private2 = 0x{args.private2:016x}")
        print(f"  public2  = 0x{pub2:016x}")

        secret1 = pow(args.server_public1, args.private1, P)
        secret2 = pow(args.server_public2, args.private2, P)
        key = secret1.to_bytes(8, "little") + secret2.to_bytes(8, "little")

        print()
        print("[SESSION KEY]")
        print(f"  secret1 = 0x{secret1:016x}")
        print(f"  secret2 = 0x{secret2:016x}")
        print(f"  key     = {key.hex()}")

    print()
    print("[NOTE]")
    print("  현재 버전은 TCP stream reassembly를 하지 않습니다.")
    print("  handshake가 여러 TCP segment로 분할된 경우 다음 버전에서 재조립을 추가합니다.")


if __name__ == "__main__":
    main()
