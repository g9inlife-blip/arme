# 2026-09-30 인게임 네트워크 Chapter Box 후속 분석

## 14. Chapter BoxStatus 직접 write 추적 결과

이번 단계에서는 `ProtoChapter.BoxStatus`의 실제 변경 지점을 찾는 것을 우선했다.

### 14.1 setter 자체는 단순 field write

`ProtoChapter$$set_BoxStatus @ 015acf8c`:

```text
015acf8c  str w1,[x0,#0x1c]
015acf90  ret
```

즉 `ProtoChapter + 0x1C = BoxStatus`가 확정된다.

### 14.2 setter caller는 현재 Listing에서 직접 확보되지 않음

GitHub Ghidra Listing 검색에서는 `set_BoxStatus`의 Calls IN이 비어 있다. 따라서 현재 자료만으로 특정 response/merge 함수가 setter를 직접 호출한다고 단정할 수 없다.

특히 `DataCenter.ProccessRequestRes @ 016e203c`가 opcode `0x14` 처리 후 `set_BoxStatus`를 호출한다고 아직 확정하지 않는다.

### 14.3 BoxStatus 읽기 경로는 확정

```text
ChapBoxMono.LayBoxItem @ 00e55c80
BattleMapMono.LayChapterItem @ 00e4f918
BattleSectionMono.SetStageBoxAndBar @ 00e53380
        ↓
ProtoChapter.IsBoxReceived @ 015acfe8
        ↓
BoxStatus & mask
```

Chapter Box UI와 Section Box UI가 동일한 `BoxStatus` bitmask를 사용한다.

## 15. Chapter 상태 merge 후보 재추적

### 15.1 MergeSectionSnapShot

`DataCenter.MergeSectionSnapShot @ 016e5908`는 실제 함수 주소가 여러 Listing의 Calls IN에서 확인되지만, 현재 저장소에는 이 함수의 독립 Function Listing 본문이 없다.

따라서 현재 확인 가능한 것은 **함수 존재 및 DataManager 관련 참조**까지이며, 내부에서 `ProtoChapter +0x1C`를 쓰는지는 미확정이다.

### 15.2 MergeSections

`DataCenter.MergeSections @ 016e55dc`도 존재가 확인된다.

검색 결과에서는 `Dictionary<int, object>` 계열 입력을 순회하는 구조라는 기존 분석 기록이 있으나, 현재 검색 결과만으로 `ProtoChapter.BoxStatus`와 직접 연결되는 field write는 확인되지 않았다.

따라서:

```text
GetSections(0x13)
 → MergeSections
 → ProtoChapter
```

의 전체 연결은 아직 가설 단계로 유지한다.

### 15.3 MergeItem / MergeEquip / MergeWeapon

다음 함수들의 존재 및 DataManager 관계는 확인된다.

```text
MergeItem  @ 016e4700
MergeEquip @ 016e4348
MergeWeapon @ 016e5be4
```

하지만 현재 Listing 인덱스에는 독립 본문이 없어 Chapter BoxStatus와의 직접 관계는 확인되지 않았다.

특히 `MergeItem`은 Chapter Box 수령 후 실제 아이템 보상이 추가되는 경로와 연결될 가능성은 있으나, 현재 증거만으로 opcode `0x14`의 보상 처리 함수라고 확정하지 않는다.

## 16. ProccessRequestRes 주변의 현재 결론

`NetworkCenter.TryHandleResponse @ 015b41e0`에서:

```text
Request.SetResponse(OpInfo)
        ↓
callback
        ↓
DataCenter.ProccessRequestRes @ 016e203c
```

호출은 확정되어 있다.

그러나 `ProccessRequestRes`의 독립 Listing 본문이 현재 저장소에 없기 때문에 opcode `0x14` 분기와 `BoxStatus` 갱신을 직접 확인하지 못했다.

따라서 현재 가장 안전한 모델은:

```text
GetChapterBoxReward
  opcode 0x14
        ↓
NetworkCenter / TCPTube
        ↓
Deserialize → OpInfo
        ↓
ProccessRequestRes
        ↓
[Chapter state merge 지점 미확정]
        ↓
ProtoChapter.BoxStatus +0x1C
```

이다.

## 17. 추가로 확인된 Section 상태 경로

`GetSections @ 00ddea78`는 opcode `0x13`이고 u32 인자 1개를 전달한다.

현재 `MergeSections @ 016e55dc`가 별도로 존재하므로 Section 목록 응답을 DataCenter 상태로 병합하는 후보로 볼 수 있다.

다만 `MergeSections`와 `MergeSectionSnapShot` 중 어느 것이 특정 response opcode를 처리하는지는 현재 증거만으로 결정하지 않는다.

## 18. 다음 작업

다음 단계는 함수 이름 추정이 아니라 **ProtoChapter 타입/필드 자체를 역으로 추적**한다.

우선순위:

1. `ProtoChapter` 생성자/초기화 함수 검색
2. `ProtoChapter.Id/Status/Progress/BoxStatus` setter의 Calls IN 비교
3. `set_Progress`, `set_Status`, `set_Id`가 같은 함수에서 연속 호출되는지 검색
4. 그 함수가 `MergeSections`, `MergeSectionSnapShot`, `ProccessRequestRes`와 연결되는지 확인
5. 가능하면 원본 Ghidra Listing에서 `str w?,[x?,#0x1c]` 직접 검색
6. 마지막으로 opcode `0x14` response와 BoxStatus bit 변경을 PCAP/runtime에서 검증

현재는 `0x14 → BoxStatus`를 아직 미확정으로 유지한다.

## 19. ProtoChapter 생성자/Setter 역추적 결과

이번 단계에서 실제 Listing을 다시 확인했다.

### 19.1 생성자는 상태 필드를 초기화하지 않음

`ProtoChapter$$.ctor @ 015acff8`:

```text
015acff8  mov x1,xzr
015acffc  b 0x02194104
```

즉 현재 확보된 생성자 Listing에는 `Id/Status/Progress/BoxStatus`에 대한 명시적 초기화가 없다. 단순히 `System.Object$$.ctor`로 전달된다.

### 19.2 4개 setter 모두 단순 field write

확인된 offset:

```text
set_Id         @ 015acf5c → [x0,#0x10]
set_Status     @ 015acf6c → [x0,#0x14]
set_Progress   @ 015acf7c → [x0,#0x18]
set_BoxStatus  @ 015acf8c → [x0,#0x1c]
```

특히 `set_BoxStatus`의 Calls IN은 비어 있으며, 다른 3개 setter 역시 현재 저장된 Function Listing에서 Calls IN이 확인되지 않는다.

### 19.3 중요한 결과

따라서 **setter 호출 체인을 따라가는 방식은 현재 Listing 데이터에서는 막혀 있다.**

현재 가장 유효한 다음 방향은:

```text
ProtoChapter setter 호출 추적
        X  (Calls IN 미확보)
        
        ↓ 전환
        
ProtoChapter 객체를 생성/채우는 상위 함수
        ↓
field offset +0x10/+0x14/+0x18/+0x1c
        ↓
MergeSections / MergeSectionSnapShot / ProccessRequestRes
```

즉 다음 단계에서는 함수명보다 **`[x?,#0x10]`, `[x?,#0x14]`, `[x?,#0x18]`, `[x?,#0x1c]`가 함께 등장하는 Listing**을 찾는 것이 우선이다.

### 19.4 현재 결론

- `ProtoChapter +0x1C = BoxStatus`: 확정
- `BoxStatus & mask` 방식: 확정
- 생성자에서 BoxStatus 초기화: 현재 Listing상 확인되지 않음
- setter 직접 호출자: 미확인
- `opcode 0x14 → BoxStatus`: 아직 미확정
- 다음 핵심 목표: **4개 필드 offset을 함께 쓰는 상위 merge/deserialize 함수 확보**


## 20. Merge 계열 재추적 결과

이번에는 후보 함수 자체의 의미를 좁혔다.

### 20.1 MergeSectionSnapShot은 Section 상태 병합 쪽으로 확인

기존 Assembly 분석 기록에서 `MergeSectionSnapShot @ 016e5908`는 `Dictionary<int,int>`를 순회하고 기존 dictionary와 비교한 뒤 변경된 값을 `set_Item`으로 갱신한다.

또한 현재 기록된 응답 경로는:

```text
opcode 0x13
 → response
 → ProccessRequestRes
 → MergeSectionSnapShot
 → Section field
```

형태다.

따라서 이 함수는 **Chapter BoxStatus 갱신 후보라기보다 Section snapshot 병합 함수**로 보는 것이 더 타당해졌다.

### 20.2 MergeSections도 Section dictionary 처리

`MergeSections @ 016e55dc` 역시 Section dictionary를 처리하며, 기존 분석에는 특정 Status 조건에서 dictionary `set_Item`을 수행하는 구조가 기록되어 있다.

따라서 현재까지는:

```text
MergeSectionSnapShot → Section snapshot
MergeSections        → Section collection
```

으로 역할이 좁혀진다.

둘 모두에서 `ProtoChapter +0x1C` 직접 write는 확인되지 않았다.

### 20.3 ProccessRequestRes의 역할

`ProccessRequestRes @ 016e203c`는 여러 상태 처리 함수의 호출자로 확인되지만 독립 Listing 본문이 없다.

따라서 현재 증거로는:

```text
ProccessRequestRes
 ├─ Section 관련 처리
 ├─ Item/Equip/Weapon 관련 처리
 ├─ UserInfo 관련 처리
 └─ 기타 상태 처리
```

정도로만 확정할 수 있다.

### 20.4 중요한 방향 전환

Chapter BoxStatus를 찾기 위해 `MergeSections / MergeSectionSnapShot`를 계속 파는 것보다,

**Chapter 객체 자체가 DataCenter 내부에서 어디에 저장되고 어떤 함수가 갱신하는지 찾는 것**이 다음 핵심이다.

다음 검색 대상:

1. `Dictionary<int, ProtoChapter>` 또는 `Dictionary<int, object>` 형태의 Chapter 저장소
2. `ProtoChapter`를 반환/검색하는 DataCenter 함수
3. Chapter Id를 key로 사용하는 함수
4. `GetChapterBoxReward(0x14)`와 같은 opcode 주변의 상태 객체 처리
5. 실제 PCAP에서 `0x14` response payload 변화와 BoxStatus bit 변화를 대조

현재 결론은 그대로다.

**`0x14 → BoxStatus`는 아직 미확정이며, Section merge 계열은 Chapter BoxStatus의 직접 갱신점이 아닌 것으로 범위를 좁혔다.**


## 21. OpInfo.Chapters 진입점 재확인

`OpInfo$$get_Chapters @ 015aadec`는 `[x0,#0xc0]`를 읽고, `set_Chapters @ 015aadf4`는 `[x0,#0xc0]`에 저장한다. 따라서 `OpInfo +0xC0 = Chapters`가 확정된다.

`set_Chapters`의 Calls IN은 비어 있어 실제 deserialize 호출자는 아직 확인되지 않았다. `ProtoChapter` 검색에서도 상위 호출자가 거의 잡히지 않아, Chapter 객체를 직접 추적하기보다 **OpInfo.Chapters가 `ProccessRequestRes`로 넘어가는 지점**을 찾는 것이 더 효율적이다.

`DataCenter$$RefreshBoxList @ 016e6c64`와 두 람다(`016ea0d4`, `016ea154`)도 확인했지만, 현재 참조는 `ItemData.isBoxItem` 및 Excel Item 데이터 처리 쪽이므로 `ProtoChapter.BoxStatus` 갱신점으로 연결할 근거가 없다.

현재 흐름은 다음 수준까지 확정한다.

```text
Server response
  ↓ deserialize
OpInfo.Chapters (+0xC0)
  ↓
ProccessRequestRes
  ↓
Chapter 상태 저장/병합  ← 미확정
  ↓
ProtoChapter.BoxStatus (+0x1C)
```

다음은 `OpInfo$$get_Chapters` 호출자와 `ProccessRequestRes` 내부의 Chapters 처리 지점을 집중 추적한다.

현재 결론: `OpInfo +0xC0 = Chapters` **확정**, `ProtoChapter +0x1C = BoxStatus` **확정**, `0x14 → BoxStatus`는 **미확정**.


## 22. OpInfo.Chapters 상위 사용처 재추적

이번 단계에서는 `get_Chapters`의 직접 호출자 확보를 다시 시도하고 Chapter UI 진입점과 대조했다.

### 22.1 직접 setter/caller는 여전히 미확보

`ProtoChapter$$set_Id`, `set_Status`, `set_Progress`, `set_BoxStatus` Function Listing은 모두 Calls IN이 비어 있다.

따라서 현재 Listing 인덱스만으로는 Chapter 객체를 채우는 deserialize/merge 함수가 setter를 직접 호출한다고 볼 수 없다.

### 22.2 Chapter 데이터의 실제 소비 지점은 확인

`BattleMapMono$$InitChapters @ 00e4e080`가 `Chapters` 관련 처리의 핵심 UI 진입점으로 반복 확인된다.

Calls IN 검색에서도 `BattleMapMono$$InitChapters`가 여러 UI/데이터 접근 함수에서 반복 참조된다. 따라서 `OpInfo.Chapters`가 최종적으로 Chapter 맵 UI 구성에 사용되는 구조는 뒷받침된다.

현재 구조:

```text
OpInfo.Chapters (+0xC0)
        ↓
DataCenter 상태
        ↓
BattleMapMono.InitChapters @ 00e4e080
        ↓
Chapter/Box UI
```

### 22.3 중요한 제한

`BattleMapMono.InitChapters`의 독립 Listing 본문은 현재 인덱스에서 확보되지 않았다. 따라서 이 함수가 `get_Chapters`를 직접 호출하는지, 별도 Chapter cache를 읽는지는 아직 확정하지 않는다.

PCAP 파일 자체도 GitHub repository에 binary로 존재하지 않아 현재 GitHub connector만으로 `0x14` response payload bytes를 직접 대조할 수 없다.

### 22.4 다음 우선순위

1. `BattleMapMono.InitChapters @ 00e4e080` 실제 Listing 확보
2. 내부의 `get_Chapters` / `ProtoChapter` / `BoxStatus` 접근 확인
3. `new ProtoChapter` 또는 deserialize 코드 탐색
4. `Id/Status/Progress/BoxStatus` 4개 field 동시 접근 코드 탐색
5. 로컬 PCAP이 있으면 `0x13/0x14` response 직접 추출 및 상태 대조

현재 결론:

**`OpInfo +0xC0 = Chapters` 확정 / `ProtoChapter +0x1C = BoxStatus` 확정 / `BattleMapMono.InitChapters` Chapter 소비 지점 확인 / `0x14 → BoxStatus` 미확정.**


## 23. 2026-09-30 Chapter 전투 PCAP JSON 확보

`research/PCAP/챕터선택_전투승리보상까지.json`이 push되어 실제 패킷 JSON을 직접 대조할 수 있게 되었다.

### 23.1 확인 결과

```text
총 164 packet
UDP/KCP: 10.215.173.1:33922 ↔ 182.92.62.79:8000
```

주요 application packet:

```text
89   client → server    77 bytes
91   server → client   221 bytes
93   client → server    77 bytes
95   server → client   301 bytes
137  client → server    93 bytes
139  server → client   269 bytes
146  client → server    77 bytes
147  client → server    77 bytes
149  server → client   237 bytes
159  client → server   109 bytes
162  server → client  1400 bytes
163  server → client   481 bytes
```

162/163은 연속된 대형 서버 응답으로 확인되며 KCP fragment 재조립 대상으로 잡는다.

### 23.2 Framing

application packet 앞부분에 다음 공통 값이 반복된다.

```text
1eee45d6fd69e607
51 ...  client → server
52 ...  server → client
```

예:

```text
frame 139
1eee45d6fd69e607 51 0020 00a6e338c2 0f000000 f1000000 ...

frame 149
1eee45d6fd69e607 51 0020 00e0ea38c2 10000000 d1000000 ...
```

따라서 framing 영역과 application 데이터 영역을 분리해서 추적할 수 있다.

### 23.3 Chapter/BoxStatus 추적에 대한 의미

현재 JSON에서 application 데이터 자체는 암호화된 형태이므로 plaintext `0x13/0x14`는 아직 직접 확인되지 않는다.

따라서 현재 가장 중요한 후보 구간은:

```text
frame 159
   ↓
frame 162 + 163
```

이 구간을 기준으로 이후 `OpInfo.Chapters`와 `ProtoChapter.BoxStatus` 변화를 대조한다.

