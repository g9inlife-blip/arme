# 2026-09-29 GetDefaultParams Helper 정적분석 결과

- 기준: `research/reports/2026-09-29-Ghidra-Listing-정적분석-작업기준.md`
- 대상: `ProtocolGame_HttpRequest$$GetDefaultParams @ 00ddbf58`
- 원본: `research/Ghidra_Listing_txt/PR.txt`, `AL/`, `AP.txt`
- 환경: ARM64 실기기 + hook-patched APK

## 1. 핵심 결론

`GetDefaultParams`의 정적 호출 순서와 runtime 로그인 body를 대조한 결과:

| key | 생성 경로 | runtime 값 | 상태 |
|---|---|---|---|
| `n` | `DateTime.Now.Ticks.ToString()` | `639262781542097130` | 확정 |
| `d` | `Ali.get_deviceUniqueIdentifier()` | `cbcfdf10d56e57a89f7cb19a491d139e` | 확정 |
| `r` | `get_retailID()` | `7` | 확정 |
| `v` | `get_buildVerion()` | `3.1.0` | 확정 |
| `m` | `AppConst.get_Mark()` | `official` | 확정 |
| `t` | `get_Token()` | 긴 Base64 값 | 확정 |
| advertisingIdentifier | `Ali.get_advertisingIdentifier()` | 로그인 body에 없음 | 조건부 |

**중요:** runtime body의 긴 Base64 `t`는 advertising identifier가 아니라 `get_Token()` 반환값이다.

## 2. GetDefaultParams 흐름

```text
GetDefaultParams @ 00ddbf58
  -> DateTime.Now -> Ticks -> ToString -> n
  -> Ali.get_deviceUniqueIdentifier @ 00e0a148 -> d
  -> Ali.get_advertisingIdentifier @ 00e0a494
       -> IsNullOrEmpty
       -> 비어 있지 않을 때만 Dictionary에 추가
  -> get_retailID @ 00dd949c -> r
  -> get_buildVerion @ 00dd90bc -> v
  -> AppConst.get_Mark @ 016dacf8 -> m
  -> get_Token @ 00dd9534 -> t
       -> IsNullOrEmpty 검사 후 Dictionary에 추가
```

## 3. n: timestamp

Listing에서 `DateTime.get_Now @ 02133d48`, `DateTime.get_Ticks @ 02132788`, `Int64.ToString @ 0214ed58`, `Dictionary.set_Item @ 0196e4c0` 순서가 확인된다.

runtime 값 `n=639262781542097130`과 정확히 연결된다.

## 4. d: deviceUniqueIdentifier

`Ali$$get_deviceUniqueIdentifier @ 00e0a148`의 우선 경로는 singleton field `+0x420`에 연결된 delegate다.

fallback에서는 `UnityEngine.SystemInfo.get_deviceUniqueIdentifier @ 024d5ca0`를 사용한다. 값이 유효하지 않은 경우 PlayerPrefs를 확인하고, 없으면 `Guid.NewGuid -> Guid.ToString -> PlayerPrefs.SetString -> PlayerPrefs.Save` 경로로 저장한다.

따라서 현재 `d`는 장치 식별값 계열이며 Token 자체가 아니다.

## 5. r: retailID

`ProtocolGame_HttpRequest$$get_retailID @ 00dd949c`:

```text
singleton field +0xd0
  -> 값이 있으면 반환
  -> 없으면 SDKManager.get_Retail @ 00deb798
  -> Int32.ToString @ 0214dc44
```

runtime `r=7`과 연결된다.

## 6. v: build version

`ProtocolGame_HttpRequest$$get_buildVerion @ 00dd90bc`:

```text
singleton field +0xf0
  -> 값이 있으면 반환
  -> 없으면 AliothEngine.BuildVersionBindings.GetBuildVersion @ 0165561c
```

runtime `v=3.1.0`과 연결된다.

## 7. m: mark

`AppConst$$get_Mark @ 016dacf8`의 우선 경로는 singleton instance field `+0x28`이다.

