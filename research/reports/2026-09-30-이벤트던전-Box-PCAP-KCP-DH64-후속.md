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



## 9. 신규 통합 PCAP — 실제 0x14 확보

신규 통합 PCAP에서 KCP key를 복구한 뒤 전체 UDP application request를 복호화했다.

### 0x14 request

**frame 428 / client → server**

복호화 plaintext:

```
08 e2 de df c0 09
10 14
22 0b
  08 cc a2 c2 e9 e4 be cf 3f
  10 05
30 e4 da c4 09
```

protobuf 기준:
- field #2 = `0x14`
- field #4 nested의 field #2 = `5`
- field #6 = `0x01312D64` = `20,000,100`

따라서 정적 분석에서 확인했던:

```
GetChapterBoxReward
→ opcode 0x14
→ chapterId + boxIndex
```

와 실제 PCAP request가 일치한다.

특히 `0x01312D64`는 이번 이벤트 Chapter 식별값으로 볼 수 있는 강한 후보이며, boxIndex는 `5`로 직접 확인된다.

### 0x14 response

**frame 430 / server → client**

- flag = `0x84`
- application length = 353
- Rijndael/AES-128-CBC/PKCS7 복호화 성공
- plaintext length = 329 bytes
- field #2 = `0x14`

응답 시작:

```
08 e2 de df c0 09
10 14
22 0b
  08 c0 ca ab a6 eb bc cf 3f
  10 05
30 e4 da c4 09
...
```

즉:

```
frame 428 : request opcode 0x14
frame 430 : response opcode 0x14
```

가 **실제 데이터로 확정**되었다.

## 10. BoxStatus 현재 확인 수준

0x14 response 내부에는 다음과 같은 repeated nested data가 존재한다.

- field #21 repeated entries 다수
- field #38 repeated entries
- field #43 entry
- field #46 repeated entries
- field #49 entry

현재 response에서 Chapter 관련 후보 데이터가 존재하는 것은 확인되지만, 특정 nested entry를 `ProtoChapter`라고 단정할 단계는 아니다.

정적 구조는 여전히:

```
ProtoChapter
+0x10 Id
+0x14 Status
+0x18 Progress
+0x1C BoxStatus
```

이고:

```
IsBoxReceived(mask)
= (BoxStatus & mask) != 0
```

가 확정되어 있다.

따라서 현재 가장 중요한 미확정은:

```
0x14 response
 ↓
어느 nested message가 ProtoChapter인가?
 ↓
그 message의 BoxStatus field는 무엇인가?
```

이다.

## 11. 통합 PCAP request opcode 흐름 1차 결과

client request를 시간순으로 복호화한 결과:

| Frame | Opcode |
|---:|---:|
| 189 | 0x02 |
| 207 | 0x39 |
| 211 | 0x06 |
| 233 | 0x5D |
| 238 | 0x30 |
| 251 | 0x2D |
| 289 | 0x2E |
| 295 | 0x2E |
| 307 | 0x7C |
| 316 | 0x30 |
| 336 | 0x13 |
| 340 | 0x13 |
| 368 | 0x16 |
| 390 | 0x17 |
| 413 | 0x4E |
| **428** | **0x14** |
| 432 | 0x4E |
| 436 | 0x30 |
| 442 | 0x28 |
| 448 | 0x15 |
| 460 | 0x4E |
| 464 | 0x0A |
| 468 | 0x0A |
| 472 | 0x4E |
| 476 | 0x13 |

이 흐름으로 인해 기존의 별도 Box PCAP에서 추측했던 0x14 후보가 아니라, **이번 통합 PCAP에서는 0x14가 실제 Box 보상 요청임을 직접 확정**할 수 있다.

## 12. 다음 작업

다음은 DH/hook이 아니다.

1. frame 430의 329-byte plaintext를 protobuf tree로 정확히 분해
2. `ProtoChapter`의 Id/Status/Progress/BoxStatus와 대응되는 nested field 탐색
3. 동일 PCAP에서 **0x14 이전/이후 상태 snapshot** 비교
4. BoxStatus bit 변화가 실제로 존재하는지 확인
5. 이후 opcode 0x15/0x4E/0x30 등을 사용자 행동과 매핑

현재 핵심 성과:

```
PCAP
→ KCP DH
→ session key
→ decrypt
→ 0x14 request
→ 0x14 response
→ chapterId = 20,000,100
→ boxIndex = 5
```

까지 연결되었다.


## 9. 통합 PCAP 후속 분석기 추가

대용량 Git JSON은 GitHub API가 본문 반환을 제한하여 서버 측에서 전체 packet bytes를 재추출할 수 없는 상태다. 이를 우회하기 위해 `research/PCAP/analyze_kcp_json.py`를 추가했다.

분석기는 이번 게임의 **64-bit KCP 28-byte header**를 사용하고, 확보된 KCP session key `44f5f445808615fe1b2e224c5e05e718`로 다음을 자동 처리한다.

```text
Wireshark JSON
 → KCP 28-byte parse
 → frg/sn 재조립
 → flag + IV16 + AES-128-CBC
 → PKCS7 제거
 → gzip 해제
 → protobuf top-level field 출력
```

따라서 통합 PCAP을 로컬에서 한 번 실행하면 로그인부터 강화까지 모든 KCP application message의 packet 번호/방향/복호화 결과를 한 번에 얻을 수 있다.

다음 분석에서는 결과의 `field=2` opcode를 기준으로:

```text
출석 / 퀘스트 / 우편 / 토벌 / 던전 / Box / 제작 / 강화
```

구간을 분리하고, **0x14 request/response가 실제 존재하는지**부터 확정한다.

현재는 hook을 추가하지 않는다. PCAP에서 KCP key와 복호화 경로가 이미 확보됐기 때문이다.


## 13. 후속 분석기 보강 — 2026-09-30

현재 GitHub 환경에서는 통합 PCAP JSON의 전체 packet bytes가 대용량 제한으로 직접 반환되지 않아, 복호화 결과를 서버에서 재계산하는 단계는 아직 수행할 수 없다.

대신 `research/PCAP/analyze_kcp_json.py`를 보강했다.

변경점:
- 64-bit KCP 28-byte header 유지
- `sn` 연속성 검사 추가
- `frg=0` 기준 message 경계 처리 개선
- AES-128-CBC/PKCS7 복호화 유지
- 복호화 plaintext를 message별 `.bin`으로 저장
- protobuf length-delimited field를 중첩 구조까지 재귀 분석
- gzip 내부 protobuf도 재귀 분석
- `messages.json`에 전체 구조 저장

따라서 로컬에서 동일 JSON을 실행하면 다음 단계인 **frame 430 response의 nested field → ProtoChapter 후보 → BoxStatus field**를 직접 추적할 수 있다.

현재 확정값은 그대로 유지한다:

``
frame 428  C→S  opcode 0x14  chapterId=20,000,100  boxIndex=5
frame 430  S→C  opcode 0x14  plaintext=329 bytes
ProtoChapter +0x1C = BoxStatus
IsBoxReceived(mask) = (BoxStatus & mask) != 0
```

frame 430의 특정 nested message를 ProtoChapter라고 확정하거나, 0x14 response가 BoxStatus를 갱신한다고 확정하는 것은 아직 보류한다.

다음 실제 분석 입력은 생성되는 `messages.json` 또는 message별 plaintext이며, 이 자료가 확보되면 0x14 response의 Chapter/BoxStatus 대응을 바로 대조한다.