단, 현재 단계에서 **162/163이 0x14 응답이라고 확정하지 않는다.**

### 23.4 상태 갱신

- PCAP JSON 확보: 확인
- 164 packet 분석: 확인
- KCP application packet 식별: 확인
- 162+163 대형 응답 확인: 확인
- plaintext opcode 0x13/0x14: 미확인
- 0x14 → BoxStatus: 미확정

다음은 159 → 162/163 구간의 실제 application message 복원과 `OpInfo.Chapters` 대조를 우선한다.


## 24. 2026-09-30 KCP 64-bit Header 및 암호화 메시지 경계 확정

PCAP JSON과 Ghidra의 `Alioth.S1.Core.KCP$$EncodeSegment @ 015b8774`를 교차 확인한 결과, 이번 PCAP의 KCP header 구조를 직접 확정했다.

### 24.1 게임 KCP Segment 구조

`EncodeSegment`가 다음 순서로 기록한다.

```text
+0x00  uint64  Segment.Conv
+0x08  uint8   Cmd
+0x09  uint8   Frg
+0x0A  uint16  Wnd
+0x0C  uint32  Ts
+0x10  uint32  Sn
+0x14  uint32  Una
+0x18  uint32  Len
+0x1C  data
```

즉 이 게임의 KCP segment header는 **28 bytes**이며, 일반적인 32-bit conv가 아니라 64-bit conv를 사용한다.

실제 PCAP frame 162:

```text
conv = 1eee45d6fd69e607
cmd  = 0x51
frg  = 1
wnd  = 0x0020
sn   = 0x11
una  = 0x06
len  = 0x55c = 1372
```

frame 163:

```text
conv = 1eee45d6fd69e607
cmd  = 0x51
frg  = 0
wnd  = 0x0020
sn   = 0x12
una  = 0x06
len  = 0x1c5 = 453
```

따라서 두 packet은 같은 conv에서 `frg 1 → 0`, `sn 0x11 → 0x12`로 이어지는 하나의 KCP message로 확정할 수 있다.

### 24.2 실제 application message 재조립

```text
frame 162 data = 1372 bytes
frame 163 data =  453 bytes
------------------------
총              1825 bytes
```

재조립 후 첫 부분은:

```text
80
5710e3494fa79b32be5d738c23d85593
...
```

Ghidra에서 확인한 `KCPTube.TryRead → DecryptUnSafe` 경로와 대조하면 application message는 다음 구조로 해석된다.

```text
[0x80 flags]
[16-byte IV]
[ciphertext]
```

이번 162+163 응답의 경우:

```text
flags      = 0x80
IV         = c4f0862cf0271983b553998be415226a
ciphertext = 1808 bytes
```

`1808 % 16 == 0`이므로 AES/Rijndael block ciphertext 경계도 정확히 맞는다.

### 24.3 요청 frame 159도 동일 구조

frame 159는 KCP data 81 bytes이며:

```text
flags      = 0x80
IV         = 5710e3494fa79b32be5d738c23d85593
ciphertext = 64 bytes
```

즉 전투 직전/직후의 요청도 동일한 암호화 application framing을 사용한다.

### 24.4 중요한 변경점

이제 단순히 `162/163이 큰 응답이다` 수준이 아니라:

```text
frame 159
  KCP reassembly
  ↓
  0x80 + IV16 + ciphertext64

frame 162 + 163
  KCP reassembly
  ↓
  0x80 + IV16 + ciphertext1808
```

까지 확정했다.

따라서 다음 단계는 KCP 분석이 아니라 **session Key 확보 → 159 request / 162+163 response 복호화**다.

### 24.5 Chapter/BoxStatus 추적 목표

복호화가 성공하면 다음 순서로 바로 확인한다.

```text
plaintext
 ↓
OperationCode
 ↓
OpInfo / response object
 ↓
Chapters (+0xC0)
 ↓
ProtoChapter
 ├─ Id       +0x10
 ├─ Status   +0x14
 ├─ Progress +0x18
 └─ BoxStatus+0x1C
```

특히 162+163의 1808-byte 응답에서 `ProtoChapter.BoxStatus`가 포함되는지 직접 확인한다.

### 24.6 현재 결론

- 64-bit KCP conv: **확정**
- KCP header 28 bytes: **확정**
- frame 162+163 단일 fragmented message: **확정**
- 응답 flags `0x80`: **확정**
- IV 16 bytes: **확정**
- ciphertext 1808 bytes: **확정**
- 16-byte block alignment: **확정**
- plaintext opcode `0x13/0x14`: **아직 미확인**
- `0x14 → BoxStatus`: **아직 미확정**

다음 작업은 `KCPTube.Handshake2 → Key` 생성값을 runtime/코드에서 확보하여 이 두 메시지를 실제 복호화하는 것이다.


## 25. 2026-09-30 KCP 실제 복호화 결과에 따른 경로 정정

이번 단계에서 `research/PCAP/챕터선택_전투승리보상까지.json`의 KCP session key를 실제 복구하고 frame 159 / 162+163을 복호화했다.

### 25.1 session key 실제 확보

KCP client public:

```text
0x3B235655562743FA
0xD4BED6816A9F1C5C
```

server public:

```text
0x7637ACF954E564B3
0xDD73013D938774B9
```

DH modulus:

```text
p = 0xFFFFFFFFFFFFFFC5
  = 2^64 - 59
```

discrete log으로 복구한 client private:

```text
private1 = 0x12499F5C0DDB1AF5
private2 = 0x6D0F828A5EA102C2
```

shared secret:

```text
secret1 = 0xEB751E69D959ADC0
secret2 = 0xAD53F6266C3490EA
```

실제 Key:

```text
c0ad59d9691e75ebea90346c26f653ad
```

### 25.2 frame 159 실제 plaintext

frame 159는:

```text
flag = 0x80
OpCode = 0x17
```

으로 복호화된다.

따라서 기존에 frame 159를 `GetChapterBoxReward` 요청으로 연결한 것은 잘못된 연결이다.

### 25.3 frame 162+163 실제 plaintext

두 KCP fragment를 재조립하면:

```text
flag = 0xC4
IV = f0862cf0271983b553998be415226aee
ciphertext = 1808 bytes
```

복호화 결과는 gzip stream이며 gzip 해제 후 5749-byte protobuf-like data가 나온다.

Top-level:

```text
field 1 = SerialNumber
field 2 = OpCode 0x17
```

즉:

```text
159 request
   ↓
OpCode 0x17

162+163 response
   ↓
OpCode 0x17
```

이다.

### 25.4 현재 가설 변경

기존:

```text
159
 ↓
162+163
 ↓
0x14
 ↓
BoxStatus
```

는 폐기한다.

현재:

```text
159
 ↓
0x17 request
 ↓
162+163
 ↓
0x17 response
 ↓
[Chapter state 포함 여부 별도 확인]
```

으로 수정한다.

### 25.5 0x14 Box reward는 별도 capture 필요

정적 분석상:

```text
GetChapterBoxReward @ 00ddeea8
opcode = 0x14
payload = u32 x2
```

이므로 실제 BoxStatus 변경을 확정하려면 **box를 실제로 클릭하여 보상을 수령하는 별도 PCAP**에서 `0x14` request/response를 확보해야 한다.

현재 PCAP에는 직접 복호화 가능한 application message 중 `0x14`가 확인되지 않았다.

따라서 현재 결론:

- ProtoChapter +0x1C = BoxStatus: 확정
- BoxStatus bitmask 읽기: 확정
- GetChapterBoxReward opcode 0x14: 정적 분석상 확정
- 159 → 162+163 = 0x14: **반증**
- 0x14 response → BoxStatus: 미확정


## 26. 2026-09-30 이벤트던전 Box 보상 선택/오픈/획득 PCAP JSON 분석

추가된 `research/PCAP/이벤트던전_box보상선택_오픈_획득.json`을 Git blob 기준으로 직접 파싱했다.

### 26.1 캡처 규모 및 Game Server 구간

- 총 packet: **103**
- TCP Game Server: `43764 ↔ 8000`
- KCP/UDP Game Server: `45186 ↔ 8000`
- TCP handshake 직후 DH 공개값 교환 확인

TCP client handshake frame 84:

``
length = 0x169
marker = 0x01
public1 raw = `ae a5 9a b9 34 02 73 6d`
public2 raw = `9b 90 eb db b5 0a a6 ed`
```

※ 위 값은 Listing/PCAP 바이트 순서를 구분해서 기록해야 하므로, 실제 분석에서는 raw 8-byte LE 기준으로 사용한다.

서버 frame 86은:

``
length = 0x19
marker = 0x01
serverPublic1 = 0x1e0f84d1514c8dbf
serverPublic2 = 0xe187d59f859685ba
```

이다.

### 26.2 핵심 KCP application packet

```
frame 92  C→S  UDP 45186→8000  UDP length 85
frame 93  S→C  ACK              UDP length 36
frame 94  S→C  UDP 8000→45186  UDP length 389
frame 95  C→S  ACK              UDP length 36
```

KCP header는 28 bytes이므로:

```
frame 92 KCP data length = 0x31 = 49 bytes
frame 94 KCP data length = 0x161 = 353 bytes
```

frame 92 header:

```
conv = 0x43c7af942c0bf54d
cmd  = 0x51
frg  = 0
wnd  = 0x0001
sn   = 0x10
una  = 0x13
len  = 0x31
```

frame 94 header:

```
conv = 0x43c7af942c0bf54d
cmd  = 0x51
frg  = 0
wnd  = 0x0020
sn   = 0x11
una  = 0x13
len  = 0x161
```

즉 이번 캡처는 요청/응답 모두 단일 KCP segment이며 fragment 재조립은 필요 없다.

### 26.3 매우 중요한 암호화 framing 확인

frame 92의 KCP data 49 bytes는 정확히:

```
0x80
+ 16-byte IV
+ 32-byte ciphertext
= 49 bytes
```

즉:

```
flag = 0x80
IV   = b3c9617c319f7d74ffe8d10b33d9bcae
CT   = 32 bytes
```

frame 94도:

```
KCP data = 353 bytes
flag     = 0xC4
IV       = a51324f4b36f138fe67259daee379cd3
CT       = 336 bytes
```

으로 `1 + 16 + (16 × N)` 구조가 정확히 성립한다.

따라서 기존에 확보한 `flag + IV16 + AES/Rijndael ciphertext` 구조와 동일하다.

### 26.4 현재 Box reward 분석에서의 의미

정적 분석으로 이미:

```
ClickGetReward
 → GetChapterBoxReward @ 00ddeea8
 → opcode 0x14
 → chapterId + boxIndex
```

가 확정되어 있다.

이번 캡처는 제목상 Box 보상 선택/오픈/획득 동작을 포함하고 있고, 실제 Game Server KCP application traffic이 **단일 요청(frame 92) → 단일 응답(frame 94)** 형태로 존재한다.

따라서 현재 가장 유력한 매칭은:

```
frame 92  C→S  encrypted request  ← 0x14 후보
frame 94  S→C  encrypted response ← 0x14 후보
```

이다.

단, **복호화 전에는 0x14라고 확정하지 않는다.**

### 26.5 다음 핵심 작업

현재 막힌 부분은 PCAP packet 추출이 아니라 **이번 세션의 DH64 session key**다.

이미 Ghidra에서:

``
DH64::.ctor
 → System.Random::.ctor

DH64::KeyPair
 → Random.Next() #1/#2
 → private = (Next1 << 32) | (Next2 + 1)
 → public = 5^private mod (2^64-59)
```

가 확정되어 있다.

따라서 이번 캡처는 다음 순서로 진행한다.

1. `System.Random` seed/구현 확인
2. 이번 handshake 시점의 private1/private2 재현 가능성 확인
3. session key 생성
4. frame 92 복호화 → request opcode 확인
5. frame 94 복호화 → response opcode/Chapter state 확인
6. response의 `ProtoChapter +0x1C`(BoxStatus) 변화 확인

### 26.6 현재 결론

- 이벤트 Box 보상 PCAP JSON: **확보 및 직접 파싱 완료**
- Game Server KCP request/response pair: **확인**
- request frame 92: **0x14 유력 후보**
- response frame 94: **0x14 response 유력 후보**
- plaintext opcode: **미확정**
- BoxStatus 갱신: **미확정**
- 다음 병목: **이번 세션 DH64 private/session key 재현**


## 27. 2026-09-30 후속 추적 — IsBoxReceived 호출부 및 추가 계정 PCAP 확인

### 27.1 IsBoxReceived 호출부 3곳 확정

`ProtoChapter$$IsBoxReceived @ 015acfe8`의 Calls IN Listing에서 다음 3개 호출부가 확인된다.

```text
ChapBoxMono$$LayBoxItem              @ 00e55c80
BattleMapMono$$LayChapterItem        @ 00e4f918
BattleSectionMono$$SetStageBoxAndBar @ 00e53380
        ↓
ProtoChapter.IsBoxReceived @ 015acfe8
```

따라서 Box 수령 상태는 Box 전용 UI뿐 아니라 Chapter Map과 Section Stage Box에서도 동일한 `ProtoChapter.BoxStatus` bitmask를 사용한다.

### 27.2 실제 mask 값은 아직 미확인

현재 GitHub Listing 검색에서는 위 3개 함수의 실제 본문 파일 경로가 검색 인덱스에 바로 노출되지 않아 `BL 015acfe8` 직전의 `w1` 설정값을 확보하지 못했다.

```text
ProtoChapter +0x1C = BoxStatus       확정
IsBoxReceived(mask) = (BoxStatus & mask)!=0 확정
boxIndex → mask 대응               미확정
```

특히 `boxIndex 5 → mask 1`은 아직 단정하지 않는다.

### 27.3 다른 계정 PCAP 추가 확인

사용자가 지정한:

`research/PCAP/로그인부터던전2회이후box오픈_이후장비착용.json`

파일명을 GitHub 검색으로 확인했으나 현재 connector 검색 인덱스에서는 정확한 파일명이 반환되지 않았다.

따라서 파일이 Git에 없다고 단정하지 않고, 현재 연결된 GitHub 검색 결과에서는 직접 읽지 못한 상태로 기록한다.

이 PCAP은 제목상 `던전 2회 → Box 오픈 → 보상 획득 → 장비 착용` 순서가 포함되어 있어 BoxStatus 전후 비교에 매우 유용한 후보이다.

### 27.4 다음 추적 순서

1. 해당 다른 계정 PCAP의 Git 존재/검색 가능 여부 재확인
2. 확보되면 KCP session key 복구 후 Box 전후 response 복호화
3. 동일 Chapter snapshot 전후 비교
4. `field 43` Chapter snapshot의 `field 4` 전후 비교
5. Ghidra에서 `00e55c80 / 00e4f918 / 00e53380`의 `IsBoxReceived` 호출 직전 `w1` 상수 확보
6. ProtoChapter serializer/deserializer에서 BoxStatus protobuf field 번호 직접 확정

### 27.5 현재 누적 결론

```text
ProtoChapter +0x1C = BoxStatus                  확정
IsBoxReceived = (BoxStatus & mask) != 0         확정
IsBoxReceived 호출부 3곳                         확정
GetChapterBoxReward = opcode 0x14               확정
0x14 request/response = 이벤트 Box PCAP 후보     유력
0x14 response가 BoxStatus를 갱신                 미확정
boxIndex → mask 값                               미확정
다른 계정 PCAP 직접 비교                         아직 파일 미검색
```

다음 세션은 다른 계정 PCAP의 Git 존재/복호화 → BoxStatus 전후 비교부터 재개한다.


## 28. 2026-09-30 다른 계정 PCAP 복호화 및 실제 0x14 검증

### 28.1 Git 파일 존재 및 DH endian 정정

`research/PCAP/로그인부터던전2회이후box오픈_이후장비착용.json`은 Git blob으로 실제 존재한다.

- packet: 306
- blob SHA: `faeb47f64d76158c731c36abb741773e376e46a2`
- KCP client port: `51943`
- KCP server: `182.92.62.79:8000`

기존 기록의 candidate key에는 **server public 8-byte LE 해석 오류**가 있었다.

실제 KCP Handshake2 기준 offset 17/25의 raw bytes:

```
server public #1 raw = cb 43 ff 46 bc 8a d1 d4
server public #2 raw = a8 59 ce f7 2e 5f cc a8
```

BitConverter.ToUInt64 기준 실제 정수:

```
serverPublic1 = 0xd4d18abc46ff43cb
serverPublic2 = 0xa8cc5f2ef7ce59a8
```

client public raw:

```
a6 0f f3 68 ac df 81 d8
ee c2 4e ec ff 6a c7 3b
```

실제 정수:

```
clientPublic1 = 0xd881dfac68f30fa6
clientPublic2 = 0x3bc76affec4ec2ee
```

discrete log으로 검증된 client private:

```
private1 = 0x1021bdff42518bc9
private2 = 0x1711d8ad4dc70e26
```

shared secret:

```
secret1 = 0x490b1c9b2ce9abdc
secret2 = 0xcf8fdf34709590da
```

따라서 이번 세션의 실제 KCP key:

```
dcabe92c9b1c0b49da90957034df8fcf
```

이 key로 실제 application ciphertext의 CBC/PKCS7 복호화가 성공했다.

### 28.2 복호화 성공으로 암호화 경로 재검증

예:

```
frame 260 C→S
flag = 0x80
opcode = 0x16
```

plaintext:

```
field 1 = serial
field 2 = 0x16
field 6 = 20000100
field 7 = 21000080
```

또한:

```
frame 273 C→S
opcode = 0x17
```

까지 정상 복호화되었다.

따라서 새 계정 PCAP에서도:

```
DH64
 ↓
