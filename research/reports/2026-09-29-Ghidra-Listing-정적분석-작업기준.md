# Ghidra Listing 자료 구조 및 정적분석 작업 기준

- 작성일: 2026-09-29
- 저장소: `g9inlife-blip/arme`
- 대상: `research/Ghidra_Listing_txt`
- 목적: Ghidra Listing 자료를 runtime hook 및 PCAP 분석과 연결하여 함수 역할을 확정

---

## 1. Listing 자료 구성

`research/Ghidra_Listing_txt`에는 Ghidra에서 추출한 Listing 결과가 함수명 시작 문자열 기준으로 묶여 ZIP으로 저장되어 있다.

예:

```text
AB.zip
AC.zip
AD.zip
...
XL.zip
...
ZH.zip
```

각 ZIP은 함수명/Listing의 시작 문자열을 기준으로 묶은 자료이므로 필요한 함수 후보를 전체 Listing에서 찾을 때 검색 범위를 줄이는 용도로 사용한다.

### FUN_ 자료

```text
FUN_.zip
```

은 자동 명명 스크립트로 실제 함수명이 부여되지 않은 `FUN_*` 함수들을 별도로 모아둔 자료다.

따라서:

- 일반 ZIP: 이미 함수명이 식별된 함수 중심
- `FUN_.zip`: 아직 의미 있는 함수명이 없는 함수 중심

으로 구분한다.

---

## 2. 현재 런타임에서 확보한 로그인 경로

2026-09-29 ARM64 실기기 + hook-patched APK 실행에서 로그인 request가 다음 경로로 확인되었다.

```text
ProtocolGame_HttpRequest.V4_POST_Login
        ↓
GetDefaultParams
        ↓
Sign
        ↓
AliothEngine.Net.HttpRequest
        ↓
UnityWebRequest
        ↓
UploadHandlerRaw(byte[])
        ↓
POST /v5/account/login
```

현재 Sign 알고리즘은 정적 + 런타임으로 확정되어 있다.

```text
Dictionary.Keys
    ↓
OrderBy(x => x)
    ↓
정렬된 key의 value
    ↓
content 추가
    ↓
String.Join(".", values)
    ↓
MD5HashString
    ↓
dict["sign"]
```

---

## 3. 이번 실행에서 확보한 HttpRequest method

`AliothEngine.Net.HttpRequest`에서 다음 메서드가 확인되었다.

```text
get_isError()
get_PingTime()
set_PingTime()
RequestCoroutine()
CheckTimeout()
get_IsDone()
set_Headers()
get_Headers()
set_Timeout()
get_Timeout()
set_OnDone()
set_OnFail()
set_OnDisposed()

.ctor(MonoBehaviour,string)
.ctor(MonoBehaviour,string,string)
.ctor(MonoBehaviour,string,float)
.ctor(MonoBehaviour,string,Dictionary<string,string>)

AddHeader(string,string)
AddData(string,string)
AddRangeData(Dictionary<string,string>)

AddBinaryData(string,byte[])
AddBinaryData(string,byte[],string)
AddBinaryData(string,byte[],string,string)

Request()
Dispose()
CheckConnection(string,Action<bool>)
CreateURL(List<string>,string,Dictionary<string,string>)
ResetCache(string)
```

### 현재 우선 분석 대상

```text
AddData
AddRangeData
Request
CreateURL
.ctor(...)
```

이 다섯 영역을 먼저 분석한다.

---

## 4. 왜 AddData부터 확인하는가

실제 로그인 body는:

```text
n=...&d=...&r=7&v=3.1.0&m=official&...&sign=2d4ae03ee9014998502caf2046c002a3
```

형태의 `application/x-www-form-urlencoded` 데이터다.

따라서 다음 질문을 코드에서 확인해야 한다.

1. dictionary가 어떤 순서로 body에 들어가는가?
2. key/value URL encoding은 어디서 수행하는가?
3. `&`와 `=`는 어디서 생성되는가?
4. 빈 문자열 `method=`는 어떻게 보존되는가?
5. `sign`은 언제 추가되는가?
6. `AddData`와 `AddRangeData` 중 어느 쪽이 로그인 body를 구성하는가?
7. `CreateURL`은 URL query와 body 중 어느 부분을 담당하는가?

---

## 5. 실제 런타임 증거

ARM64 실기기에서 v4.6 hook으로 다음이 확인되었다.

### UploadHandlerRaw

```text
UploadHandlerRaw(byte[])
body_len = 551
```

실제 body:

```text
n=639262781542097130&d=cbcfdf10d56e57a89f7cb19a491d139e&r=7&v=3.1.0&m=official&t=jLDohEUPbopnwARSF4L%2fERqOUc1bvMSJCWDvIQqHkF0Qjn%2fS2xt%2f5CAoaxoYsTQ0oEeS7l1xEy8U2TNzM%2br9wJ8qGD8B%2f3ItbtOa7IDcauHiZnHoKIUnDAQQGbUdLia3D1BNXW70lzjbVmA%2f0%2bRuQUpa1n6Gj881gOEgtovFxkbYptUVUEByYWgkhJcuqW%2fVv25Pm95ikRUXVXKlAGJq9G5Demi43jfStGJBdE3F692g3JaBkfGRoDgH%2f92BIT7s%2fI%2f9Tt7jDH6p0uJdHr9GEVVwMlfnlL%2bWhfthrijayY6GyziOg6Qhn7NjK1NkHYxoOE125o5gV9e1Dr4qsgC60Q%3d%3d&u=witchwind3&p=witchwind3&method=&platform=google&p2=logout&sign=2d4ae03ee9014998502caf2046c002a3
```

HTTP:

```text
POST https://ac.aliother.com/v5/account/login?778927
Content-Type: application/x-www-form-urlencoded
```

