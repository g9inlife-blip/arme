# 2026-10-01-리나와협업전용문서-server_lina-56B-KCP-Handshake-검증정리

> **리나와협업전용문서**
>
> 목적: `server_lina` 최신 구현을 참고하여 `arme`의 기존 네트워크 분석과 대조하고, 로컬 서버의 56B KCP Handshake 문제를 별도 관리한다.
>
> 원칙: `server_lina`는 **참고/분석만** 한다. 이 문서는 `arme`의 기존 분석문서를 수정하지 않고 별도 문서로 관리한다.

## 1. 확인한 server_lina 최신 상태

최신 커밋 기준 주요 변경:

- `KCP: 전체 패킷 로깅`
- `작업정리: 핸드셰이크 문제 발견`
- `작업정리: 핸드셰이크 패킷 구조 분석`
- `작업정리: PCAP 핸드셰이크 분석`
- `KCP: Handshake1/2 구분 처리`
- `KCP: 토큰 추출 수정`

현재 `app/kcp/server.py`는 다음 흐름이다.

1. 373B 수신 → Handshake1
2. 37B 응답 전송
3. 다음 56B 수신 → Handshake2
4. `data[0x11:0x19]`을 little-endian UInt64로 읽어 Client public으로 사용
5. DH secret 계산
6. 56B 응답 생성
7. 응답은 기본적으로 입력 packet을 에코하고 `0x11~0x18`만 Server public으로 교체
8. 이후 패킷 대기

현재 56B 응답 핵심 구현:

```python
resp = bytearray(56)
resp[0:0x11] = data[0:0x11]
srv_pub1, _ = dh.get_public_pair()
struct.pack_into("<Q", resp, 0x11, srv_pub1)
resp[0x19:] = data[0x19:]
conn.send(bytes(resp))
```

즉 현재 구현은 **56B 전체를 동일하게 유지하면서 +0x11의 8바이트만 서버 public #1로 교체**한다.

## 2. arme 기존 분석과의 대조

`arme`의 Ghidra 분석에서는 `KCPTube$$Handshake2`가 다음 위치를 읽는 것으로 확인되어 있다.

- packet + `0x11` → Peer public #1
- packet + `0x19` → Peer public #2
- local private #1/#2를 각각 사용
- `DH64.Secret(private1, public1)`
- `DH64.Secret(private2, public2)`
- 두 secret을 연결하여 16바이트 session key 생성

따라서 현재 `server_lina` 구현의

```data[0x11:0x19]
```

만 사용하는 DH 계산은 **Ghidra에서 확인된 2중 DH 구조와 아직 일치하지 않는다.**

관련 기준 문서:
`research/reports/1001-2026-10-01-DH64-KCP2-56바이트-구조-가설-및-검증기록.md`

## 3. 현재 가장 중요한 충돌점

현재 관찰된 56B 입력에서:

- +0x11 값은 DH public #1 후보
- +0x19 값도 Ghidra상 DH public #2 후보
- 그런데 +0x19 영역에서 `0x61636f6c...` 형태가 반복 관찰됨

따라서 다음 세 가지를 아직 열어둔다.

### 가설 A
+0x11과 +0x19가 모두 실제 DH public 값이다.

### 가설 B
+0x19는 DH public #2가 아니라 token/다른 논리 필드이며, Ghidra의 read 위치와 실제 wire 구조를 추가 검증해야 한다.

### 가설 C
56B packet 자체가 여러 handshake 필드의 조합이며 현재 parser의 field boundary가 잘못 잡혀 있다.

**현재 단계에서는 A/B/C 중 하나를 확정하지 않는다.**

## 4. 왜 현재 56B 응답에서 클라이언트가 종료되는가

현재 서버 응답은:

- +0x11 → server public #1
- +0x19 이후 → client packet 그대로 복사

형태다.

그런데 Ghidra 분석이 맞다면 서버 응답도 client가 기대하는 DH pair/handshake 구조와 대응해야 한다.

따라서 현재 클라이언트 종료는 단순히 TCP 연결 문제가 아니라 다음 항목 중 하나일 가능성이 있다.

1. Server public #2가 필요한데 제공하지 않음
2. +0x19 영역이 token/다른 필드인데 잘못 에코함
3. response header/length/marker가 client 기대값과 다름
4. server public byte order가 잘못됨
5. DH secret/session key가 client와 일치하지 않음
6. Handshake2 이후 KCP state transition에 필요한 응답값이 없음

아직 종료 원인을 하나로 확정하지 않는다.

## 5. 다음 검증 순서

서버 코드를 바로 수정하기보다 다음 순서로 검증한다.

### 1단계 — 원본 56B 분해

실제 수신 packet을:

```
00~10
11~18
19~20
...
37
```

형태로 offset별 출력한다.

특히 +0x11과 +0x19를 raw byte와 UInt64 양쪽으로 기록한다.

### 2단계 — Ghidra와 1:1 대응

`KCPTube$$Handshake2`의:

- +0x11 read
- +0x19 read
- private #1
- private #2
- Secret #1
- Secret #2

를 각각 server 로그의 값과 대응시킨다.

### 3단계 — 56B 응답 원본 확보

현재 서버가 생성한 응답 전체 hex를 반드시 기록한다.

비교:

```
Client 56B request
Server 56B response
        ↓
offset별 차이
```

현재 예상되는 차이는 +0x11 하나뿐이다.

### 4단계 — client 종료 직전 확인

56B response 직후:

```
Handshake2
 → response parse
 → DH/key initialization
 → KCP state
 → GAME_CONN
```

중 어디에서 종료되는지 확인한다.

### 5단계 — 그 후 server response 수정

검증 결과에 따라:

- public #1
- public #2
- header
- token
- length/marker

중 필요한 부분만 단계적으로 변경한다.

## 6. 현재 결론

현재 `server_lina` 구현은 **56B를 받고 응답을 보내는 TCP 단계까지는 진행**하고 있다.

하지만 현재 응답은:

> 입력 56B를 거의 그대로 에코 + +0x11의 Server public #1 교체

이므로, `arme`에서 확인된 **DH64 2중 public/session-key 구조를 완전히 반영한 서버 응답이라고 볼 수 없다.**

따라서 다음 핵심 작업은 **56B response format 자체를 추측해서 수정하는 것이 아니라, client가 response를 읽는 위치와 server가 보내야 할 두 public/필드를 1:1로 확정하는 것**이다.

## 7. 작업 경계

- `server_lina`: 실제 서버 구현 및 테스트 대상
- `arme`: Ghidra/PCAP/기존 연구 결과 참고 대상
- 본 문서: 두 저장소의 분석 결과를 연결하는 **리나와협업전용문서**
- `arme`의 기존 분석문서는 변경하지 않는다.