16-byte key
 ↓
Rijndael CBC/PKCS7
 ↓
KCP encrypted application
 ↓
protobuf-like OpInfo
```

경로가 실제 bytes 수준에서 검증된다.

### 28.3 실제 Box reward request 확정

**frame 283 C→S**:

```
KCP cmd = 0x51
encrypted flag = 0x80
plaintext:
field 1 = serial
field 2 = 0x14
field 4 = { field 1 = 20000100, field 2 = 5 }
field 6 = 20000100
field 7 = 1
```

따라서:

```
opcode = 0x14
chapterId = 20,000,100
boxIndex = 5
```

가 실제 PCAP plaintext로 직접 확정된다.

이는 정적 분석의:

```
ChapBoxMono.ClickGetReward
 ↓
GetChapterBoxReward(chapter.id, UIData.data)
 ↓
opcode 0x14
 ↓
chapterId + boxIndex
```

와 정확히 일치한다.

### 28.4 실제 Box reward response 확정

**frame 285 S→C**도 정상 복호화된다.

Top-level:

```
field 1 = serial
field 2 = 0x14
```

그리고:

```
field 43
 ├─ field 1 = 20000100
 └─ field 2 = nested Chapter data
```

nested Chapter data:

```
field 1 = 20000100
field 3 = 12
field 4 = 3
field 9 = { field1 = 1, field2 = 15 }
field10 = { field1 = 1, field2 = 15 }
field11 = 1
```

즉 **0x14 response에 chapterId=20000100인 Chapter snapshot이 실제 포함**되는 것은 확정이다.

### 28.5 BoxStatus 해석은 여기서 보류

정적 분석으로:

```
ProtoChapter +0x1C = BoxStatus
IsBoxReceived(mask) = (BoxStatus & mask) != 0
mask = 1 << boxIndex
```

가 확정되어 있다.

frame 283의 boxIndex=5이므로 UI 코드 기준 검사 mask는:

```
1 << 5 = 0x20
```

그런데 frame 285의 nested Chapter data에서 field 4 값은:

```
3
```

이다.

따라서 **nested protobuf field 4 = BoxStatus라고 지금 단정하면 안 된다.**

현재 안전한 결론:

- 0x14 request의 chapterId=20000100: 확정
- 0x14 request의 boxIndex=5: 확정
- 0x14 response의 동일 Chapter snapshot: 확정
- ProtoChapter +0x1C = BoxStatus: 확정
- boxIndex 5의 UI 검사 mask = 0x20: 확정
- response nested field 4 = BoxStatus: **보류**
- 0x14 response가 BoxStatus +0x1C를 갱신: **아직 미확정**

특히 field 4=3은 mask 0x20과 직접 일치하지 않으므로, **protobuf field 번호와 ProtoChapter 메모리 field 번호를 동일하다고 가정했던 이전 해석은 폐기**한다.

### 28.6 현재 가장 중요한 다음 작업

이제 암호/PCAP은 병목이 아니다.

다음은 **ProtoChapter protobuf field tag ↔ C# property/메모리 offset 매핑**을 직접 확보하는 것이다.

우선순위:

1. ProtoChapter deserialize/merge 코드에서 field tag 처리 확인
2. field 1 → Id 여부 확인
3. field 2 → Status 여부 확인
4. field 3 → Progress 여부 확인
5. field 4 → BoxStatus 여부 확인
6. field 9/10/11의 실제 property 확인
7. 0x14 response에서 +0x1C write가 발생하는지 확인
8. 필요하면 frame 285 직후 runtime state를 별도 hook으로 비교

### 28.7 이번 단계 최종 상태

```
다른 계정 PCAP Git 존재              확정
DH64 endian 정정                     확정
실제 KCP session key                 dcabe92c9b1c0b49da90957034df8fcf
실제 PCAP CBC/PKCS7 복호화            성공
frame 283 opcode 0x14                확정
frame 283 chapterId 20000100         확정
frame 283 boxIndex 5                 확정
frame 285 opcode 0x14 response       확정
frame 285 Chapter snapshot           확정
ProtoChapter +0x1C = BoxStatus       확정
boxIndex 5 → mask 0x20              확정
protobuf field4 = BoxStatus          보류
0x14 → BoxStatus write               미확정
```

**현재 분석의 핵심 병목은 BoxStatus 값 자체가 아니라 protobuf field tag와 ProtoChapter 메모리 field의 대응 관계다.**

## 29. 2026-09-30 ProtoChapter field mapping 재추적 결과

### 29.1 ProtoChapter Listing 범위 확인

Git의 `research/Ghidra_Listing_txt/AL`에서 `ProtoChapter$$`를 검색한 결과, 현재 저장된 Listing에는 다음 accessor/constructor가 확인된다.

```
get/set_Id
get/set_Status
get/set_Progress
get/set_BoxStatus
get/set_URL1
get/set_URL2
get/set_Readed
get/set_Timeout
get/set_OpeningTime
IsBoxReceived
.ctor
```

현재 Git Listing 검색 결과에는 `MergeFrom/ParseFrom/WriteTo/CalculateSize/Descriptor/Parser` 명시적 serializer 함수가 없다.

### 29.2 현재 강한 정적 증거

```
Id         +0x10
Status     +0x14
Progress   +0x18
BoxStatus  +0x1C
```

`get_BoxStatus`, `set_BoxStatus`, `IsBoxReceived` 모두 `+0x1C`를 직접 사용하므로 메모리 구조는 확정이다.

반면 0x14 response Chapter snapshot은:

```
field 1 = 20000100
field 3 = 12
field 4 = 3
field 9 = {1,15}
field10 = {1,15}
field11 = 1
```

이 값만으로 protobuf field tag와 C# property를 단순 1:1 대응시키면 안 된다.

### 29.3 핵심 재평가

가설 A는 `field 4 = BoxStatus`이지만, boxIndex=5의 단순 mask `1 << 5 = 0x20`과 field4=3이 직접 맞지 않는다.

따라서 현재는 가설 B, 즉 protobuf field 번호와 메모리 offset/property 순서가 단순 대응하지 않을 가능성도 유지한다.

### 29.4 0x14 이후 packet도 비교 대상

Box request 이후:

```
frame 285  S→C  0x14 response
frame 287  C→S
frame 289  S→C
frame 294  C→S
frame 296  S→C
```

가 이어진다. 따라서 BoxStatus가 frame 285에서 즉시 반영되지 않고 후속 response에서 갱신될 가능성도 확인해야 한다.

특히 `285 vs 289 vs 296`의 Chapter snapshot 변화가 중요하다.

### 29.5 다음 정적 분석 목표

1. `ProccessRequestRes @ 016e203c` 실제 Listing 확보
2. response object의 Chapter collection 접근 확인
3. Chapter 생성/병합 함수 확인
4. 해당 함수의 `ProtoChapter.set_*` 또는 `+0x1C` write 확인
5. `StarStatus`와 `BoxStatus`가 같은 merge 경로에서 갱신되는지 비교
6. 0x14 후속 response의 Chapter snapshot 변화와 대조

### 29.6 현재 상태

```
ProtoChapter +0x1C = BoxStatus              확정
IsBoxReceived가 +0x1C를 읽음              확정
0x14 request chapterId/boxIndex             확정
0x14 response Chapter snapshot              확정
protobuf field 4 = BoxStatus                미확정
field 3/4/9/10/11 의미                     미확정
0x14 response 직후 상태 갱신 시점            미확정
serializer Listing 직접 확인                현재 Git 자료에 없음
```

**다음 실질 목표는 285 → 289 → 296의 Chapter snapshot을 비교하거나, 그 값을 생성하는 merge 함수에서 +0x1C write를 직접 잡는 것이다.**
## 30. 2026-09-30 0x14 응답 Chapter snapshot 교차 비교

### 30.1 다른 계정 frame 285

실제 복호화된 frame 285의 field 43:

```
field 43
 ├─ field 1 = 20000100
 └─ field 2 = Chapter
     ├─ field 1 = 20000100
     ├─ field 3 = 12
     ├─ field 4 = 3
     ├─ field 9 = {1,15}
     ├─ field10 = {1,15}
     └─ field11 = 1
```

### 30.2 기존 통합 PCAP frame 430

기존 계정 frame 430의 동일 구조:

```
field 43
 ├─ field 1 = 20000100
 └─ field 2 = Chapter
     ├─ field 1 = 20000100
     ├─ field 3 = 6
     ├─ field 4 = 1
     ├─ field 9 = {1,15}
     ├─ field10 = {1,15}
     └─ field11 = 1
