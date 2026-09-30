# 2026-09-30 이벤트던전 Box PCAP / KCP DH64 후속 분석

## 기준
- Git 기준 `research/*.md`, `research/reports/*.md`
- `Ghidra_Listing_txt` 함수명은 앞 2글자 기준이며 `< > $` 등은 `_` 치환
- 대상 PCAP JSON: `research/PCAP/이벤트던전_box보상선택_오픈_획득.json`
- 확인되지 않은 opcode/상태는 추측으로 확정하지 않음

## 1. 이벤트 Box PCAP 직접 확인

총 103 packet.

Game Server:
- TCP: `10.215.173.1:43764 <-> 182.92.62.79:8000`
- UDP/KCP: `192.0.0.8:45186 <-> 182.92.62.79:8000`

TCP handshake:
- client frame 84: payload 373 bytes
- server frame 86: payload 37 bytes
- client/server DH public 2개씩 존재

TCP client public raw:
`ae a5 9a b9 34 02 73 6d`
`9b 90 eb db b5 0a a6 ed`

TCP server public raw:
`bf 8d 4c 51 d1 84 0f 1e`
`ba 85 96 85 9f d5 87 e1`

client handshake 뒤 344-byte Base64 parameter도 존재하며 Base64 decode 결과는 256 bytes다. 현재 이 값의 의미는 확정하지 않는다.

## 2. 실제 KCP application pair

KCP application packet은 다음 4개가 확인된다.

```
frame 92  C -> S  UDP 45186 -> 8000
frame 93  S -> C  ACK
frame 94  S -> C  UDP 8000 -> 45186
frame 95  C -> S  ACK
```

KCP header는 28 bytes.

frame 92:
- KCP data length = 0x31 = 49
- flag = 0x80
- IV = `b3c9617c319f7d74ffe8d10b33d9bcae`
- ciphertext = 32 bytes

frame 94:
- KCP data length = 0x161 = 353
- flag = 0xC4
- IV = `a51324f4b36f138fe67259daee379cd3`
- ciphertext = 336 bytes

따라서 이 캡처에서도 기존과 동일하게:

```
flag + IV16 + Rijndael ciphertext
```

framing이 확인된다.

## 3. 중요한 정정 — TCP DH key로 KCP payload가 복호화되지 않음

TCP handshake의 public 값을 기준으로 `p=2^64-59`, `g=5`의 discrete log을 계산했다.

client private residue:

```
private1 = 0x37310cfa29010efd
private2 = 0x524b10294d25bb02
```

TCP server public을 사용한 shared secret:

```
secret1 = 0x344b216fd2367c88
secret2 = 0xace2f3c707c7a405
```

16-byte LE key:

```
887c36d26f214b3405a4c707c7f3e2ac
```

그러나 frame 92/94의 KCP ciphertext를 이 key + 각 packet IV로 Rijndael/AES-128-CBC/PKCS7 복호화하면 padding 검증에 실패한다.

따라서 이번 캡처에서는 TCP DH session key를 KCP application key로 재사용한다고 볼 수 없다.

이 결과는 기존 보고서의:

```
TCP
  -> TCP session key

KCP
  -> 별도 DH
  -> KCP session key
```

구조와 일치한다.

## 4. 이번 PCAP에서 KCP DH handshake가 보이지 않는 문제

현재 JSON의 UDP packet을 모두 확인했다.

Game Server UDP packet은 frame 92~95뿐이며, 이 중:
- frame 92 = encrypted application
- frame 93 = ACK
- frame 94 = encrypted application
- frame 95 = ACK

이다.

기존 분석에서 확인된 KCP Handshake1 구조:

```
8 bytes zero
8 bytes KCP public #1
8 bytes KCP public #2
param4
```

형태의 별도 UDP handshake packet은 이번 캡처에 존재하지 않는다.

따라서 현재 이벤트 PCAP만으로는 KCP private/public pair를 복구할 직접 입력이 부족하다.

## 5. Box opcode 0x14에 대한 현재 상태

정적 Listing으로 다음은 확정이다.

```
ChapBoxMono.ClickGetReward
    ↓
GetChapterBoxReward @ 00ddeea8
    ↓
opcode 0x14
    ↓
u32 chapterId + u32 boxIndex
```

이번 이벤트 PCAP의 frame 92가 제목상 Box 보상 동작과 시간/구간상 대응되는 강한 후보이기는 하지만, 현재 KCP key가 없어 plaintext opcode를 확인하지 못했다.

따라서 현재도:

```
frame 92 = opcode 0x14 후보
frame 94 = opcode 0x14 response 후보
```

까지만 유지한다.

## 6. 다음 작업

가장 필요한 것은 새로운 Ghidra 분석이 아니라 **KCP handshake 확보**다.

우선순위:

1. 동일 이벤트 Box 동작을 다시 캡처할 때 KCP 시작 직전부터 capture
2. UDP 8000 전체 packet을 빠짐없이 확보
3. KCP Handshake1/Handshake2 packet에서 client/server public #1/#2 추출
4. public -> private residue 계산
5. KCP session key 생성
6. frame 92 복호화하여 plaintext OpCode 확인
7. frame 94 복호화하여 response OpInfo 확인
8. `OpInfo.Chapters -> ProtoChapter -> BoxStatus(+0x1C)` 갱신 여부 확인

## 7. 현재 결론

- 이벤트 Box PCAP JSON 직접 분석: 완료
- frame 92/94 KCP application pair: 확인
- 암호화 framing: 확인
- TCP DH private residue 계산: 확인
- TCP DH key로 KCP decrypt: 실패
- TCP와 KCP의 별도 key 구조: 추가로 지지
- frame 92/94의 0x14 여부: 미확정
- BoxStatus response 갱신: 미확정
- 현재 병목: **이번 이벤트 세션의 KCP DH handshake packet 확보**


## 8. 2026-09-30 추가 — KCP 키 입력 경로 재확인

기존 저장소의 별도 PCAP 분석 결과에서 KCP handshake는 다음 구조로 확인되어 있다.

```
8 bytes zero
8 bytes KCP public #1
8 bytes KCP public #2
param4
```

이번 이벤트 PCAP의 TCP handshake 뒤 344-byte Base64 → 256-byte 데이터는 현재 의미가 확정되지 않았으므로 KCP public으로 취급하지 않는다.

현재 병목은:

```
TCP DH public
   ↓
TCP session key
   ↓
KCP decrypt 실패

KCP 별도 DH public
   ↓
KCP session key
   ↓
frame 92/94 decrypt
```

이다.

따라서 다음 캡처에서는 **UDP 8000 최초 packet부터** 확보해야 한다.

```
KCP 연결 시작
 → Handshake1
 → Handshake2
 → Box 선택/오픈/획득
```

확보 후 바로:

```
KCP public
 → private residue
 → session key
 → frame 92/94 decrypt
 → opcode 0x14 확인
 → Chapters
 → ProtoChapter.BoxStatus
```

로 이어간다.

현재 결론:
- frame 92 = 0x14: 후보
- frame 94 = 0x14 response: 후보
- BoxStatus 변경: 미확정
- TCP DH key 재사용: 반증
- 다음 핵심 입력: **KCP handshake packet**
