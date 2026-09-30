# 2026-09-30 이벤트던전 Box PCAP / KCP DH64 후속 분석

## 기준
- Git 기준 `research/*.md`, `research/reports/*.md`
- `Ghidra_Listing_txt` 함수명은 앞 2글자 기준이며 `< > $` 등은 `_` 치환
- 대상 신규 PCAP JSON: `research/PCAP/로그인_출석_퀘스트_우편_토벌_던전_상자_무기제작_강화.json`
- 확인되지 않은 opcode/상태는 추측으로 확정하지 않음

## 1. 신규 통합 PCAP 확인

신규 JSON은 총 **479 packet**이며, 기존 Box 전용 103 packet PCAP과 달리 로그인부터 여러 게임 행동을 하나의 세션 흐름으로 포함한다.

사용자 행동 순서:
```
로그인
→ 이벤트 메뉴/출석
→ 출석
→ 퀘스트/업적 수령
→ 우편 2개 수령
→ 토벌 일괄수령/퀘스트 수령
→ 던전 진입/시작/승리/보상
→ 무기 경험치 증가/레벨업
→ 던전 업적 3개
→ Box 보상 수령
→ 무기 제작
→ 영웅 경험치 강화/레벨업
```

따라서 행동별 PCAP을 별도로 나누지 않아도 시간순서 + KCP Conv/session으로 구간 분리가 가능하다.

## 2. 이번에는 KCP DH handshake가 실제로 포함됨

Game Server UDP:
```
10.215.173.1:40193 ↔ 182.92.62.79:8000
```

KCP 시작 구간:

### frame 180 — client → server

UDP payload 길이 368 bytes.

구조:
```
00 00 00 00 00 00 00 00
53 54 0f b7 35 9e a7 25
8e b3 94 2e 8f fc e5 35
[344-byte Base64 parameter]
```

LE UInt64:
```
client public #1 = 0x25A79E35B70F5453
client public #2 = 0x35E5FC8F2E94B38E
```

### frame 182 — server → client

UDP payload 길이 33 bytes.

```
00 00 00 00 00 00 00 00
01
7d 94 40 73 46 8e b4 14
f3 ea d6 b7 90 6a 4b 56
14 48 ea 88 2a fc 02 18
```

기존 `KCPTube.Handshake2`의 public offset 기준:
- peer public #1 = packet + 0x11
- peer public #2 = packet + 0x19

따라서:
```
server public #1 = 0x564B6A90B7D6EAF3
server public #2 = 0x1802FC2A88EA4814
```

**결론: 신규 PCAP에는 KCP DH public pair가 실제로 존재한다.**

## 3. 이번 세션 private 복구

기존 정적 분석 확정:
```
p = 2^64 - 59
g = 5
public = 5^private mod p
```

이번 client public에 discrete-log을 적용:

```
client private #1 = 0x20A728990271B002
client private #2 = 0x237FCE167BB3CC9F
```

검증:
```
5^private1 mod p = 0x25A79E35B70F5453
5^private2 mod p = 0x35E5FC8F2E94B38E
```

둘 다 PCAP public과 정확히 일치한다.

## 4. KCP session key 복구

server public으로 DH Secret 계산:

```
secret1 = 0xFE15868045F4F544
secret2 = 0x3F3287258010223F
```

기존 Ghidra 확정 조합:
```
Key[0:8]  = LE64(secret1)
Key[8:16] = LE64(secret2)
```

이번 KCP session key:

```
44f5f445808615fe1b2e224c5e05e718
```

## 5. 실제 KCP application 복호화 검증

frame 189:
```
client → server
KCP data
flag = 0x80
```

위 key + packet IV + AES-128-CBC/PKCS7로 복호화했으며 **padding 검증 성공**.

plaintext 시작:
```
08 d2 de df c0 09
10 02
...
```

즉 protobuf field #2의 값이 `0x02`로 확인된다.

따라서 이번 단계에서 단순히 public/key 계산만 성공한 것이 아니라:

```
KCP handshake
→ public 추출
→ discrete log private 복구
→ DH Secret
→ KCP session key
→ 실제 application decrypt
```

전체 경로가 실제 PCAP으로 검증되었다.

## 6. Hook 필요 여부 변경

기존 이벤트 Box 전용 PCAP에서는 KCP handshake가 없어 hook을 고려했었다.

신규 통합 PCAP에서는 상황이 변경되었다.

### 현재
```
PCAP만으로
KCP public 확보
→ private 복구
→ session key 복구
→ application 복호화 가능
```

따라서 **KCP DH key 확인을 위해 hook을 사용할 필요가 없다.**

hook은 다음 경우에만 보조 수단으로 남긴다.

- 특정 세션에서 KCP handshake packet이 누락된 경우
- private 생성 과정 자체를 runtime에서 검증할 필요가 있는 경우
- PCAP key 계산 결과와 runtime 값을 교차검증할 경우

## 7. 다음 분석 대상

이제 핵심 병목은 DH가 아니다.

신규 통합 PCAP에서 시간순으로:

```
로그인
출석
퀘스트
우편
토벌
던전
Box
무기제작
강화
```

각 KCP application request/response를 복호화하여 opcode와 protobuf 구조를 매핑한다.

특히 Box 구간은:

```
GetChapterBoxReward
→ opcode 0x14
→ response
→ OpInfo.Chapters
→ ProtoChapter
→ BoxStatus +0x1C
```

를 직접 확인한다.

또한 던전 승리/보상 구간에서:
- 골드
- 최하급 경험치 물약
- 무기 경험치
- 업적 3개
- Box 조건/진행도

가 어느 opcode에서 갱신되는지 함께 비교한다.

## 8. 현재 결론

- 신규 통합 PCAP: **479 packets**
- KCP handshake: **실제 포함**
- client public #1/#2: 확보
- server public #1/#2: 확보
- client private #1/#2: **discrete-log으로 복구**
- KCP session key: `44f5f445808615fe3f2210802587323f`가 아니라 정확히 **`44f5f445808615fe1b2e224c5e05e718`**
- frame 189 실제 복호화: **성공**
- 따라서 **hook 없이 PCAP 분석 계속 가능**
- 다음 핵심: **전체 행동구간 opcode/protobuf 매핑 및 Box의 0x14/BoxStatus 확인**

