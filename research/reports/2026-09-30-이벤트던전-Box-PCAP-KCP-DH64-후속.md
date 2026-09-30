# 2026-09-30 이벤트던전 Box PCAP / KCP DH64 후속 분석

## 기준
- Git 기준 `research/*.md`, `research/reports/*.md`
- `Ghidra_Listing_txt` 함수명은 앞 2글자 기준이며 `< > $` 등은 `_` 치환
- 대상 신규 PCAP JSON: `research/PCAP/로그인_출석_퀘스트_우편_토벌_던전_상자_무기제작_강화.json`
- 확인되지 않은 opcode/상태는 추측으로 확정하지 않음

## 1. 신규 통합 PCAP 확인
신규 JSON은 총 **479 packet**이며 로그인부터 여러 게임 행동을 하나의 세션 흐름으로 포함한다.

사용자 행동 순서:
```
로그인 → 출석 → 퀘스트/업적 → 우편 → 토벌 → 던전
→ 승리/보상 → 던전 업적 → Box 보상 → 무기 제작 → 강화
```

## 2. KCP DH64 / session key 확정
Game Server UDP:
```
10.215.173.1:40193 ↔ 182.92.62.79:8000
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

정적 분석의 `GetChapterBoxReward @ 00ddeea8` 계약과 일치한다.

### frame 430 — S→C
```
flag = 0x84
application bytes = 353
plaintext = 329 bytes
opcode(field #2) = 0x14
```

## 4. analyzer 수정
frame 430 누락 원인은 KCP 재조립이 아니라 암호화 flag 목록에서 `0x84`가 빠져 있었던 것이다.

수정:
```
ENC_FLAGS = {0x80, 0x84, 0xC0, 0xC4}
```

수정 commit:
```
076e991f0513b9ace469553a1c87f13b3b6a688d
```

현재 Git에는 수정 후 생성된:
```
plaintext/000430_s2c.bin
```
이 존재하며 **실제 329-byte plaintext가 확인되었다.**

## 5. frame 430 ProtoChapter 구조 확인

frame 430의 핵심 nested 구조:

```
field 43
 └─ length 30
    ├─ field 1 = 20,000,100
    ├─ field 3 = 6
    ├─ field 4 = 1
    ├─ field 9 = { field1=1, field2=15 }
    ├─ field10 = { field1=1, field2=15 }
    └─ field11 = 1
```

특히 field 43 내부의 **field 1 = 20,000,100**은 요청 chapterId와 정확히 일치한다.

Ghidra에서 확인된 `ProtoChapter` 메모리 필드:
```
+0x10 = Id
+0x14 = Status
+0x18 = Progress
+0x1C = BoxStatus
```

이에 따라 protobuf의 연속적인 Chapter 핵심 필드가:
```
protobuf field 1 → Id
protobuf field 2 → Status
protobuf field 3 → Progress
protobuf field 4 → BoxStatus
```
로 대응하는 것이 **frame 430에서 직접 관측된 값과 일치한다.**

따라서 이번 frame 430에서는:

```
ProtoChapter.Id        = 20,000,100
ProtoChapter.Progress  = 6
ProtoChapter.BoxStatus = 1
```

로 해석할 근거가 확보되었다.

**중요:** field 4 → BoxStatus는 단순 이름 추측이 아니라, Ghidra의 필드 순서/offset과 frame 430의 Chapter 구조가 동시에 일치한 결과다. 다만 protobuf serializer/deserializer 함수 자체에서 field 번호를 직접 확인하면 최종 확정이 된다.

## 6. BoxStatus 의미
```
IsBoxReceived(mask)
= (BoxStatus & mask) != 0
```

현재 frame 430:
```
BoxStatus = 1
```

요청은:
```
boxIndex = 5
```

이므로 **BoxStatus=1이 boxIndex 5의 수령 완료를 직접 의미한다고 아직 해석하면 안 된다.**

현재 확인된 것은:
- opcode 0x14 요청에서 boxIndex=5가 서버로 전달됨
- 같은 response의 chapterId=20,000,100 Chapter snapshot에 BoxStatus 후보값 1이 존재
- 실제 BoxStatus는 bit mask이므로 boxIndex와 bit 위치의 매핑을 추가 확인해야 함

## 7. 다음 추적 포인트

다음은 frame 430 자체보다 **0x14 이전/이후의 동일 chapter snapshot 비교**가 중요하다.

확인 순서:
```
1. chapterId=20,000,100인 field 43 검색
2. BoxStatus 후보(field 4)의 이전 값 확인
3. frame 428 boxIndex=5 요청
4. frame 430 response의 field 4=1 확인
5. boxIndex 5 ↔ BoxStatus bit 매핑 확인
6. ProtoChapter protobuf serializer/deserializer에서 field 번호 직접 확인
```

현재 가장 중요한 확정 경로:
```
frame 428
→ opcode 0x14
→ chapterId 20,000,100
→ boxIndex 5
→ server response frame 430
→ field 43 Chapter snapshot
→ Id=20,000,100
→ Progress=6
→ BoxStatus 후보/매핑 field=4
→ 값=1
```


## 8. 2026-09-30 chapterId=20000100 상태 변화 추적

### 8.1 이전 동일 Chapter 응답
통합 PCAP에서 동일 `chapterId=20000100`은 먼저 frame 340/341의 0x13 요청과 frame 343/346의 0x13 응답에 등장한다. frame 343/346에는 `field 6 = 20000100` 및 `field 44` 계열 데이터가 있지만, frame 430에서 확인된 `field 43` Chapter snapshot은 확인되지 않는다.

### 8.2 Box 요청 직전/직후
```text
frame 428 C→S
  opcode = 0x14
  chapterId = 20000100
  boxIndex = 5

frame 430 S→C
  opcode = 0x14
  chapterId = 20000100
  field 43 = Chapter snapshot
```

frame 430:
```text
field 1 = 20000100
field 3 = 6
field 4 = 1
field 9 = {1,15}
field10 = {1,15}
field11 = 1
```

따라서 0x14 요청 직후 Chapter state가 response에 포함되는 것은 확인된다.

### 8.3 BoxStatus 0→1 변화는 미증명
현재 PCAP에는 0x14 요청 직전의 동일 Chapter snapshot이 없으므로 `이전 BoxStatus=0 → boxIndex 5 수령 → 이후 BoxStatus=1`의 시간적 변화는 직접 증명되지 않는다.

정적 분석에서 확정된 것은:
```text
IsBoxReceived(mask) = (BoxStatus & mask) != 0
```
뿐이다. 따라서 boxIndex 5의 실제 mask가 1인지도 아직 확정하지 않는다.

### 8.4 현재 가장 강한 연결
```text
0x14 request
 ├─ chapterId = 20000100
 └─ boxIndex  = 5
        ↓
0x14 response
 └─ Chapter snapshot
     ├─ Id = 20000100
     ├─ Progress = 6
     └─ field 4 = 1  ← BoxStatus 후보
```

Ghidra의 `ProtoChapter +0x10=Id`, `+0x14=Status`, `+0x18=Progress`, `+0x1C=BoxStatus`와 대응한다. 다만 protobuf serializer/deserializer에서 field 번호를 직접 확인하기 전까지 field 4의 최종 매핑과 bit 의미는 보수적으로 유지한다.

### 8.5 다음 추적
1. 다른 PCAP에서 `chapterId=20000100` Chapter snapshot 검색
2. Box 수령 전/후 field 4 비교
3. `IsBoxReceived(mask)` 호출부에서 실제 mask 확보
4. ProtoChapter serializer/deserializer에서 field 번호 직접 확인

현재 결론:
```text
chapterId=20000100 동일성       확정
0x14 request ↔ chapterId       확정
0x14 response ↔ Chapter state 확정
ProtoChapter +0x1C=BoxStatus   확정
BoxStatus bitmask              확정
BoxStatus 0→1 변화             미확정
boxIndex 5 ↔ mask 1            미확정
```
