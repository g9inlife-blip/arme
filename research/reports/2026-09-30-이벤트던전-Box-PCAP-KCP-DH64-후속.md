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

## 2. KCP DH64 / session key 확정

Game Server UDP:
```
10.215.173.1:40193 ↔ 182.92.62.79:8000
```

KCP handshake:
- frame 180 C→S: client public #1/#2
- frame 182 S→C: server public #1/#2

정적 분석 및 PCAP 검증:
```
p = 2^64 - 59
g = 5
private = ((uint64)R1 << 32) | ((uint32)R2 + 1)
public = 5^private mod p
```

이번 세션:
```
client private #1 = 0x20A728990271B002
client private #2 = 0x237FCE167BB3CC9F

secret1 = 0xFE15868045F4F544
secret2 = 0x3F3287258010223F

KCP key = 44f5f445808615fe1b2e224c5e05e718
```

frame 189 실제 application 복호화 성공으로 전체 경로가 검증되었다.

## 3. 0x14 Box request/response 확정

### frame 428 — C→S

```
opcode = 0x14
chapterId = 20,000,100
boxIndex = 5
```

복호화 protobuf:
```
08 e2 de df c0 09
10 14
22 0b
  08 cc a2 c2 e9 e4 be cf 3f
  10 05
30 e4 da c4 09
```

정적 분석의:
```
GetChapterBoxReward
→ opcode 0x14
→ chapterId + boxIndex
```
와 실제 PCAP이 일치한다.

### frame 430 — S→C

기존 분석에서 이미:
```
flag = 0x84
application length = 353
plaintext = 329 bytes
field #2 = 0x14
```
가 확인되었다.

## 4. frame 430이 analyzer에서 빠진 원인 확인

Git의 생성 결과 `messages.txt`를 다시 확인한 결과:

```
packets=[430] ... bytes=353 flags=None decrypt=None
```

원인은 KCP 재조립 문제가 아니라 **암호화 flag 목록 누락**이었다.

기존:
```
ENC_FLAGS = {0x80, 0xC0, 0xC4}
```

frame 430은:
```
flag = 0x84
```

따라서 analyzer가 `decrypt_app()` 단계에서 0x84를 암호화 메시지로 인정하지 않고 그대로 반환했다.

### 수정

```
ENC_FLAGS = {0x80, 0x84, 0xC0, 0xC4}
```

수정 commit:
```
076e991f0513b9ace469553a1c87f13b3b6a688d
```

이제 동일 PCAP을 다시 실행하면 frame 430도:
```
0x84
→ IV16
→ AES-128-CBC
→ PKCS7
→ 329-byte plaintext
→ protobuf tree
```
경로로 분석된다.

## 5. ProtoChapter / BoxStatus 현재 상태

Ghidra에서 확정:
```
ProtoChapter +0x10 = Id
ProtoChapter +0x14 = Status
ProtoChapter +0x18 = Progress
ProtoChapter +0x1C = BoxStatus
```

```
IsBoxReceived(mask)
= (BoxStatus & mask) != 0
```

또한:
```
OpInfo +0xC0 = Chapters
DataCenter.ProccessRequestRes
→ OpInfo.Chapters
→ MergeSectionSnapShot / MergeSections
```

그러나 **frame 430의 특정 nested protobuf를 ProtoChapter라고 확정하거나, 그 field가 BoxStatus라고 확정한 것은 아직 아니다.**

## 6. 다음 분석

수정된 analyzer로 통합 PCAP을 재실행한다.

```
python research\\PCAP\\analyze_kcp_json.py "research\\PCAP\\로그인_출석_퀘스트_우편_토벌_던전_상자_무기제작_강화.json"
```

우선 확인 대상:
```
frame 430
→ plaintext 329 bytes
→ protobuf nested tree
→ Id / Status / Progress / BoxStatus 후보
```

그 다음 frame 430 전후 snapshot과 비교하여 BoxStatus bit 변화 여부를 확인한다.

현재 확정:
```
PCAP
→ KCP DH64
→ session key
→ AES decrypt
→ opcode 0x14
→ chapterId 20,000,100
→ boxIndex 5
→ response plaintext 329 bytes
```

**BoxStatus의 실제 protobuf field 번호는 재실행 결과 확인 전까지 확정하지 않는다.**