```

두 계정에서 동일 chapterId에 대해 `account A: field3=6, field4=1`, `account B: field3=12, field4=3`가 관찰된다.

### 30.3 핵심 관찰

두 PCAP 모두 0x14 request는 `chapterId=20000100`, `boxIndex=5`이다. 그런데 response Chapter의 field4는 각각 1과 3이다.

따라서 현재 데이터만으로 `field4 == BoxStatus`와 `boxIndex 5 == bit 5`를 동시에 만족하는 수령 완료 변화는 관찰되지 않는다.

가능성은 분리한다:

1. field4가 BoxStatus가 아니다.
2. 0x14 response의 Chapter snapshot이 요청 처리 후 최종 BoxStatus가 아니라 기존/부분 snapshot이다.
3. request boxIndex와 UI index가 동일하지 않다.

단, UI의 `IsBoxReceived` 호출부에서는 실제 mask가 `1 << w23`임이 확인되었으므로 UI index와 request boxIndex의 동일성은 별도 검증이 필요하다.

### 30.4 현재 결론 수정

```
ProtoChapter +0x1C = BoxStatus       확정
protobuf Chapter field3 = Progress   유력
protobuf Chapter field4 = 상태값     확정
protobuf Chapter field4 = BoxStatus  유력하지만 미확정
boxIndex → UI mask = 1 << index     정적 코드 확정
request boxIndex == UI index         미확정
0x14 response가 최종 BoxStatus 반환  미확정
```

### 30.5 다음 작업

1. `GetChapterBoxReward @ 00ddeea8`에서 request 두 번째 값의 원천 추적
2. `UIData.data` index와 request `+0x34` 관계 확인
3. `DataCenter.ProccessRequestRes @ 016e203c`의 Chapter 관련 merge 분기 추적
4. `MergeSectionSnapShot` 외 Chapter merge 후보 확인
5. raw Listing 전체에서 `set_BoxStatus @ 015acf8c` callsite 주소 검색
6. Box 요청 전 Chapter snapshot 확보

## 31. 2026-09-30 ClickGetReward / Box index 직접 Listing 재검증

### 31.1 ClickGetReward의 두 번째 인자는 변환 없이 UIData.data

`ChapBoxMono$$ClickGetReward @ 00e5705c` 실제 CH.txt Listing에서 `BaseMono.GetUIData → UIData.get_data` 후 boxed int를 `ldr w19,[x0]`로 꺼내고, `BaseData.get_id` 결과와 함께 `GetChapterBoxReward @ 00ddeea8`로 전달한다.

즉:

```text
UIData.data → boxed int 해제 → w19
Chapter(+0xd0).BaseData.id → chapterId
GetChapterBoxReward(chapterId, w19)
```

**boxIndex에 +1/-1 등의 별도 변환이 없다.**

### 31.2 Box UI index와 IsBoxReceived mask도 같은 index

`ChapBoxMono$$LayBoxItem @ 00e55c80`에서:

```text
00e55ebc  ldr w23,[x0]       ; UIData.data
00e56024  ldr x0,[x19,#0xd8] ; Chapter runtime object
00e56044  mov w8,#0x1
00e56048  lsl w1,w8,w23
00e56050  bl  0x015acfe8     ; ProtoChapter.IsBoxReceived
```

따라서 동일한 `UIData.data = i`가:

```text
수령 검사 → mask = 1 << i
클릭 요청 → boxIndex = i
```

양쪽에 그대로 사용된다.

실제 다른 계정 PCAP의 `boxIndex=5`는 정적 코드 기준 검사 mask `0x20`이 확정된다.

### 31.3 Chapter reward pair에 대한 추가 증거

`LayBoxItem`의 `List<KeyValuePair<int,int>>.get_Item @ 01ba5934` 반환값은 64비트 packed 값으로 취급된다.

```text
00e55ee4  mov x21,x0
00e55f24  lsr x1,x21,#0x20
00e55f2c  bl  0x01736d60   ; Ali.GetExcelData<object>
```

즉 pair의 **상위 32비트가 Excel data 조회 ID로 직접 사용**된다.

동일한 `get_Item`/`lsr #0x20` 패턴이 `RewardPanelMono$$ShowItem @ 0100e49c`에서도 확인된다. 따라서 Chapter reward pair는 최소한:

```text
high 32 = Excel Item ID 계열
low  32 = 수량/조건값 계열
```

로 좁혀진다. 다만 `SplitToInt32Dict @ 00df3f10` 본문을 직접 확보하기 전까지 threshold/rewardId의 key/value 방향은 최종 확정하지 않는다.

### 31.4 BoxStatus 해석 정리

현재 다음 3개는 모두 직접 확정된다.

```text
① request boxIndex = UIData.data
② IsBoxReceived mask = 1 << UIData.data
③ ProtoChapter +0x1C = BoxStatus
```

따라서 `boxIndex=5`의 최종 BoxStatus를 확인하려면 반드시 `0x20` bit를 확인해야 한다.

현재 0x14 response snapshot의 nested field4 값 `1` 또는 `3`은 `0x20`과 일치하지 않는다. 따라서 아직:

- response snapshot이 최종 수령 후 상태가 아닐 가능성
- field4가 BoxStatus가 아닐 가능성
- 후속 response에서 상태가 갱신될 가능성

을 모두 유지한다.

**현재 `protobuf field4 = BoxStatus`는 확정하지 않는다.**

### 31.5 다음 작업

1. 다른 계정 PCAP에서 0x14 이후 `Chapter 20000100` snapshot 검색
2. 후속 response의 Chapter 상태값 변화 확인
3. 다른 boxIndex의 0x14 요청이 있으면 `1 << index`와 response 상태 비교
4. 이후 `DataCenter.ProccessRequestRes @ 016e203c` Chapter merge 경로 재추적


## 32. 2026-09-30 실제 0x14 응답 재복호화 확인

추가 계정 PCAP blob을 직접 다시 읽어 `frame 285`를 DH64 복구 key로 AES-CBC 복호화했다.

```text
KCP frame 285
  flag = 0x84
  IV   = 945ec753adab00499a5cf5fd41f9cf42
  opcode = 0x14
```

복호화 protobuf top-level:

```text
field 1 = serial
field 2 = 0x14
field 4 = nested request/result data
field 6 = 20000100
field 7 = 1
field 43 = Chapter snapshot container
```

field43:

```text
field1 = 20000100
field2 = ProtoChapter-like nested message
```

nested Chapter:

```text
field1  = 20000100
field3  = 12
field4  = 3
field9  = { field1=1, field2=15 }
field10 = { field1=1, field2=15 }
field11 = 1
```

따라서 기존에 확인했던 `frame 285 / field43 / Chapter 20000100 / field4=3`은 단순 패킷 추측이 아니라 **실제 AES-CBC 복호화 결과**로 재확인됐다.

### 32.1 중요한 추가 확인

동일 PCAP의 후속 `frame 289`도 같은 key로 복호화했으며:

```text
opcode = 0x11
field6 = 10000001
field43 없음
```

이었다.

즉 frame 285의 Chapter snapshot이 frame 289에서 그대로 반복되는 구조는 아니다.

`frame 296`은 현재 동일 단일-fragment 복호화 방식으로 유효 protobuf가 나오지 않아, 별도 재검증 대상으로 남긴다.

### 32.2 현재 BoxStatus 판단

정적 분석은:

```text
ProtoChapter +0x1C = BoxStatus
IsBoxReceived(i) = (BoxStatus & (1 << i)) != 0
```

를 확정한다.

실제 0x14 request는:

```text
chapterId = 20000100
boxIndex  = 5
```

이므로 기대되는 수령 bit는:

```text
1 << 5 = 0x20
```

하지만 0x14 response의 Chapter nested `field4=3`은 `0x20`이 아니다.

따라서 현재 증거로는 **protobuf field4를 BoxStatus라고 매핑하면 모순**이다.

현재 가장 중요한 다음 작업은 `DataCenter.ProccessRequestRes @ 016e203c`에서 `OpInfo.Chapters`가 실제 `ProtoChapter` 객체로 병합되는 지점을 찾고, `set_BoxStatus @ 015acf8c`에 도달하는 값을 확인하는 것이다.


## 33. 2026-09-30 후속 정리 — BoxStatus 직접 write 경로 재검색

### 33.1 현재 정적 증거 재확정

이번 단계에서 Git의 관련 Listing을 다시 검색했다.

```
ProtoChapter$$get_BoxStatus @ 015acf84
    ldr w0,[x0,#0x1c]

ProtoChapter$$set_BoxStatus @ 015acf8c
    str w1,[x0,#0x1c]

ProtoChapter$$IsBoxReceived @ 015acfe8
    ldr w8,[x0,#0x1c]
    tst w8,w1
```

따라서 `ProtoChapter +0x1C = BoxStatus`와 bitmask 검사 구조는 변함없이 확정이다.

### 33.2 setter 호출 추적 결과

`set_BoxStatus @ 015acf8c`의 Calls IN은 현재 Git Listing에서 비어 있다.

또한 다음 3개 setter도 직접 caller가 확보되지 않았다.

```
set_Id       +0x10
set_Status   +0x14
set_Progress +0x18
set_BoxStatus +0x1C
```

따라서 setter callsite를 계속 찾는 것보다, Chapter 객체를 채우는 상위 merge/deserialize 경로를 찾는 방식으로 전환한다.

### 33.3 Section merge 계열은 우선순위 하향

현재까지 확인된:

```
MergeSections        @ 016e55dc
MergeSectionSnapShot @ 016e5908
```

은 Section collection/snapshot 처리 성격이 강하다.

현재 자료에서는 두 함수가 `ProtoChapter +0x1C`를 직접 쓰는 증거가 없다.

따라서 Chapter BoxStatus 추적의 1차 후보에서 우선순위를 낮춘다.

### 33.4 새로 확정된 중요한 연결

Box 요청 쪽은 이미 완전히 연결되어 있다.

```
ChapBoxMono.ClickGetReward @ 00e5705c
        ↓
UIData.data
        ↓
GetChapterBoxReward @ 00ddeea8
        ↓
opcode 0x14
        ↓
chapterId + boxIndex
```

실제 PCAP에서도:

```
chapterId = 20000100
boxIndex  = 5
```

가 확인되었고, response frame 285에는 같은 Chapter ID의 snapshot이 포함된다.

따라서 현재 남은 핵심은 request 생성이 아니라 **response Chapter snapshot → ProtoChapter 객체 반영**이다.

### 33.5 다음 단계 — Chapter 저장소/생성 경로 집중

다음 검색은 함수명 추정이 아니라 다음 순서로 진행한다.

1. `OpInfo.Chapters (+0xC0)`의 실제 사용처 재검색
2. `ProtoChapter` 객체를 생성/반환/검색하는 DataCenter 함수 탐색
3. Chapter ID를 key로 하는 Dictionary/cache 탐색
4. `+0x10/+0x14/+0x18/+0x1C`가 한 함수에서 함께 접근되는 Listing 탐색
5. `ProccessRequestRes @ 016e203c`와 위 함수의 연결 확인
6. PCAP의 0x14 후속 response에서 동일 Chapter snapshot이 다시 나타나는지 비교

### 33.6 현재 상태

```
ProtoChapter +0x1C = BoxStatus          확정
IsBoxReceived mask 구조                확정
UIData.data → request boxIndex         확정
boxIndex 5 → 검사 mask 0x20            확정
0x14 request chapterId/boxIndex         확정
0x14 response Chapter snapshot         확정
protobuf field4 = BoxStatus             미확정
response → ProtoChapter +0x1C write     미확정
```

이번 단계에서는 새로운 BoxStatus write 지점을 확보하지 못했다. 다음은 **OpInfo.Chapters 사용처와 Chapter 객체 저장/병합 경로**를 직접 좁힌다.


## 34. 2026-09-30 FUN_ 그룹 Listing 추가 반영

사용자가 `research/Ghidra_Listing_txt`에 명명되지 않은 함수들을 주소 prefix 기준으로 `FUN_00X.txt` 그룹화한 자료를 추가했다.

### 34.1 Git 반영 확인

최근 commit:

```
822ba036a9d70605d304679e694ff8312283ca80
message: FUN_ 추가
```

추가된 주요 그룹 파일은 `FUN_008.txt ~ FUN_026.txt`이며, 비교 결과 `FUN_015.txt`, `FUN_016.txt` 등에서 기존 개별 Listing에 없던 unnamed 함수 본문을 확인할 수 있다.

### 34.2 Chapter Box 추적에 적용한 결과

`FUN_015.txt`를 직접 확인했지만 `015a...~015e...` 영역의 unnamed 함수들은 NodeCanvas/FullSerializer/TCPTube/Asset 관련 helper가 대부분이며 `ProtoChapter` 상태 갱신과 직접 연결되는 함수는 현재 확인되지 않았다.

`FUN_016.txt`에서는 `016e0008_FUN_016e0008`가 확인된다.

이 함수는:

```
DataManager.TryGetAll
→ Enumerable.ToDictionary
→ Dictionary<int,object>
→ WeaponInfo/HeroInfo/ProtoFashion
→ DataManager
```

계열의 데이터 구성 함수이며, `ProtoChapter.BoxStatus` 갱신 함수로 볼 근거가 없다.

따라서 이 그룹 파일을 추가했다고 해서 `016e...` unnamed 함수를 무조건 Chapter merge로 연결하지 않는다.

### 34.3 중요한 분석 방법 변경

이제부터 unnamed 함수 추적은 기존처럼 검색 인덱스에 노출되는 Calls IN/OUT만 의존하지 않고:

```
주소 → FUN_00X 그룹 파일
        ↓
Calls OUT
        ↓
상위 함수
        ↓
field offset / Dictionary / OpInfo 접근
```

순서로 직접 확인한다.

특히 다음 주소군을 우선 대상으로 한다.

1. `016e...` — DataCenter/상태 병합 주변
2. `0177...` — DataManager generic Merge/Dictionary 계열
3. `0192...` — Dictionary<int,object> 처리
4. `01a4...` — Dictionary Enumerator
5. `015a...` — Proto* accessor/serializer 인접 영역

### 34.4 현재 결론

이번 FUN 그룹 추가로 **이전에는 이름 없는 함수 본문을 직접 확인하기 어려웠던 부분을 추적할 수 있는 기반이 생겼다.**

그러나 현재 확인된 `FUN_016`의 직접 내용만으로는 BoxStatus 갱신점이 새로 확정되지는 않았다.

다음 단계는 `FUN_016/FUN_017`의 DataCenter 인접 함수와 `FUN_019` Dictionary 처리 함수를 연결하여, `OpInfo.Chapters → ProtoChapter` 병합 객체가 생성되는 지점을 찾는다.


## 34. 2026-09-30 — 신규 FUN_ 그룹핑 TXT 반영

### 34.1 Git 반영 확인

최근 Git 커밋에서 `research/Ghidra_Listing_txt/FUN_008.txt ~ FUN_026.txt` 그룹이 추가된 것을 확인했다.

그룹 기준은 명명되지 않은 함수 `FUN_0xx...`이며, 기존 함수명 Listing과 병행해서 사용한다.

### 34.2 BoxStatus 경로에 대입한 결과

이번에 신규 FUN 그룹을 대상으로 다음 직접 호출 관계를 재검색했다.

```
ProtoChapter.IsBoxReceived @ 015acfe8
ProtoChapter.set_BoxStatus @ 015acf8c
ProtocolGame.SendRequest.GetChapterBoxReward @ 00ddeea8
ChapBoxMono.ClickGetReward @ 00e5705c
DataCenter.ProccessRequestRes @ 016e203c
NetworkCenter.TryHandleResponse @ 015b41e0
```

현재 신규 `FUN_008~FUN_026` 그룹에서 위 Box 전용 함수들을 직접 호출하는 unnamed function은 확인되지 않았다.

따라서 신규 FUN 그룹은 현재 BoxStatus의 직접 setter/caller를 찾는 핵심 증거는 아니며, **명명된 함수 내부에서 호출하는 unnamed helper를 역추적할 때 사용하는 보조 인덱스**로 판단한다.

### 34.3 오히려 중요한 점

`ProtoChapter$$set_BoxStatus` 자체의 Calls IN이 비어 있다는 기존 결과와 일치한다.

즉 현재 구조는 다음 가능성이 높다.

```
Network response
  ↓
ProccessRequestRes
  ↓
protobuf/공통 deserialize 또는 객체 생성
  ↓
ProtoChapter 필드 직접 반영
  ↓
ProtoChapter.BoxStatus(+0x1C)
```

setter를 호출하는 일반적인 C# property 경로가 아니라 **deserialize 과정에서 backing field를 직접 채우는 구조**일 가능성을 우선 검토한다.

### 34.4 다음 추적 포인트

다음은 신규 FUN 파일을 무작정 전체 검색하지 않고, 다음 기준으로 좁힌다.

1. `ProtoChapter`와 함께 사용되는 protobuf/serializer 함수
2. Chapter 객체를 반환하는 Dictionary/List 검색 함수
3. `Id + Status + Progress + BoxStatus`에 대응하는 연속 필드 접근
4. `ProccessRequestRes`에서 호출되는 merge 함수 중 Chapter 계열
5. response snapshot의 field 번호와 `ProtoChapter +0x10/+0x14/+0x18/+0x1C`의 대응 확인

### 34.5 현재 판단

`FUN_*` 그룹 추가로 unnamed function 추적 기반은 확보되었다.

하지만 현재 BoxStatus 문제의 핵심 미확정점은 여전히:

```
response Chapter snapshot
        ↓
ProtoChapter 객체 생성/검색
        ↓
+0x1C BoxStatus 반영
```

이다. 다음 단계는 **Chapter protobuf deserialize/merge 함수 식별**이다.


## 35. 2026-09-30 — OpInfo.Chapters / BoxStatus 직접 write 재검색

### 35.1 OpInfo.Chapters 메모리 위치 재확정

`OpInfo$$get_Chapters @ 015aadec`:

```text
015aadec  ldr x0,[x0,#0xc0]
015aadf0  ret
```

`OpInfo$$set_Chapters @ 015aadf4`:

```text
015aadf4  str x1,[x0,#0xc0]!
015aadf8  b 0x00b07850
```

따라서 `OpInfo +0xC0 = Chapters`는 재확정된다.

### 35.2 BoxStatus setter 직접 callsite 재검색

Git 전체 검색에서 `015acf8c`는 setter 자체 Listing과 보고서만 검색되며, 별도 함수의 `bl 0x015acf8c` callsite는 확인되지 않았다.

따라서 현재 Listing 구조에서는:

```text
set_BoxStatus @ 015acf8c
    ↓ 직접 caller 미확인
상위 deserialize / merge / field population
```

으로 보는 것이 타당하다.

### 35.3 +0x1C 단독 검색의 한계 확인

`str ..., [x?,#0x1c]` 검색 결과에는 여러 unrelated 타입의 필드도 다수 섞인다. 따라서 단순 offset 검색만으로 ProtoChapter write를 특정할 수 없다.

반대로 `ProtoChapter`의 네 필드는:

```text
+0x10 Id
+0x14 Status
+0x18 Progress
+0x1C BoxStatus
```

로 연속 배치되어 있으므로, 네 offset이 같은 함수에서 함께 접근되는지 확인하는 방식이 더 강한 식별 기준이다.

### 35.4 Section StarStatus 비교도 직접 caller 미확보

`ProtoSection$$set_StarStatus @ 015ad948` 역시 단순 field write이고, 현재 검색 인덱스에서 직접 caller가 확인되지 않았다.

따라서 StarStatus setter 호출 구조도 Chapter와 유사하게 serializer/field population 경로일 가능성을 검토한다.

### 35.5 PCAP 입력 파일 상태

Git에는 다음 다른 계정 PCAP JSON이 존재하며 blob SHA도 확인된다.

```text
research/PCAP/로그인부터던전2회이후box오픈_이후장비착용.json
SHA faeb47f64d76158c731c36abb741773e376e46a2
```

다만 현재 GitHub connector에서는 대용량 JSON의 본문이 빈 결과로 반환되어, 이번 단계에서는 packet byte를 다시 직접 분석하지 못했다.

### 35.6 현재 단계 결론

```text
OpInfo +0xC0 = Chapters                 확정
ProtoChapter +0x1C = BoxStatus          확정
boxIndex 5 → UI mask 0x20              확정
set_BoxStatus 직접 caller               미확인
+0x1C 단독 검색                         식별력 부족
Chapter 4-field population 함수         미확인
0x14 response → BoxStatus write         미확정
```

다음은 `FUN_016/FUN_017`에서 DataCenter 인접 함수와 Dictionary 처리 함수를 좁히고, 동시에 `ProtoChapter`와 같은 함수에서 `+0x10/+0x14/+0x18/+0x1C`를 연속 접근하는 패턴을 우선 탐색한다.


## 36. 2026-09-30 — 실제 ProtoBuf.Deserialize → ProccessRequestRes 연결 확정

### 36.1 네트워크 수신부에서 실제 protobuf deserialize 위치 확인

Git Listing의 `TCPTube$$TryRead @ 015b6d54`와 `KCPTube$$TryRead @ 015b08bc`에서 공통으로:

```text
DecryptUnSafe @ 015b0d28
        ↓
DecompressUnSafe @ 015b1204
        ↓
ProtoBuf.Serializer$$Deserialize<object> @ 017cec0c
        ↓
output reference에 객체 저장
```

가 직접 확인된다.

TCPTube의 실제 호출:

```text
015b7094  ldr x1,[x19]
015b7098  mov x0,x21
015b709c  bl  0x017cec0c
015b70a0  mov x1,x0
015b70a4  str x0,[x20]
```

KCPTube도 동일하게 `015b0c10 → 017cec0c → 015b0c1c str x0,[x20]` 구조다.

즉 이전의 단순 추정이 아니라 **암호 해제 후 protobuf 객체가 실제로 생성되어 output reference로 전달되는 지점**이 확보됐다.

### 36.2 Deserialize 결과가 NetworkCenter로 들어가는 경로

`NetworkCenter$$TryHandleResponse @ 015b41e0`에서는 queue에서 해당 response object를 꺼낸 뒤:

```text
015b4430  mov x2,xzr
015b4434  bl  0x016e203c
```

로 `DataCenter$$ProccessRequestRes @ 016e203c`를 호출한다.

기존 분석에서 이 함수의 `x1` 객체 offset이 `Alioth.S1.Common.OpInfo` getter들과 일치하는 것도 확인되어 있다.

따라서 현재 네트워크 경로는 다음처럼 직접 연결된다.

```text
KCP/TCP 수신
   ↓
DecryptUnSafe
   ↓
DecompressUnSafe
   ↓
ProtoBuf.Serializer.Deserialize<object> @ 017cec0c
   ↓
response object
   ↓
NetworkCenter.TryHandleResponse @ 015b41e0
   ↓
DataCenter.ProccessRequestRes @ 016e203c
   ↓
OpInfo 계열 상태 접근
```

### 36.3 중요한 새 추적점 — Deserialize의 Type 인자

`Deserialize<object>`는 이름상 generic object API지만 실제 Listing에서는 호출 직전에 `x1`에 별도 참조를 넣는다.

현재 코드:

```text
015b7074  ldr x8,[x21]
015b7078  adrp x19,0x3367000
015b707c  mov x0,x21
...
015b7090  blr x9
015b7094  ldr x1,[x19]
015b7098  mov x0,x21
015b709c  bl 0x017cec0c
```

따라서 다음 정적 목표는 `0x3367000 + 0xd90` 전역 참조가 가리키는 **실제 deserialize Type 정보**를 식별하는 것이다.

이 값을 확보하면:

```text
Deserialize Type
      ↓
실제 protobuf root 타입
      ↓
OpInfo.Chapters
      ↓
ProtoChapter
```

를 직접 연결할 수 있다.

### 36.4 현재 핵심 결론

이전에는:

```text
암호해제 → protobuf → OpInfo
```

가 간접 추론이었다면, 현재는:

```text
Decrypt/Decompress
 → ProtoBuf.Serializer.Deserialize<object>
 → response object
 → NetworkCenter.TryHandleResponse
 → DataCenter.ProccessRequestRes
```

가 Ghidra Listing으로 직접 연결됐다.

남은 병목은 **Deserialize가 생성한 root object의 실제 Type/Chapter collection population 방식**이다.

다음 단계는 `0x3367000+0xd90` Type 참조와 `Protobuf.Serializer.Deserialize` 내부/주변 helper를 추적한다.


## 37. 2026-09-30 — Deserialize 인자 재검증 및 OpInfo root object 확정

### 37.1 0x3367000+0xD90에 대한 기존 가설 수정

TCPTube/KCPTube의 공통 코드에서 `0x3367000+0xD90 → x1 → ProtoBuf.Serializer.Deserialize<object> @ 017cec0c`가 확인되지만, 이 전역 참조를 Chapter Type 또는 ProtoChapter Type이라고 직접 단정할 근거는 없다.

송신부 `ProtoBuf.Serializer.Serialize<object> @ 017cfc64`에서는 다른 static reference가 사용된다. 따라서 `0x3367000+0xD90`은 현재 `Deserialize` 호출에 사용되는 generic/metadata 관련 static reference 후보로만 기록한다.

### 37.2 실제 response root object는 OpInfo로 연결

`TCPTube.TryRead/KCPTube.TryRead`의 Deserialize 결과는 output reference에 저장된다. 이후 `NetworkCenter.TryHandleResponse @ 015b41e0`에서 같은 response object가 `Request.SetResponse(response)`와 `DataCenter.ProccessRequestRes(response)`에 연속 전달된다.

기존 분석에서 `ProccessRequestRes @ 016e203c`의 x1 객체 offset이 `OpInfo` getter offset과 일치하므로 response root는 OpInfo 계열 객체로 보는 것이 확정 수준이다.

### 37.3 핵심 구조

```text
ProtoBuf Deserialize
        ↓
OpInfo
 ├─ +0x14 opcode
 ├─ +0x30 payload #1
 ├─ +0x34 payload #2
 ├─ +0xC0 Chapters
 └─ +0xC8 Sections
        ↓
DataCenter.ProccessRequestRes
```

따라서 현재 병목은 protobuf root Type 자체가 아니라 `ProccessRequestRes` 내부에서 `OpInfo.Chapters/Sections`를 어떤 response field와 merge하는지 확인하는 것이다.

### 37.4 BoxStatus 추적 우선순위 변경

1. `ProccessRequestRes @ 016e203c`의 Chapter/Section 관련 호출 관계
2. `MergeSectionSnapShot @ 016e5908` 입력 객체의 field access
3. `MergeSections @ 016e55dc`의 Chapters/Sections 접근
4. `ProtoChapter +0x10/+0x14/+0x18/+0x1C` 연속 field population 패턴
5. 직접적인 `+0x1C BoxStatus` write

`set_BoxStatus @ 015acf8c` 직접 caller가 없으므로 protobuf merge가 backing field를 직접 쓰는 가설은 유지한다.

### 37.5 현재 상태

```text
Deserialize → response object       확정
response object → OpInfo 계열       확정
OpInfo +0xC0 = Chapters              확정
ProtoChapter +0x1C = BoxStatus       확정
0x14 = ChapterBoxReward request      확정
chapterId + boxIndex request         확정
0x3367000+0xD90 = Chapter Type       미확정
0x14 response → BoxStatus 변경       미확정
```


## 39. 2026-09-30 — AL 전체 검색에서 Chapter 직접 population 경로 재확인

대형 `AL.txt` 전체를 직접 검색해 `ProtoChapter` 관련 문자열과 4개 연속 offset 패턴을 다시 대조했다.

- `ProtoChapter` 직접 노출은 accessor/constructor 계열에 집중됨
- `set_BoxStatus @ 015acf8c`의 별도 호출자는 현재 Listing에서 확인되지 않음
- `+0x10/+0x14/+0x18/+0x1C`가 함께 등장하는 함수 18개를 추출했지만 `ProtoChapter` 또는 Chapter merge와 직접 연결되는 함수는 확인되지 않음
- 따라서 offset 패턴만으로 Chapter population 함수를 특정할 수 없음을 재확인

현재 가장 가치 있는 추가 자료는 `016e203c / 016e55dc / 016e5908`의 **Ghidra 원본 함수 Listing**이다.

다음 단계는 이 세 함수의 원본 Listing이 추가되면 `OpInfo.Chapters → ProtoChapter`의 실제 대입 instruction부터 확인한다.


## 38. 2026-09-30 — MergeSections / Section snapshot 분리 및 Chapter 경로 재집중

### 38.1 기존 Assembly 기록 재검증

기존 분석 기록에 `DataCenter$$MergeSections @ 016e55dc`의 실제 Assembly가 이미 확보되어 있다.

핵심은:

```text
OpInfo.Sections (+0xC8)
        ↓
MergeSections @ 016e55dc
        ↓
incoming Dictionary<int,object>
        ↓
ProtoSection 계열 객체의 +0x14(Status)
        ├─ Status == 1 → 기존 Section dictionary Remove
        └─ Status != 1 → Section dictionary set_Item
        ↓
Section 객체 +0x78
        ↓
DataManager BaseData / DataCenter +0xE0 collection
```

따라서 `MergeSections`는 **ProtoChapter의 BoxStatus(+0x1C)를 갱신하는 직접 후보가 아니다.**

### 38.2 Section snapshot(+0x90)도 BoxStatus와 분리

`DataCenter$$MergeSectionSnapShot @ 016e5908`에 대해서는 기존 Assembly 분석에서:

```text
DataCenter +0x90
    = Dictionary<int,int>
    key   = SectionID
    value = Section 상태값
```

으로 확인되어 있다.

`DataCenter$$IsSectionClear @ 016e7948`에서 동일 dictionary를 조회하고 `value == 1`이면 Clear로 판정한다.

따라서:

```text
DataCenter +0x90
    ≠ ProtoChapter +0x1C
```

이다.

즉 `MergeSectionSnapShot`을 따라가서 BoxStatus를 찾는 경로는 우선순위를 낮춘다.

### 38.3 현재 Chapter BoxStatus의 실제 미확정 지점

현재 직접 확정된 것은:

```text
ProtoChapter
 +0x10 = Id
 +0x14 = Status
 +0x18 = Progress
 +0x1C = BoxStatus

OpInfo
 +0xC0 = Chapters
 +0xC8 = Sections

0x14 GetChapterBoxReward
 +0x30 = chapterId
 +0x34 = boxIndex

boxIndex 5
 → UI mask 1 << 5
 → 0x20
```

이다.

반면 아직 직접 확인되지 않은 것은:

```text
OpInfo.Chapters(+0xC0)
        ↓
Chapter collection merge
        ↓
ProtoChapter 객체
        ↓
+0x1C BoxStatus write
```

이다.

### 38.4 중요한 분석 방향 변경

`MergeSections`/`MergeSectionSnapShot`을 Chapter merge로 계속 확장하지 않고, 다음 검색 기준을 사용한다.

1. `OpInfo +0xC0`를 읽는 함수
2. 해당 결과를 `Dictionary<int,object>`/`List<object>` 형태로 순회하는 함수
3. 객체에서 `+0x10` Id를 읽어 기존 Chapter를 찾는 코드
4. 같은 함수에서 `+0x14`, `+0x18`, `+0x1C` 중 2개 이상을 함께 접근하는 코드
5. 최종적으로 `str ..., [x?,#0x1C]`가 발생하는 함수

특히 `set_BoxStatus @ 015acf8c`의 Calls IN이 비어 있으므로, **protobuf/merge 과정에서 backing field를 직접 쓰는 경우**를 우선 탐색한다.

### 38.5 현재 결론

이번 단계에서 새로운 BoxStatus write 자체가 확정된 것은 아니다.

다만 다음 두 경로를 명확히 분리했다.

```text
[Section 상태]
OpInfo.Sections(+0xC8)
    → MergeSections
    → ProtoSection / Section state

[Section snapshot 상태]
DataCenter(+0x90)
    → MergeSectionSnapShot
    → SectionID → Clear/상태값

[Chapter Box 상태]
OpInfo.Chapters(+0xC0)
    → 아직 merge 함수 미확정
    → ProtoChapter(+0x1C)
```

따라서 다음 작업의 직접 목표는 **`OpInfo.Chapters(+0xC0)` 소비 지점을 찾아 ProtoChapter population을 확인하는 것**으로 유지한다.

## 40. 2026-09-30 — MergeSections의 응답 merge 경로 재확인

### 40.1 MergeSections는 응답 경로 후보에서 제외하지 않음

`DataCenter$$MergeSections @ 016e55dc`의 Calls IN을 다시 대조했다.

확인된 호출자는:
- `DataCenter$$ProccessRequestRes @ 016e203c`
- `Ali$$GetExcelData<object> @ 01736d60`

즉 `MergeSections`는 초기 Excel 데이터 구성에도 사용되지만 **네트워크 응답 처리(`ProccessRequestRes`)에서도 실제 호출되는 함수**다.

따라서 이전의 “Section collection 처리 성격이 강하므로 BoxStatus 1차 후보에서 하향”이라는 판단은 수정한다. 현재는 `MergeSections`를 **response snapshot merge 후보로 유지**한다.

### 40.2 MergeSectionSnapShot도 DataCenter 상태와 직접 연결

`DataCenter$$MergeSectionSnapShot @ 016e5908`의 Calls IN에는:
- `DataCenter$$ProccessRequestRes @ 016e203c`
- `DataCenter$$get_dataManager @ 00e0277c`

가 확인된다.

특히 `get_dataManager` Listing에서는 `MergeSectionSnapShot`이 실제 Calls IN으로 명시되어 있어, 이 함수가 단순 UI 함수가 아니라 DataCenter/DataManager 상태와 연결된 merge 함수임을 재확인했다.

### 40.3 현재 구조 수정

현재 가장 안전한 경로는:

```text
KCP/TCP response
    ↓
Deserialize<object>
    ↓
OpInfo
    ↓
ProccessRequestRes
    ├─ MergeSections @ 016e55dc
    └─ MergeSectionSnapShot @ 016e5908
            ↓
      Section/Chapter 관련 상태 반영 후보
```

단, 아직 두 함수의 **실제 `ProtoChapter +0x1C` write instruction은 확보되지 않았다.**

### 40.4 다음 정적 분석 목표

`MergeSections`와 `MergeSectionSnapShot` 자체 Listing 본문이 현재 Git 검색 인덱스에 노출되지 않는 상태이므로, 다음은 함수명을 더 검색하는 것이 아니라:

1. 두 함수의 unnamed helper(`FUN_016/FUN_017`) 연결 확인
2. 호출자 `ProccessRequestRes`에서 두 함수 직전의 객체/인자 관계 확인
3. `ProtoSection`의 `StarStatus`와 `ProtoChapter`의 `BoxStatus`가 같은 snapshot에서 함께 갱신되는지 비교
4. Chapter ID가 Section snapshot에서 어떤 collection/key로 전달되는지 확인

순서로 좁힌다.

현재까지의 핵심 미확정점은 그대로다.

```text
response Chapter snapshot
        ↓
ProtoChapter 객체
        ↓
+0x1C BoxStatus
```

이 마지막 대입 지점을 직접 확보하는 것이 다음 목표다.
## 40. 2026-09-30 — DataCenter Merge 함수 Listing 부재 재확인 및 추적 기준 보강

### 40.1 Git Listing 검색 결과

현재 Git의 함수별 Listing/검색 인덱스에서 다음 함수의 실제 본문 Listing은 확보되지 않았다.

- DataCenter.ProccessRequestRes @ 016e203c
- DataCenter.MergeSections @ 016e55dc
- DataCenter.MergeSectionSnapShot @ 016e5908

검색 결과는 이 함수들을 Calls IN으로 참조하는 다른 Listing 또는 보고서만 반환한다.

따라서 현재 단계에서 이 함수 내부가 ProtoChapter +0x1C를 직접 쓰거나, Chapters를 순회한다고 단정하지 않는다.

### 40.2 새로 확인한 직접 단서

`Ali.get_dataManager @ 00e0277c`의 Calls IN에 다음이 함께 존재한다.

```text
DataCenter.ProccessRequestRes @ 016e203c
DataCenter.MergeSectionSnapShot @ 016e5908
DataCenter.MergeItem @ 016e4700
DataCenter.MergeEquip @ 016e4348
DataCenter.MergeWeapon @ 016e5be4
DataCenter.UpdateHeroInfo @ 016e4ba4
```

이는 이 함수들이 동일한 DataManager singleton 접근 계층과 연결됨을 보여주지만, 서로 직접 호출한다는 의미는 아니다.

### 40.3 ProccessRequestRes의 상태 객체 접근 범위

Git의 `US.txt` Calls IN 검색에서 `DataCenter.ProccessRequestRes @ 016e203c`가 `UserInfo` getter 계열에도 호출자로 기록되어 있음이 확인된다.

예:

```text
UserInfo.get_Level @ 00dd1ba0
UserInfo.get_Exp   @ 00dd1ca4
```

즉 `ProccessRequestRes`는 Request 완료 통지만 하는 함수가 아니라, 여러 typed game-state 객체의 값을 참조하는 상태 처리 함수라는 기존 판단을 보강한다.

단, 이것만으로 Chapter response가 해당 getter를 통해 갱신된다고 해석하지 않는다.

### 40.4 Chapter 추적 기준 강화

현재 가장 식별력이 높은 기준은 단일 `+0x1C` 검색이 아니다.

우선순위를 다음처럼 유지한다.

```text
ProtoChapter
 +0x10 Id
 +0x14 Status
 +0x18 Progress
 +0x1C BoxStatus
```

위 네 필드가 동일 함수에서 함께 접근되는 경우를 Chapter population 후보로 우선한다.

그 다음:

```text
Chapters collection
 → Chapter Id 검색
 → ProtoChapter object
 → +0x10/+0x14/+0x18/+0x1C
```

순서를 확인한다.

### 40.5 현재 정적 분석 한계와 다음 단계

현재 Git export에 `016e203c/016e55dc/016e5908` 본문이 없으므로, 더 이상 동일 검색을 반복하지 않는다.

다음 우선순위는:

1. 해당 주소의 Ghidra 원본 Listing이 Git에 추가되는지 확인
2. `FUN_*` 그룹에서 해당 주소 주변 unnamed helper가 새로 추가되는지 확인
3. runtime에서 `ProtoChapter.get_BoxStatus @ 015acf84`를 기준으로 Chapter 객체 주소와 BoxStatus 값을 관찰
4. boxIndex 5 오픈 전후 값 변화가 확인되면 `0x00 → 0x20` 가설을 실제 값으로 검증
## 41. 2026-09-30 — 0930-8 재개: Chapter getter/setter 직접 caller 부재 재확인

### 41.1 OpInfo.Chapters accessor도 직접 caller가 잡히지 않음

Git의 개별 Listing을 다시 검색한 결과:

~~~text
OpInfo$$get_Chapters @ 015aadec
OpInfo$$set_Chapters @ 015aadf4
~~~

두 함수 모두 실제 field 접근은 확인되지만, get_Chapters의 Calls IN은 비어 있고 set_Chapters 역시 현재 인덱스에서 직접 caller가 확인되지 않는다.

따라서 현재 Listing export만으로:

~~~text
ProccessRequestRes
 → OpInfo.get_Chapters()
 → Chapter collection
~~~

처럼 일반 C# property accessor를 거치는 경로를 확정할 수 없다.

### 41.2 ProtoChapter 4개 accessor도 동일한 패턴

~~~text
get_Id        @ 015acf54
get_Status    @ 015acf64
get_Progress  @ 015acf74
get_BoxStatus @ 015acf84

set_Id        @ 015acf5c
set_Status    @ 015acf6c
set_Progress  @ 015acf7c
set_BoxStatus @ 015acf8c
~~~

현재 검색 인덱스에서는 이 accessor들의 직접 caller가 확인되지 않는다.

따라서 현재까지의 증거는 **Chapter 객체의 네 필드가 property setter를 통해 채워진다고 볼 수 없는 상태**다.

### 41.3 Deserialize 경로와 결합하면 의미가 커짐

이미 다음 경로는 직접 Listing으로 확정되어 있다.

~~~text
KCP/TCP
 ↓
DecryptUnSafe
 ↓
DecompressUnSafe
 ↓
ProtoBuf.Serializer.Deserialize<object> @ 017cec0c
 ↓
response object
 ↓
NetworkCenter.TryHandleResponse @ 015b41e0
 ↓
DataCenter.ProccessRequestRes @ 016e203c
~~~

따라서 현재 가장 타당한 추적 방향은:

~~~text
protobuf Deserialize
 ↓
ProtoBuf 내부 reflection / generated metadata
 ↓
ProtoChapter 객체 생성 및 field population
 ↓
OpInfo.Chapters
 ↓
ProccessRequestRes
~~~

이다.

단, **reflection/direct-field population이라고 아직 확정하지 않는다.** 현재는 setter caller 부재와 Deserialize 구조를 설명하는 유력 가설이다.

### 41.4 중요한 분석 전환

이제 다음 단계에서는 set_BoxStatus를 계속 검색하지 않는다.

대신 다음 3개를 우선 확인한다.

1. ProtoBuf.Serializer.Deserialize<object> @ 017cec0c 내부/Calls OUT의 타입 생성 helper
2. ProtoChapter와 연결되는 protobuf metadata / field-number 처리 함수
3. ProccessRequestRes @ 016e203c 직전 response object의 concrete type을 결정하는 코드

특히 목표는 다음 관계를 직접 확보하는 것이다.

~~~text
protobuf field #N
      ↓
ProtoChapter backing field +0x1C
~~~

### 41.5 BoxStatus 현재 확정/미확정

~~~text
ProtoChapter +0x1C = BoxStatus       확정
IsBoxReceived(mask)                  확정
mask = 1 << UIData.data              확정
boxIndex 5 → mask 0x20              확정
0x14 request chapterId/boxIndex      확정
0x14 response Chapter snapshot       확정

protobuf field 4 = BoxStatus         미확정
0x14 response → +0x1C write          미확정
deserialize → ProtoChapter field map 미확정
~~~

이번 재개에서 새로 확보된 것은 **Chapter 관련 accessor들이 전반적으로 직접 caller를 잃고 있다는 패턴**이다. 이는 다음 분석을 protobuf/deserialize metadata 쪽으로 이동시키는 근거가 된다.

### 41.6 다음 작업

~~~text
017cec0c Deserialize
    ↓
Calls OUT / helper
    ↓
ProtoChapter metadata
    ↓
field #1/#2/#3/#4
    ↓
+0x10/+0x14/+0x18/+0x1C
~~~

이 경로를 우선 추적한다.


## 41. 2026-09-30 — Chapter response 소비 경로 재평가

이번 재검색에서 `OpInfo$$get_Chapters @ 015aadec`의 Calls IN은 여전히 비어 있고, 현재 확보된 `ProccessRequestRes` Assembly 구간에서도 `OpInfo +0xC0` 접근이 확인되지 않았다.

반면 `BattleMapMono$$InitChapters @ 00e4e080`는 Chapter 데이터를 소비하는 UI 진입점으로 반복 확인된다. 다만 해당 함수의 독립 본문은 현재 Git export에서 확보되지 않아 `get_Chapters` 직접 호출 여부는 미확정이다.

따라서 현재 Chapter Box 경로는 다음처럼 분리한다.

```text
0x14 response
   ↓
Deserialize → OpInfo
   ├─ Items/Weapons/Equip/Sections
   │      ↓
   │  ProccessRequestRes merge 경로
   │
   └─ Chapters +0xC0
          ↓
      Chapter 소비/저장 경로 미확정
          ↓
      BattleMapMono.InitChapters
          ↓
      ProtoChapter
          ↓
      BoxStatus +0x1C
```

추가로 `ProtoChapter` accessor 전체를 재검색했지만 serializer/`MergeFrom`/`ParseFrom` 형태의 명시적 함수는 현재 Git Listing에서 발견되지 않았다. 따라서 protobuf field tag를 C# property와 직접 매핑하는 방식은 아직 증명되지 않았다.

### 현재 결론

```text
OpInfo +0xC0 = Chapters                 확정
ProtoChapter +0x1C = BoxStatus          확정
BattleMapMono.InitChapters = Chapter 소비 지점 유력
ProccessRequestRes → Chapters 직접 merge 미확인
0x14 response → ProtoChapter +0x1C     미확정
```

**다음은 `BattleMapMono.LayChapterItem @ 00e4f918`의 Chapter 객체 입력 경로와 `InitChapters @ 00e4e080` 주변 unnamed helper를 `FUN_00E*` 기준으로 좁힌다.**

## 30. 2026-09-30 0930-8 후속 — protobuf tag와 ProtoChapter offset을 분리해서 추적

### 30.1 ProtoChapter 메모리 field는 확정 상태 유지

Id +0x10 / Status +0x14 / Progress +0x18 / BoxStatus +0x1C

각 accessor가 직접 해당 offset을 읽고/쓴다. 따라서 메모리 layout 자체에는 추가 의문이 없다.

### 30.2 ProtoBuf.Meta 계열 코드 추가 확인

`FUN_022.txt`에서 `ProtoBuf.Meta.MetaType$$GetFieldBoolean @ 021fdf7c`가 `FUN_021fe00c`를 호출하는 구조를 확인했다.

동일 Listing 영역에는 field index를 증가시키면서 객체 내부 offset에 저장하는 반복 패턴도 존재한다.

다만 현재 확보된 Listing만으로 이 반복 코드를 ProtoChapter serializer/deserializer라고 직접 명명할 근거는 없다.

### 30.3 protobuf tag와 C# 메모리 offset은 동일하다고 가정하지 않음

실제 0x14 response Chapter snapshot은 field 1=20000100, field 3=12, field 4=3, field 9={1,15}, field10={1,15}, field11=1이다.

요청의 boxIndex=5에 대해 UI 검사 mask는 1 << 5 = 0x20이다.

따라서 response field 4=3을 ProtoChapter.BoxStatus라고 단순 대응시키는 것은 현재 증거와 맞지 않는다.

즉 protobuf field #4와 C# memory field +0x1C를 동일시하지 않는다.

### 30.4 0x14 response 이후 갱신 시점

현재 순서는 283 C→S opcode 0x14, 285 S→C opcode 0x14 + Chapter snapshot, 287 C→S, 289 S→C, 294 C→S, 296 S→C이다.

285에 Chapter snapshot이 존재하는 것은 확정이나 BoxStatus가 어느 response에서 갱신되어 IsBoxReceived 결과가 바뀌는지는 미확정이다. frame 296은 유효 protobuf 복호화 재검증 대상이다.

### 30.5 MergeSectionSnapShot 방향 재확인

`DataCenter.ProccessRequestRes @ 016e203c` → `DataCenter.MergeSectionSnapShot @ 016e5908` 연결은 확인되지만, 현재 Listing 검색 결과만으로 MergeSectionSnapShot이 ProtoChapter +0x1C를 쓰는 직접 증거는 없다.

### 30.6 다음 분석 목표

1. `ProccessRequestRes @ 016e203c` / `MergeSectionSnapShot @ 016e5908` 실제 Listing 확보
2. 해당 함수 및 helper에서 `str w?,[x?,#0x1c]` 확인
3. 같은 함수에서 +0x10/+0x14/+0x18/+0x1C가 같은 객체에 함께 접근되는지 확인

네 offset이 한 함수에서 같은 객체에 연속적으로 접근되면 ProtoChapter merge 경로일 가능성이 크게 올라간다.

### 30.7 현재 결론

ProtoChapter +0x1C = BoxStatus: 확정
0x14 request chapterId/boxIndex: 확정
0x14 response Chapter snapshot: 확정
boxIndex 5 → UI mask 0x20: 확정
protobuf field 4 = BoxStatus: 미확정
0x14 response → +0x1C write: 미확정
MergeSectionSnapShot → BoxStatus: 미확정
285에서 즉시 상태 갱신: 미확정

이번 단계에서는 잘못된 field 4 = BoxStatus 단순 매핑을 제거하고, protobuf tag → deserializer/merge → ProtoChapter memory offset의 3단계 연결을 직접 증명하는 방향으로 추적을 고정한다.

## 31. 2026-09-30 — ProccessRequestRes 실제 병합 구간 재확인 및 Chapter 경로 분리

### 31.1 ProccessRequestRes에서 직접 확인된 OpInfo 접근

기존 보고서에 보존된 Assembly 구간을 다시 검증했다.

```text
016e29dc  ldr x0,[x20,#0x40]
016e29e0  ldr x1,[x26,#0xa0]
016e29e4  bl  0x016e414c        ; MergeWeapon

016e29e8  ldr x0,[x20,#0x38]
016e29ec  ldr x1,[x26,#0xa8]
016e29f0  bl  0x016e4348        ; MergeEquip

016e29f4  ldr x1,[x26,#0x98]
016e29f8  mov x0,x20
016e29fc  bl  0x016e4700        ; MergeItem

016e2a00  mov x0,x20
016e2a04  mov x1,x26
016e2a08  bl  0x016e4ba4        ; UpdateHeroInfo

016e2a1c  ldr x1,[x20,#0x50]
016e2a20  ldr x2,[x26,#0xc8]
016e2a24  mov x0,x20
016e2a28  bl  0x016e55dc        ; MergeSections
```

여기서 `x26`은 OpInfo로 확인되며, +0x98 Items / +0xA0 Weapons / +0xA8 Equipments / +0xC8 Sections가 실제 merge 입력으로 사용된다.

### 31.2 중요한 음성 증거: Chapters(+0xC0)는 같은 구간에서 직접 읽히지 않음

위 확보 구간에는 `ldr ... [x26,#0xc0]`가 없다. 또한 개별 Listing 검색에서 `OpInfo$$get_Chapters @ 015aadec`의 Calls IN도 비어 있다.

따라서 현재 증거로는:

```text
ProccessRequestRes
  → OpInfo +0xC8 Sections → MergeSections      확인
  → OpInfo +0xC0 Chapters → 직접 merge        미확인
```

으로 분리해야 한다.

### 31.3 MergeSectionSnapShot도 ProtoChapter 경로와 분리

확인된 호출:

```text
016e3804  ldr x1,[x20,#0x90]
016e3808  ldr x2,[x28]
016e380c  mov x0,x20
016e3810  bl  0x016e5908        ; MergeSectionSnapShot
```

이 함수는 `DataCenter +0x90`의 `Dictionary<int,int>` 상태를 갱신하며, `IsSectionClear`에서 value == 1 여부가 사용된다.

따라서 현재 근거만으로 `MergeSectionSnapShot → ProtoChapter +0x1C(BoxStatus)`라고 연결하지 않는다.

### 31.4 StarStatus 비교 대상 정정

기존 단계에서 `ProtoChapter.set_StarStatus @ 015ad948`를 비교 대상으로 언급한 부분은 주소/타입 기준으로 정정한다.

`015ad948`는 실제로:

```text
Alioth.S1.Common.ProtoSection$$set_StarStatus
015ad948  str w1,[x0,#0x1c]
```

이다.

즉 `+0x1C`라는 동일 offset이 `ProtoSection.StarStatus`에도 존재할 수 있으므로, 단순 `+0x1C write` 검색만으로 Chapter BoxStatus를 식별하면 오인할 수 있다.

### 31.5 현재 검색 기준 강화

Chapter BoxStatus 후보는 다음 4개 조건을 함께 본다.

1. 객체가 `ProtoChapter`와 연결되는 증거
2. +0x10 / +0x14 / +0x18 / +0x1C 중 복수 필드 접근
3. Chapters collection 또는 Chapter ID와 연결
4. 0x14 response 또는 Chapter UI 경로와 연결

따라서 단순 `str w?,[x?,#0x1c]` 단독 검색은 보조 증거로만 사용한다.

### 31.6 다음 추적 지점

현재 가장 가치 있는 미확정 연결은:

```text
0x14 response
   ↓
OpInfo +0xC0 Chapters
   ↓
ProtoChapter 객체 생성/병합
   ↓
ProtoChapter +0x1C BoxStatus
```

개별 함수 Listing이 없는 `016e203c / 016e5908`를 동일 방식으로 반복 검색하지 않고, 다음은 `ProtoBuf.Serializer.Deserialize<object> @ 017cec0c`와 protobuf metadata 계열에서 `ProtoChapter`의 field population 흔적을 우선 찾는다.

### 31.7 현재 결론

```text
ProtoChapter +0x1C = BoxStatus             확정
ProccessRequestRes → OpInfo +0xC8 Sections 확인
ProccessRequestRes → OpInfo +0xC0 Chapters 직접 접근 미확인
MergeSectionSnapShot → DataCenter +0x90     확인
MergeSectionSnapShot → ProtoChapter +0x1C   미확인
0x14 response → BoxStatus 갱신             미확정
```


## 42. 2026-09-30 — Deserialize 이후 response object 전달점 재확인

`NetworkCenter$$TryHandleResponse @ 015b41e0`에서 response object가 `sp+0x48`에 유지되고 `015b4434 bl 0x016e203c`로 `DataCenter.ProccessRequestRes`에 직접 전달된다. `Request$$SetResponse @ 015b461c`도 같은 response object를 callback 또는 `Request$$set_Res`로 전달한다.

따라서 현재 네트워크 계층에서는 **Deserialize 결과 object → Request/Callback → TryHandleResponse → ProccessRequestRes** 연결이 확정된다.

`ProtoBuf.Meta.MetaType$$GetFieldBoolean @ 021fdf7c` → `FUN_021fe00c`라는 generic metadata 경로도 확인했지만, 이를 `ProtoChapter` 특정 field와 연결하는 타입별 metadata 기록은 현재 Git Listing에 없다. 따라서 generic metadata를 ProtoChapter deserializer라고 명명하지 않는다.

현재 확정 경계:

```text
KCP/TCP
 ↓
Deserialize<object> @ 017cec0c
 ↓
response object
 ↓
Request.SetResponse / callback
 ↓
NetworkCenter.TryHandleResponse @ 015b41e0
 ↓
DataCenter.ProccessRequestRes @ 016e203c
```

그 다음 `ProccessRequestRes → OpInfo.Chapters(+0xC0) → ProtoChapter(+0x1C)`는 아직 직접 Listing으로 연결되지 않았다.

다음 우선순위는 generic FUN_022 검색 확대보다 `016e203c / 016e55dc / 016e5908` 주변 unnamed helper와 runtime `ProtoChapter$$set_BoxStatus @ 015acf8c` 관찰이다. runtime hook으로 setter 호출 여부 또는 backing-field 직접 write 여부를 판별할 수 있다.

현재 상태: ProtoChapter +0x1C=BoxStatus **확정** / 신규 3개 PCAP f4 bitmask **확정** / f7=0-based **확정** / Deserialize→ProccessRequestRes **확정** / OpInfo +0xC0=Chapters **확정** / ProccessRequestRes→Chapters **미확정** / 0x14 response→+0x1C **미확정**.

## 43. 2026-10-01 — FUN_* / +0x1C 역추적 재검증 및 최신 PCAP 결과 반영

### 43.1 Ghidra unnamed 함수 검색 재검증

FUN_016.txt를 직접 확인하여 016e... 영역의 unnamed 함수를 재검토했다.

확인된 FUN_016e0008 @ 016e0008은 DataManager.TryGetAll, Dictionary<int,object>, WeaponInfo, HeroInfo, ProtoFashion 등을 처리하는 Excel/DataManager 초기화 계열 함수다. 따라서 016e0008은 Chapter/BoxStatus merge 함수가 아니다.

FUN_013.txt의 0131200c @ 0131200c에서는 동일 객체에 +0x10/+0x14/+0x18/+0x1C를 연속 기록하는 실제 예가 발견됐다. 그러나 객체 생성자가 ProtoHeroSnapshot이므로 ProtoChapter와 무관하다. 따라서 단순히 네 offset이 함께 등장하는 것만으로 Chapter merge를 판별할 수 없다는 점을 확인했다.

### 43.2 ProtoChapter setter 직접 caller 검색 결과

015acf8c 검색 결과는 ProtoChapter$$set_BoxStatus 자신의 Listing과 기존 보고서만 반환한다. set_Id / set_Status / set_Progress / set_BoxStatus 모두 현재 Git export에서는 직접 Calls IN이 잡히지 않는다.

따라서 현재 정적 자료만으로 serializer가 setter를 호출하는 경로는 확보되지 않았다.

### 43.3 InitChapters / LayChapterItem Listing 한계 재확인

BattleMapMono$$InitChapters @ 00e4e080 및 BattleMapMono$$LayChapterItem @ 00e4f918는 여러 함수의 Calls IN에서 반복 확인된다. ProtoChapter$$IsBoxReceived @ 015acfe8의 Calls IN에도 ChapBoxMono$$LayBoxItem, BattleMapMono$$LayChapterItem, BattleSectionMono$$SetStageBoxAndBar가 확인된다.

따라서 Chapter Box UI 소비 경로는 확정적이지만, 두 BattleMap 함수 자체의 독립 Assembly Listing은 현재 Git export에서 확보되지 않는다.

### 43.4 최신 3개 PCAP 실험 결과와 정적 분석 교차검증

새 세션 모두 chapterId=20000000이며 다음 상태가 확인됐다.

| 실험 | 0x14 f7 | response f4 |
|---|---:|---:|
| 1번째 Box 오픈 | 0(기본값 생략) | 1 |
| 3번째 Box 오픈 | 2 | 5 |
| 2번째 Box 오픈 | 1 | 7 |

상태 변화는 1번 오픈 → 001b=1, 1+3번 오픈 → 101b=5, 1+2+3번 오픈 → 111b=7이다.

따라서 f4는 누적 개수가 아니라 BoxStatus bitmask이며 boxIndex 0→0x01, 1→0x02, 2→0x04가 실제 패킷 변화로 검증된다. 이는 IsBoxReceived의 BoxStatus & mask 및 mask=1<<boxIndex와 일치한다.

### 43.5 현재 핵심 결론

확정: ProtoChapter +0x1C=BoxStatus, IsBoxReceived=(BoxStatus & mask)!=0, mask=1<<boxIndex, 0x14 f7=0-based boxIndex, 0x14 response f4=BoxStatus bitmask, 실제 상태 변화 1→5→7.

미확정: 0x14 response object에서 ProtoChapter +0x1C로 이어지는 정확한 write 지점, protobuf field/tag→backing field 매핑, ProccessRequestRes→OpInfo.Chapters(+0xC0) 직접 연결, Chapter population을 담당하는 concrete serializer/merge helper.

### 43.6 다음 우선순위

정적 검색은 동일 패턴 반복을 중단하고 runtime의 ProtoChapter$$set_BoxStatus @ 015acf8c / get_BoxStatus @ 015acf84 호출 및 object/value 관찰을 우선한다. setter가 호출되지 않으면 backing field 직접 write 가능성을 확인한다. 정적 측면에서는 protobuf metadata의 ProtoChapter Type 결정 지점, Deserialize<object> @ 017cec0c 이후 concrete type helper, OpInfo.Chapters(+0xC0)를 직접 참조하는 unnamed helper를 추적한다.


## 44. 2026-10-01 — protobuf metadata helper 재검증

### 44.1 Deserialize 경계
`TCPTube$$TryRead` 및 `KCPTube$$TryRead`에서 공통으로 `ProtoBuf.Serializer$$Deserialize<object> @ 017cec0c`를 호출한다. 현재 Listing에서 이 호출 이후 concrete `ProtoChapter`를 결정하는 직접 호출은 확인되지 않았다.

### 44.2 MetaType helper 판별
`ProtoBuf.Meta.MetaType$$GetFieldBoolean @ 021fdf7c`가 `FUN_021fe00c @ 021fe00c`로 이어진다. 해당 helper는 `+0x40`의 값을 비교한 뒤 `FUN_00b07998` 결과의 byte를 기록하는 짧은 타입/메타 비교 계열 helper이며, 현재 증거만으로 ProtoChapter field mapping/deserializer write helper라고 볼 근거가 없다.

따라서 기존의 MetaType 계열이 존재한다는 사실과 ProtoChapter를 실제로 채운다는 주장은 분리한다.

### 44.3 현재 가장 유효한 추적점
정적 Listing만으로는 `Deserialize<object> → ProtoChapter`의 구체적 mapping을 아직 연결하지 못했다. 다음은 `ProccessRequestRes @ 016e203c`에서 `OpInfo.Chapters +0xC0`를 사용하는 unnamed helper 및 Chapter collection 객체의 실제 생성/대입을 찾는 방향이 우선이다.

BoxStatus 의미는 이미 PCAP 1→5→7과 `IsBoxReceived`의 bitmask 로직으로 확정되어 있으므로, 이후 분석 목표는 의미 재확인이 아니라 실제 메모리 write 경로 확보다.


## 45. 2026-10-01 — OpInfo.Chapters 사용처 재검색 및 Chapter UI 경로 정리

### 45.1 Chapters accessor 직접 caller는 여전히 미확보

Git Listing에서 다음을 재검색했다.

```text
OpInfo$$get_Chapters @ 015aadec
OpInfo$$set_Chapters @ 015aadf4
```

`get_Chapters`는 Calls IN이 비어 있고, `set_Chapters`도 현재 인덱스에서 직접 caller가 확인되지 않는다.

### 45.2 Chapter 소비 경로 재확인

`BattleMapMono$$InitChapters @ 00e4e080`는 Chapter 관련 UI 초기화 진입점으로 반복 확인된다.

`ProtoChapter$$IsBoxReceived @ 015acfe8`의 Calls IN에는:

```text
ChapBoxMono$$LayBoxItem
BattleMapMono$$LayChapterItem
BattleSectionMono$$SetStageBoxAndBar
```

가 확인된다.

따라서 Chapter 객체가 UI로 전달된 뒤 `IsBoxReceived`가 BoxStatus를 소비하는 경로는 유지한다. 단, InitChapters/LayChapterItem의 독립 Assembly 본문이 현재 Git export에 없어 `get_Chapters` 직접 호출 여부는 미확정이다.

### 45.3 Chapter 생성/채움 경로

`ProtoChapter$$.ctor @ 015acff8`의 Calls IN은 없으며 생성자는 `System.Object$$.ctor`만 호출한다.

현재 Git 검색에서도 `ProtoChapter`와 `Serializer/Deserialize/MergeFrom/ParseFrom`를 직접 연결하는 concrete 함수는 확인되지 않았다.

따라서 현재는 다음 셋 중 어느 방식인지 미확정이다.

```text
A. protobuf reflection → backing field 직접 기록
B. generic object population helper
C. 별도 merge/cache 함수가 ProtoChapter 생성 후 기록
```

### 45.4 현재 정적 경계

```text
Deserialize<object> @ 017cec0c
        ↓
response object
        ↓
TryHandleResponse @ 015b41e0
        ↓
ProccessRequestRes @ 016e203c
        ├─ +0x98 Items       확인
        ├─ +0xa0 Weapons     확인
        ├─ +0xa8 Equipments  확인
        ├─ +0xc8 Sections    확인
        └─ +0xc0 Chapters    미확인
```

따라서 남은 핵심은 `Chapters` 자체가 아니라 **Chapters를 실제로 생성/저장/소비하는 concrete helper**다.

### 45.5 다음 우선순위

1. `BattleMapMono$$InitChapters @ 00e4e080` 주변 `FUN_00E*` helper
2. `BattleMapMono$$LayChapterItem @ 00e4f918` 주변 `FUN_00E*` helper
3. `OpInfo +0xC0`와 함께 등장하는 unnamed 함수
4. runtime `ProtoChapter$$set_BoxStatus @ 015acf8c` / `get_BoxStatus @ 015acf84`
5. setter가 호출되지 않으면 `ProtoChapter +0x1C` 직접 write 추적

### 45.6 현재 상태

```text
BoxStatus 의미/bitmask              확정
f7 = 0-based boxIndex              확정
OpInfo +0xC0 = Chapters             확정
ProtoChapter +0x1C = BoxStatus      확정
Deserialize → ProccessRequestRes    확정
ProccessRequestRes → Chapters      미확정
Chapter population helper          미확정
0x14 response → +0x1C write        미확정
```


## 46. 2026-10-01 — protobuf-net 직접 backing-field write 전제로 추적 전략 전환

### 46.1 MetaType 경로 제외

`FUN_021fe00c @ 021fe00c`를 직접 디스어셈블리로 재검증했다.

```asm
021fe00c  ldr x8,[x9,#0x40]
021fe010  ldr x9,[x1,#0x40]
021fe014  cmp x8,x9
021fe018  b.ne 0x021fe044
021fe01c  bl 0x00b07998
021fe020  ldrb w8,[x0]
021fe024  strb w8,[x19]
```

이 함수는 두 객체의 `+0x40` 값을 비교한 뒤 결과의 byte를 복사하는 generic helper다.

호출 중간의 `FUN_0220b8e8`도:

```asm
ldr x1,[x8]
b 0x021fe00c
```

형태의 trampoline으로 확인됐다.

따라서:

```text
MetaType$$GetFieldBoolean
 → FUN_0220b8e8
 → FUN_021fe00c
```

경로를 `ProtoChapter` 또는 `BoxStatus` field mapping으로 해석하지 않는다.

### 46.2 set_BoxStatus 호출자 추적 중단

`ProtoChapter$$set_BoxStatus @ 015acf8c`는:

```asm
015acf8c  str w1,[x0,#0x1c]
015acf90  ret
```

뿐이다.

현재 Calls IN이 비어 있는 것과 결합하면, setter 호출자 검색은 더 이상 핵심 추적점으로 사용하지 않는다.

다만 **실제 ProtoChapter +0x1C 직접 write가 확인된 것은 아니다.**

현재의 안전한 표현은:

```text
setter 호출 경로             미확인
protobuf-net direct-field write 가능성 강함
실제 ProtoChapter +0x1C store 위치 미확정
```

이다.

### 46.3 추적 모델 변경

기존:

```text
Deserialize
 → set_BoxStatus
 → ProtoChapter +0x1C
```

에서 다음으로 변경한다.

```text
Deserialize<object>
        ↓
protobuf-net field metadata
        ↓
concrete object allocation
        ↓
field offset 결정
        ↓
direct store
        ↓
ProtoChapter +0x1C
```

이때 가장 중요한 식별자는 단순 `+0x1C`가 아니라 **store 대상 객체가 ProtoChapter인지** 여부다.

### 46.4 다음 정적 추적 기준

다음 순서로 검색한다.

1. protobuf-net deserializer에서 primitive/int field를 object offset에 기록하는 generic write helper
2. field metadata가 실제 object offset을 결정하는 지점
3. 해당 metadata가 `ProtoChapter` 타입과 연결되는 지점
4. `str w?,[x?,#0x1c]` 주변에서 `+0x10/+0x14/+0x18` 또는 Chapter ID 처리가 함께 존재하는지 확인
5. `OpInfo.Chapters(+0xc0)`와 concrete Chapter collection 연결
6. 정적 연결이 막히면 runtime에서 `ProtoChapter` 객체의 `+0x1c` 값 변화를 관찰

### 46.5 현재 상태

```text
MetaType generic helper → ProtoChapter     제외
set_BoxStatus caller 추적                 중단
ProtoChapter +0x1C = BoxStatus             확정
f4 = BoxStatus bitmask                     확정
f7 = 0-based boxIndex                      확정
Deserialize → ProccessRequestRes           확정
ProccessRequestRes → Chapters              미확정
실제 direct +0x1C write 위치               미확정
```


## 47. 2026-10-01 — runtime 추적용 justice_hook v4.8 추가

정적 분석에서 protobuf-net의 direct backing-field write 가능성이 높아졌으므로 Git의 `research/justice_hook.js`에 runtime 관찰점을 추가했다.

추가 hook:

```text
ProtoChapter.get_BoxStatus()
ProtoChapter.set_BoxStatus(Int32)
```

출력에는 object 주소와 `+0x1C`의 실제 값을 함께 기록한다.

목적은 setter가 실제 deserialize 과정에서 호출되는지를 다시 주장하는 것이 아니라, 다음을 구분하는 것이다.

```text
A. deserialize 과정에서 setter 진입
B. setter는 전혀 호출되지 않고 다른 코드에서 +0x1C 직접 기록
C. deserialize 직후 이미 +0x1C가 채워진 ProtoChapter 객체가 전달됨
```

특히 `set_BoxStatus` hook의 존재 자체는 direct write 증거가 아니다. setter가 호출되지 않는 경우가 핵심 관찰 결과다.

Git 변경:
- `research/justice_hook.js`
- v4.8 runtime BoxStatus 관찰 hook 추가
- commit `96d015fc66c111cdbe38c4f46659b803a9741ef1`

### 47.1 정적 분석 결과와 runtime 분석의 역할 분리

현재 정적 분석:

```text
ProtoChapter +0x1C = BoxStatus             확정
MetaType FUN_021fe00c = generic helper     확정
set_BoxStatus direct caller                추적 중단
실제 direct +0x1C write 위치              미확정
```

runtime 분석의 목표:

```text
0x14 response 수신
 ↓
ProtoChapter 객체 생성/채움
 ↓
BoxStatus 값 1/5/7 관찰
 ↓
setter 호출 여부 확인
 ↓
객체 주소/값을 이용한 후속 메모리 추적
```

따라서 다음 실행에서는 Box 1/3/2 순서의 기존 실험과 동일한 상태 변화를 재현하면 가장 유용하다.



## 48. 2026-10-01 — runtime response-path 관찰 hook 추가

### 48.1 목적

기존 ProtoChapter.get_BoxStatus/set_BoxStatus hook에서 실제 호출이 관찰되지 않았고, 로그인 이후 일반 게임 활동에서 HTTP 관련 로그도 제한적으로 발생했다. 따라서 BoxStatus 자체를 계속 추적하기 전에 **응답 처리 경로가 실제 런타임에서 실행되는지** 확인하도록 justice_hook.js에 다음 두 관찰점을 추가했다.

NetworkCenter.TryHandleResponse
DataCenter.ProccessRequestRes

### 48.2 정적 근거

NetworkCenter$$TryHandleResponse @ 015b41e0 Listing에서:

015b442c  ldr x1,[sp,#0x48]
015b4430  mov x2,xzr
015b4434  bl  0x016e203c

가 확인된다. 즉 TryHandleResponse 내부의 response object가 DataCenter.ProccessRequestRes의 arg[1]로 전달된다.

따라서 runtime에서는:

TryHandleResponse 호출
        ↓
ProccessRequestRes 호출
        ↓
arg[1] = 실제 response object

를 직접 관찰한다.

### 48.3 justice_hook v4.9 변경

research/justice_hook.js에 추가:

- NetworkCenter.TryHandleResponse 이름 기반 runtime hook
- DataCenter.ProccessRequestRes 이름 기반 runtime hook
- method overload의 실제 parameter type 출력
- TryHandleResponse의 this 객체 주소/타입 출력
- ProccessRequestRes의 this, arg[1] response, arg[2] 관찰
- 기존 ProtoChapter BoxStatus getter/setter hook 유지
- 시작 버전을 v4.9로 갱신

ProccessRequestRes는 static Listing에서 x1이 response/OpInfo 계열 입력으로 사용되는 것이 확인되어 arg[1]을 핵심 관찰 대상으로 삼는다.

### 48.4 다음 런타임 판별 기준

A. TryHandleResponse가 발생하지 않음
→ 현재 runtime hook 대상/네트워크 경로가 실제 게임 요청 경로와 다름

B. TryHandleResponse 발생 + ProccessRequestRes 발생
→ 응답 처리 경로는 실제 실행됨
→ arg[1] concrete type/주소를 다음 추적 기준으로 사용

C. ProccessRequestRes 발생 + BOXSTATUS_GET 발생
→ Chapter UI/상태 소비 시점과 response 처리 시점을 주소 기준으로 비교

D. ProccessRequestRes 발생 + BOXSTATUS_GET 없음
→ 해당 응답이 Chapter BoxStatus를 직접 소비하지 않거나, 다른 helper에서 객체가 채워지는 경로를 우선 추적

E. set_BoxStatus 없음
→ setter 호출 방식이 아니라 direct backing-field write 가능성을 유지

이번 단계의 hook 추가 자체는 **BoxStatus write 경로를 확정하지 않는다.** 목적은 먼저 Deserialize → TryHandleResponse → ProccessRequestRes 런타임 경계를 실제 실행으로 확인하는 것이다.

### 48.5 Git

- research/justice_hook.js v4.9
- commit: ba2c0515e27c7d942915dca5ad01a36dfa7210b3

현재 상태:

ProtoChapter +0x1C = BoxStatus             확정
0x14 response f4 = BoxStatus bitmask       확정
Deserialize → TryHandleResponse            정적 확정
TryHandleResponse → ProccessRequestRes     정적 확정
두 함수 실제 runtime 실행 여부            미확인
0x14 response → ProtoChapter +0x1C write   미확정


## 49. 2026-10-01 — v4.9 runtime 결과 및 status 분기 확인

### 49.1 runtime 결과

실제 실행에서 다음이 확인됐다.

- `NetworkCenter.TryHandleResponse @ 0x7499eb91e0` hook 정상 설치
- `DataCenter.ProccessRequestRes @ 0x7499fe703c` hook 정상 설치
- 로그인 이후 `TryHandleResponse`가 반복 호출됨
- 그러나 같은 실행에서 `ProccessRequestRes` hook은 호출되지 않음

따라서 **응답 처리 루프 자체는 실제 실행 중**이라는 것은 확정됐지만, 모든 응답이 `ProccessRequestRes`로 전달되는 것은 아니다.

### 49.2 정적 분기 원인 확인

`TryHandleResponse @ 015b41e0`에서:

```text
015b4410  ldr x8,[sp, #0x48]
015b4414  cbz x8,0x015b42e4
015b4418  ldrb w20,[sp, #0x44]
015b441c  cmp w20,#0x5
015b4420  b.cs 0x015b44ec
015b442c  ldr x1,[sp, #0x48]
015b4430  mov x2,xzr
015b4434  bl 0x016e203c
```

즉:

```text
status = sp+0x44
status >= 5  → ProccessRequestRes 호출 안 함
status < 5   → ProccessRequestRes 호출
```

현재 로그만으로는 반복된 `TryHandleResponse`가 어느 status인지 확인할 수 없으므로, 다음 v4.9 후속 수정에서 분기 지점(+0x238)의 `sp+0x44`를 직접 관찰하도록 했다.

### 49.3 다음 실행에서 확인할 것

```text
[NET_RESP_STATUS] status=0~4
    → ProccessRequestRes 경로여야 함

[NET_RESP_STATUS] status=5 이상
    → ProccessRequestRes가 호출되지 않는 것이 정상
```

특히 로그인/인게임 요청에서 `status < 5`가 실제 발생하는지 확인한다. 발생한다면 그 시점의 `ProccessRequestRes` 호출과 response object 타입을 연결한다.

### 49.4 Git

- 후속 hook commit: `6653112c26dc5d783c71830c8631c975adc8d132`

현재 단계 결론:

```text
TryHandleResponse runtime 실행                 확인
TryHandleResponse → ProccessRequestRes 조건   정적 확인
ProccessRequestRes runtime 실행               아직 미확인
status별 실제 routing                         다음 실행에서 확인
```


## 50. 2026-10-01 — status=4 및 ProccessRequestRes runtime 경로 확정

### 50.1 runtime 확인

실제 Frida 실행에서 다음 순서가 반복 관찰됐다.

```text
[NET_RESP] TryHandleResponse enter
[NET_RESP_STATUS] status=4 route=ProccessRequestRes
[NET_RESP] ProccessRequestRes enter
  this=DataCenter@...
  response=OpInfo@...
  arg2=0x0
[NET_RESP] ProccessRequestRes leave
[NET_RESP] TryHandleResponse leave
```

따라서 이전의 미확정 상태였던:

```text
TryHandleResponse
  └─ status < 5
       └─ ProccessRequestRes
            └─ arg[1] = OpInfo
```

가 runtime에서 직접 확인됐다.

특히 `status=4`이고 `response=OpInfo@`로 확인되므로, 현재 실행의 일반 데이터 응답은 실제 `DataCenter.ProccessRequestRes(OpInfo)` 경로로 들어간다.

### 50.2 여러 OpInfo 객체 확인

동일 실행에서 다음과 같이 서로 다른 response 객체가 반복 생성/전달됐다.

```text
OpInfo@0x75d43ae5c0
OpInfo@0x75dd6c8730
OpInfo@0x75d3d67b80
```

따라서 특정 단일 OpInfo 인스턴스가 계속 재사용되는 것으로 단정하지 않고, 각 응답별 OpInfo 객체가 생성/전달되는 것으로 취급한다.

### 50.3 BoxStatus 추적의 다음 단계

현재까지:

```text
network response
 → TryHandleResponse
 → status=4
 → ProccessRequestRes(OpInfo)
 → OpInfo +0xC0 = Chapters
 → ProtoChapter +0x1C = BoxStatus
```

앞의 세 단계는 runtime까지 확인됐다.

남은 핵심은:

```text
ProccessRequestRes의 response=OpInfo
        ↓
OpInfo.Chapters(+0xC0)
        ↓
ProtoChapter 객체
        ↓
ProtoChapter +0x1C
```

연결이다.

다음 runtime hook에서는 `ProccessRequestRes` 진입 시 `response=OpInfo`의 `+0xC0` 값을 읽고, collection 객체가 존재하는지 먼저 확인한다. 이후 collection 내부의 ProtoChapter 객체와 `+0x1C` 값을 관찰한다.

### 50.4 HTTP 로그 해석

동일 실행에서 AssetBundle 다운로드의 `HTTP_SEND` 로그가 있었으나 method/body가 비어 있었다.

이는 현재 BoxStatus 추적과 직접 관계가 없으며, 기존 HTTP_SEND 상태 추출의 한계로 취급한다. 네트워크 응답 처리 경로는 이번 runtime 결과로 별도로 확정됐으므로 HTTP_SEND 로그를 다음 단계의 핵심 증거로 사용하지 않는다.

### 50.5 현재 상태

```text
ProtoChapter +0x1C = BoxStatus             확정
0x14 response f4 = BoxStatus bitmask       확정
Deserialize → TryHandleResponse            정적 확정
TryHandleResponse → ProccessRequestRes     정적 + runtime 확정
status=4 → ProccessRequestRes              runtime 확정
ProccessRequestRes arg[1] = OpInfo         runtime 확정
OpInfo +0xC0 = Chapters                    확정
OpInfo.Chapters → ProtoChapter              미확정
ProtoChapter +0x1C 실제 write 지점          미확정
```

### 50.6 다음 작업

1. ProccessRequestRes runtime에서 `response +0xC0` 관찰
2. Chapters collection의 실제 타입/주소 확인
3. collection 내부 ProtoChapter 객체 식별
4. 각 ProtoChapter `+0x1C` 값과 PCAP의 1/5/7 상태 비교
5. 가능하면 Box 1→3→2 실험 중 동일 Chapter 객체의 주소와 BoxStatus 변화를 연결


## 51. 2026-10-01 — OpInfo.Chapters runtime 직접 관찰 hook 추가

정적 Listing에서는 get_Chapters의 Calls IN이 없어 호출 경로를 확보하지 못했다.

따라서 research/justice_hook.js v4.10에 다음 관찰점을 추가했다.

1. DataCenter.ProccessRequestRes 진입 시 response +0xC0 직접 읽기
2. OpInfo.get_Chapters() runtime hook

출력 형식:

    [CHAPTERS_RAW] OpInfo=... +0xc0=...
    [CHAPTERS_GET] OpInfo=... ret=...

목적은 먼저 +0xC0의 실제 concrete 객체 타입을 확인하는 것이다. 이후 해당 객체가 어떤 collection인지 판별하고, 내부의 ProtoChapter 객체를 추적한다.

Git:
- research/justice_hook.js v4.10
- commit 260af582284d0a253487ec4d4816ebf9eb6f7036

다음 실행에서는 BoxStatus 실험을 바로 재현할 필요 없이 일반 로그인/인게임 응답만으로도 [CHAPTERS_RAW]가 나오는지 먼저 확인한다.


## 52. 2026-10-01 — OpInfo.Chapters Dictionary 내부 추적 단계 진입

### 52.1 현재 확인된 runtime 연결

기존 v4.10 실행 결과로 다음까지 확인됐다.

```
TryHandleResponse
  ↓ status=4
ProccessRequestRes
  ↓ arg[1]
OpInfo
  ↓ +0xC0
Chapters collection @ 0x7351b05840
```

따라서 이제 응답 객체와 Chapters collection 사이의 경계는 runtime에서 확인됐다.

### 52.2 이번 단계의 핵심

Chapters가 실제 Dictionary 객체라면 내부에서 다음을 확인해야 한다.

```
Dictionary
 ├─ key
 └─ value
      ↓
   ProtoChapter
      ├─ +0x10 ChapterId
      └─ +0x1C BoxStatus
```

특히 key 또는 ProtoChapter의 ChapterId가 `20000000`인지 확인한다.

### 52.3 주의점

Dictionary 내부 레이아웃을 추정해서 바로 결론 내리지 않는다.

IL2CPP generic Dictionary의 실제 런타임 layout과 현재 Unity/IL2CPP 버전을 먼저 확인하고, 잘못된 offset으로 메모리를 읽어 crash/오판하는 것을 피한다.

따라서 다음 runtime hook의 목적은:

1. +0xC0 객체의 concrete type 확인
2. Dictionary 여부 확인
3. count/entries 확인
4. entry의 key/value 확인
5. value가 ProtoChapter인지 확인
6. `ChapterId=20000000`, `BoxStatus` 연결

순서다.

### 52.4 현재 상태

```
ProccessRequestRes → OpInfo                 runtime 확정
OpInfo +0xC0 → Chapters collection          runtime 확정
Chapters concrete type                      다음 확인
Dictionary key/value → ProtoChapter         미확정
ChapterId 20000000 → ProtoChapter            미확정
ProtoChapter +0x1C → BoxStatus               확정
```

### 52.5 다음 작업

`get_Chapters`의 기존 hook을 중복 설치하지 않고, 해당 return 객체를 대상으로 concrete type/Dictionary 구조를 관찰한다.

Dictionary가 확인되면 key/value를 출력하고, value 객체에 대해 기존 `ProtoChapter +0x10/+0x1C` 관찰을 연결한다.


## 53. 2026-10-01 — Chapters 정적 Listing 재검색 결과

### 53.1 UI 함수 본문 확보 여부

Git의 `research/Ghidra_Listing_txt`를 함수명/주소 기준으로 재검색했다.

```
BattleMapMono$$InitChapters  @ 00e4e080
BattleMapMono$$LayChapterItem @ 00e4f918
```

현재 Git export에서는 두 함수의 독립 Listing 파일/본문을 직접 확보하지 못했다. `UI.txt`와 다른 함수의 Calls IN에서는 해당 주소가 반복 참조되지만, 본문 자체는 검색 결과에 노출되지 않는다.

따라서 이 두 함수 주변 `FUN_00E*`를 현재 Git 텍스트만으로 추정하여 연결하지 않는다.

### 53.2 현재 확인된 Chapter 소비 관계

`ProtoChapter$$IsBoxReceived @ 015acfe8`의 Calls IN:

```
ChapBoxMono$$LayBoxItem
BattleMapMono$$LayChapterItem
BattleSectionMono$$SetStageBoxAndBar
```

즉 `IsBoxReceived`는 Chapter UI 소비 지점이라는 기존 결론을 유지한다.

### 53.3 get_Chapters 직접 caller

현재 Git 검색에서도:

```
OpInfo$$get_Chapters @ 015aadec
```

의 concrete Calls IN은 확보되지 않았다.

따라서 `BattleMapMono$$InitChapters`가 내부적으로 get_Chapters를 호출한다고 현재 단계에서 단정하지 않는다.

### 53.4 다음 추적 방향 변경

정적 UI 본문 확보가 막힌 상태이므로, 현재 가장 정보량이 큰 것은 runtime이다.

우선:

```
ProccessRequestRes
  ↓
response +0xC0
  ↓
concrete type
  ↓
Dictionary 여부
  ↓
entry key/value
  ↓
ProtoChapter 주소
  ↓
+0x10 ChapterId
  ↓
+0x1C BoxStatus
```

를 확인한다.

특히 기존 실행에서 확인된:

```
OpInfo +0xC0 = 0x7351b05840
```

를 다시 확보하고, 이 주소의 concrete type을 먼저 확인한다.

Dictionary가 맞는 경우에만 내부 entry layout을 적용한다.

### 53.5 현재 상태

```
OpInfo +0xC0 = Chapters             runtime 확인
Chapters concrete type              미확정
Dictionary key/value                미확정
ChapterId=20000000 연결             미확정
ProtoChapter +0x1C = BoxStatus      확정
InitChapters 본문                   Git export 미확보
LayChapterItem 본문                 Git export 미확보
```

## 54. 2026-10-01 — InitChapters/LayChapterItem 본문 확보 및 Chapters Dictionary 경로 확정

사용자가 제공한 Ghidra Listing으로 기존에 미확보였던 두 함수 본문을 직접 확인했다.

### 54.1 BattleMapMono::InitChapters

`BattleMapMono$$InitChapters @ 00e4e080`에서 다음이 확인된다.

```
DataCenter.Instance
  +0x48
    ↓
Dictionary<int, ProtoChapter>
```

실제 Listing에서 `Dictionary<int, ProtoChapter>.GetEnumerator()`, `ContainsKey()`, `DataCenter.Instance`, `DataCenter +0x48`가 함께 사용된다.

또한 `DataCache.LastChapter`를 key로 사용하여 `Dictionary<int, ProtoChapter>.ContainsKey()`를 수행한다.

### 54.2 BattleMapMono::LayChapterItem

`BattleMapMono$$LayChapterItem @ 00e4f918`에서는 ChapterData의 ID를 key로 하여 동일 Dictionary에서 `ProtoChapter`를 가져오는 경로가 직접 확인된다.

```
ChapterData
  ↓ BaseData.get_id()
  ↓
DataCenter.Instance + 0x48
  ↓ Dictionary<int, ProtoChapter>.get_Item(id)
  ↓ ProtoChapter
```

그리고 가져온 ProtoChapter에 대해 `ProtoChapter$$IsBoxReceived(lVar6, 1 << uVar14)`를 호출한다.

동일 객체에서 `*(int *)(lVar6 + 0x18)`도 직접 읽으므로 ProtoChapter의 +0x18 필드가 Chapter UI의 보상 조건 계산에 사용되는 것도 확인된다.

### 54.3 현재 객체 관계

```
DataCenter
 └─ +0x48
     Dictionary<int, ProtoChapter>
       ├─ key   = ChapterData ID
       └─ value = ProtoChapter
                    ├─ +0x10 ChapterId
                    ├─ +0x18 Chapter 관련 상태값
                    └─ +0x1C BoxStatus
```

따라서 기존에 미확정이었던 `Chapters concrete type`과 `Dictionary key/value → ProtoChapter`가 정적으로 확정됐다.

`ChapterId=20000000`은 아직 실제 runtime key/value에서 확인하지 않았다.

### 54.4 justice_hook.js 현재 버전

Git 현재 기준 `research/justice_hook.js`는 v4.11로 갱신했다.

기존 `OpInfo.get_Chapters` hook을 중복 설치하지 않고 반환 객체에 concrete class name, 객체 주소, `_count` field offset/value를 출력하도록 확장했다.

출력:

```
[CHAPTERS_GET] ...
[CHAPTERS_DICT] type=...
[CHAPTERS_DICT] _count@+0x...=...
```

Git commit:
`f651b75e392e8b2740c3f2a5fee70969dd40d397`

### 54.5 다음 런타임 작업

Dictionary raw entry layout은 아직 추정하지 않는다.

다음 실행에서 먼저 `[CHAPTERS_DICT] type=Dictionary...`와 `_count`를 확인한다.

그 후 concrete Dictionary의 `_entries` field와 Entry generic layout을 runtime metadata로 확인하고 `key → ProtoChapter* → +0x10 ChapterId → +0x1C BoxStatus`를 연결한다.

최종 목표는 `ChapterId=20000000`에 해당하는 ProtoChapter 객체 주소와 BoxStatus 값을 직접 확인하는 것이다.