fallback에서는 `AliothEngine.Android.VasDollyHelper$$GetChannel @ 016a857c`를 호출하고, 반환값이 비어 있는 경우 내부 분기에서 채널 문자열을 선택한다.

runtime 값은 `m=official`로 확정된다. 다만 이번 실행에서 `+0x28` 직접 경로인지 VasDolly fallback인지까지는 아직 확정하지 않는다.

## 8. t: Token

`ProtocolGame_HttpRequest$$get_Token @ 00dd9534`는:

```text
singleton field +0x100
  -> 값이 있으면 delegate 반환
  -> 없으면 global object 확인
       -> object +0x20
       -> field +0x28
```

구조다.

V4 로그인 body에서 `t=` 뒤에 들어간 긴 Base64 문자열은 이 getter 직후 Dictionary에 추가된다. 따라서 `t=Token`으로 확정한다.

이전의 `t=advertisingIdentifier` 추정은 폐기한다.

## 9. 현재 로그인 body 구조

```text
GetDefaultParams
  n = DateTime.Now.Ticks.ToString()
  d = deviceUniqueIdentifier
  advertisingIdentifier = 조건부
  r = retailID
  v = buildVersion
  m = mark
  t = Token
       |
       v
V4_POST_Login 추가
  u
  p
  method
  platform
  p2
       |
       v
Sign
  -> sorted Dictionary keys
  -> values
  -> String.Join(".")
  -> MD5HashString
  -> sign
```

현재 runtime body는 다음 구조다.

```text
n=639262781542097130&d=cbcfdf10d56e57a89f7cb19a491d139e&r=7&v=3.1.0&m=official&t=<Token>&u=witchwind3&p=witchwind3&method=&platform=google&p2=logout&sign=2d4ae03ee9014998502caf2046c002a3
```

## 10. 현재 분석 상태

| 항목 | 상태 |
|---|---|
| n 생성 | 확정 |
| d 생성 | 확정 |
| advertisingIdentifier 호출 | 확정 |
| advertisingIdentifier 로그인 포함 여부 | 미포함 확인 |
| r 생성 | 확정 |
| v 생성 | 확정 |
| m 반환값 | `official` 확정 |
| m의 실제 분기 경로 | 추가 확인 필요 |
| t 생성 getter | 확정 |
| t의 최초 원천 | 추가 분석 필요 |
| Sign 입력 구성 | 확정 |
| HTTP form 결과 | runtime으로 확정 |
| PCAP byte-level 대응 | 다음 단계 |

## 11. 다음 작업

### 1순위: Token 원천 추적

현재 가장 중요한 미해결 지점은 `get_Token`의 singleton field `+0x100` 또는 fallback global object `+0x20/+0x28`에 **언제 값이 기록되는가**이다.

다음에는 해당 field의 write XREF를 추적하여 긴 Base64 Token이 서버 response에서 저장되는지, 로컬 저장값인지, 암호화/인코딩 결과인지 확인한다.

### 2순위: 로그인 PCAP byte-level 대조

대상:

`research/PCAP/PCAPdroid_29_9월_11_12_23_어플시작_로그인_메인까지.pcap`

runtime 기준:

```text
POST /v5/account/login?778927
Content-Type: application/x-www-form-urlencoded
body_len = 551
```

비교 순서:

```text
PCAP TCP stream
 -> HTTP request 탐색
 -> URL / method 확인
 -> body 추출
 -> runtime body와 byte-for-byte 비교
 -> Content-Length / TCP sequence 확인
 -> HTTP response 추출
```

### 3순위: response 처리

request가 PCAP에서 정확히 일치하면 `RequestCoroutine -> UnityWebRequest.Post -> Send -> isDone -> response -> OnDone/OnFail` 순으로 로그인 response까지 연결한다.

## 12. 분석 원칙

함수명만으로 역할을 확정하지 않는다.

```text
Ghidra Listing
+ 호출 관계
+ 인자/반환값
+ runtime 실제 값
+ PCAP 실제 bytes
```

가 일치하는 경우에만 확정한다.

이번 단계에서는 특히 `t`를 `get_Token()`으로 확정한 것이 핵심 진전이다.