이 값은 이후 Ghidra 정적 분석의 검증 기준으로 사용한다.

---

## 6. Ghidra 분석 방법

### 6.1 이름이 있는 함수

먼저 Listing ZIP에서 직접 함수명을 검색한다.

우선순위:

```text
AliothEngine.Net.HttpRequest$$AddData
AliothEngine.Net.HttpRequest$$AddRangeData
AliothEngine.Net.HttpRequest$$Request
AliothEngine.Net.HttpRequest$$CreateURL
AliothEngine.Net.HttpRequest$$.ctor
```

함수명에 `$$` 표기가 없는 경우에도 마지막 메서드명 기준으로 검색한다.

### 6.2 호출 함수 추적

각 함수에서 다음을 기록한다.

```text
- 호출 대상
- 호출 순서
- 문자열 literal
- Dictionary/List 관련 API
- StringBuilder 관련 API
- URL encode 관련 API
- byte[] 생성/복사
- UTF-8/Encoding 변환
- UnityWebRequest 생성
- UploadHandlerRaw 호출
```

### 6.3 FUN_ helper 추적

이름이 없는 helper가 발견되면 `FUN_.zip`에서 해당 주소의 Listing을 찾는다.

단순히 함수명만 보고 역할을 추정하지 않는다.

다음 증거가 있어야 의미를 부여한다.

```text
호출 위치
+
인자 형태
+
반환값
+
문자열/상수
+
호출 대상
+
runtime 결과
```

---

## 7. 함수 역할 확정 기준

함수 역할은 다음 3개 자료가 일치할 때 확정한다.

```text
Ghidra Listing
    ↓
정적 호출 관계 / 데이터 흐름

Runtime Hook
    ↓
실제 인자 / 반환값 / 호출 시점

PCAP
    ↓
실제 네트워크 bytes
```

예를 들어 `AddData`가:

```text
key + "=" + URL-encoded(value)
```

를 생성한다면 실제 로그인 body의 해당 부분과 일치하는지 확인한다.

---

## 8. PCAP과 연결

로그인 PCAP:

```text
research/PCAP/PCAPdroid_29_9월_11_12_23_어플시작_로그인_메인까지.pcap
```

현재 확보한 runtime request:

```text
POST /v5/account/login?778927
Content-Type: application/x-www-form-urlencoded
body_len: 551
sign: 2d4ae03ee9014998502caf2046c002a3
```

다음 단계에서는 PCAP에서 동일 request를 찾아:

```text
URL
HTTP method
Content-Type
Content-Length
body
TCP sequence
response
```

를 비교한다.

PCAP과 runtime body가 정확히 일치하면 로그인 HTTP 경로가 완전히 연결된다.

---

## 9. 현재 작업 우선순위

### 1순위 — HttpRequest

```text
AddData
AddRangeData
CreateURL
Request
.ctor
```

### 2순위 — URL/form serialization helper

```text
Uri.EscapeDataString
WWWForm
StringBuilder
Encoding.UTF8
byte[]
```

등과 유사한 동작을 하는 함수 탐색.

### 3순위 — response

로그인 response를 처리하는:

```text
RequestCoroutine
OnDone
OnFail
get_IsDone
```

경로를 확인한다.

### 4순위 — 로그인 이후 API

로그인 후 메인 화면까지 발생하는 API 요청과 AssetBundle 요청을 구분한다.

### 5순위 — TCP/KCP/DH64

기존:

```text
Alioth.S1.Common.DH64
Alioth.S1.Net.KCPTube
Alioth.S1.Net.TCPTube
```

분석과 연결하여 인게임 데이터 통신 경로를 확정한다.

---

## 10. 실기기 분석 환경 기준

현재 hook 분석 환경은:

```text
ARM64 실기기
+
hook-patched APK
```

이다.

**LDPlayer/x86 에뮬레이터를 현재 hook 실행 환경으로 사용하지 않는다.**

따라서 이후 실행 지시 및 문서에서는 실기기 기준으로 작성한다.

---

## 11. 다음 작업에서 사용자가 제공할 자료

현재 v4.6 로그인 body는 이미 충분히 확보되었으므로 다시 hook을 실행할 필요는 없다.

다음 사용자 작업은 Ghidra에서 우선 다음 함수의 Listing/decompile 내용을 확보하는 것이다.

```text
AliothEngine.Net.HttpRequest$$AddData
AliothEngine.Net.HttpRequest$$AddRangeData
AliothEngine.Net.HttpRequest$$CreateURL
AliothEngine.Net.HttpRequest$$Request
AliothEngine.Net.HttpRequest$$.ctor
```

각 함수의:

- 시작 주소
- 전체 Listing
- decompile
- 호출되는 FUN_ 함수

가 있으면 된다.

이 자료를 현재 `Ghidra_Listing_txt`와 대조하여 로그인 body 생성 과정을 정리한다.

---

## 12. 결론

현재 단계의 핵심은 Sign 알고리즘 재분석이 아니다.

Sign은 다음과 같이 확정되었다.

```text
sort(keys)
→ values
→ content
→ Join(".")
→ MD5
→ sign
```

그리고 실제 HTTP body까지 확보되었다.

따라서 다음 분석 목표는:

```text
Sign 결과
    ↓
HttpRequest.AddData/AddRangeData
    ↓
form-urlencoded serialization
    ↓
HttpRequest.Request
    ↓
UnityWebRequest
    ↓
UploadHandlerRaw
    ↓
PCAP
```

를 Ghidra 코드 수준에서 연결하는 것이다.

`Ghidra_Listing_txt`의 이름 있는 함수 묶음과 `FUN_.zip`을 이 작업의 정적 분석 원본으로 사용한다.
