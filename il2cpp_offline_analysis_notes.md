# IL2CPP 오프라인 진입 분석 작업 정리

## 목표
종료된 게임을 온라인 서버 없이 로컬 리소스(OBB/Cache/Build)를 이용해 초기화하고 게임 화면까지 진입할 수 있는지 분석한다.

현재는 **패치보다 정적 분석으로 최소 분기 지점을 찾는 단계**다.

## 작업 경로
`C:\Users\USER\Documents\Codex\arme`

주요 파일:
- APK / OBB
- `arm64-v8a/libil2cpp.so`
- `global-metadata.dat`
- `script.json`
- `stringliteral.json`
- `il2cpp.h`
- smali / il2cppdump 결과

OBB는 대화에 업로드하지 않았지만 로컬에는 존재한다.

## 현재 실행 현상
게임 시작 시:
1. 버전 체크
2. `업데이트 확인중`
3. `리소스파일 업데이트`
4. `업데이트 실패, 다시 시도하겠습니까?`

기존 `noNeed` 관련 처리는 효과가 있었고 유지한다. 이후 분석에서는 이 부분을 다시 건드리지 않는다.

현재 목표는 **리소스/Manifest 업데이트 확인 단계에서 이미 존재하는 로컬 리소스를 정상 경로로 취급하도록 하는 지점**을 찾는 것이다.

---

## 중요한 논리 이름
dump/script에서 확인된 관련 이름:
- `CheckAssets`
- `CheckAssets_d__75`
- `CheckAssets_d__75::MoveNext`
- `isAssetNeedUpdate_CheckCacheAndBuild`

`stringliteral.json`에서 확인된 값:
- `"CheckAssets"` → `0x3E57848`
- `"isAssetNeedUpdate_CheckCacheAndBuild"` → `0x3E57860`

주의: 위 값은 **문자열 주소**이지 코드 RVA가 아니다.

---

## 확인된 함수 1: `FUN_016807A0`

주소:
`0x016807A0`

핵심 구조:

```c
iVar2 = FUN_02104534(param_1, 0);

if (iVar2 == 0) {
    // 객체 상태 확인
    // 필요하면 FUN_00EC52B8
    // 최종적으로 [lVar4 + 0xB8] 값을 반환
} else {
    // FUN_01C80F88(...)
    // FUN_00EF2BCC(...)
    // 다른 결과를 반환
}
```

현재 해석:
- `FUN_02104534` 결과에 따라 두 경로로 분기
- 그러나 이 함수 자체가 업데이트 서버 체크 함수라는 증거는 없음
- **직접 패치하지 않음**

---

## 확인된 함수 2: `FUN_02104534`

```c
int FUN_02104534(undefined8 param_1)
{
  int iVar1;
  int iVar2;
  int iVar3;

  iVar1 = FUN_00EE86B4(param_1,0);
  iVar2 = FUN_00EE876C(param_1);

  if (1 < iVar2) {
    iVar2 = 1;
    do {
      iVar3 = FUN_00EE86B4(param_1,iVar2);
      iVar1 = iVar3 * iVar1;
      iVar2++;
      iVar3 = FUN_00EE876C(param_1);
    } while (iVar2 < iVar3);
  }
  return iVar1;
}
```

해석:
- 여러 상태값을 곱해서 집계
- 예: `1×1×0 = 0`
- 따라서 실제 검사를 수행하기보다 **상태 배열의 결과를 집계하는 함수**로 보임

패치하지 않음.

---

## 확인된 함수 3: `FUN_00EE86B4`

```c
undefined4 FUN_00EE86B4(long *param_1,int param_2)
{
  long *plVar1;

  if (param_2 >= 0 &&
      param_2 < (int)(uint)*(byte *)(*param_1 + 0x122)) {

    plVar1 = param_1 + 3;

    if (param_1[2] != 0)
      plVar1 = (long *)(param_1[2] + (long)param_2 * 0x10);

    return (int)*plVar1;
  }

  ...
}
```

해석:
- 배열/컬렉션에서 특정 원소 값을 읽음
- 실제 업데이트 체크 함수가 아님
- 중요한 것은 **이 상태 배열에 0/1을 누가 기록하는가**

패치하지 않음.

---

## 확인된 코드 4: `0x01681958 ~ 0x01681A2C`

주요 명령:

```asm
01681968  ldr x2,[x8,#0x10]
0168196c  bl  FUN_01C83B04

01681998  bl  FUN_00EF2BCC

...

016819FC  bl  FUN_00EC52B8

01681A18  ldr x8,[x19,#0xB8]
01681A1C  ldr x0,[x8]
01681A2C  ret
```

객체 상태/초기화 관련 helper 성격으로 보임.

`CheckAssets_d__75::MoveNext`라고 확정하지 않는다.

---

## 중요한 정정

이전에 다음 주소를 `MoveNext` 또는 성공 callback으로 추정했으나 현재는 폐기한다.

- `0x01681DF0`
- `0x01681980`

이유:
- `0x01681980`은 함수 시작점이 아니라 중간 명령
- `0x01681DF0`도 coroutine `MoveNext`라는 충분한 증거가 없음
- 디스어셈블리 구조가 일반적인 상태 머신 `MoveNext`와 일치한다고 확정할 수 없음

따라서 이 주소를 패치 지점으로 사용하지 않는다.

---

## FDE/XREF 혼동

다음과 같은:

```text
03050BCC ...
031E2EB8 ...
FUN_016807A0
```

항목은 `.eh_frame`의 FDE(Frame Descriptor Entry) / unwind 정보다.

실제 함수 호출자가 아니다.

따라서 `03050...`, `031E2...`, `fde_...` XREF는 호출자 탐색에서 무시한다.

---

## Ghidra 함수명 문제

Ghidra에서는 함수가:

```text
FUN_016807A0
FUN_00EE86B4
...
```

처럼 익명으로 표시된다.

따라서 `CheckAssets_d__75::MoveNext` 같은 이름을 Ghidra에서 직접 검색하는 방법은 사용할 수 없다.

**RVA / code XREF / ARM64 instruction pattern 기반 분석이 필요하다.**

---

## script.json에서 MoveNext RVA 찾기

`script.json`에서 `CheckAssets_d__75::MoveNext`의 실제 code address를 명확히 매칭하지 못했다.

`il2cpp.h`에는 `CheckAssets_d__75` 및 `MoveNext` 관련 구조가 있지만, 그것만으로 Ghidra의 `FUN_xxx`와 실제 RVA를 확정할 수 없다.

따라서:
`0x01681DF0 = CheckAssets_d__75::MoveNext`
라는 가정은 폐기한다.

---

## 현재 가장 좋은 분석 전략

주소를 눈으로 계속 매핑하지 않고 **ARM64 명령어 패턴을 자동 검색**한다.

### 1차 후보
```asm
BL    <검사 함수>
CBZ   W0, ...
```

```asm
BL    <검사 함수>
CBNZ  W0, ...
```

```asm
BL    <검사 함수>
TBZ/TBNZ ...
```

### 2차 후보
```asm
BL    <검사 함수>
CMP   W0,#0
B.EQ/B.NE ...
```

이 패턴에서 `BL` 직후의 조건분기가 실제 검사 결과를 다음 경로로 보내는 지점일 가능성이 높다.

특히 `CBZ/CBNZ`는 함수 반환값 검사에 유용하고, `TBZ/TBNZ`는 객체 내부 flag 검사일 가능성이 높으므로 구분한다.

---

## Ghidra Python/Jython 문제

기존 Jython 스크립트로 `BL → CBZ/CBNZ/TBZ/TBNZ`를 자동 추출하려 했으나 현재 Ghidra 환경에서는 Python/Jython 기능을 사용할 수 없다.

따라서 Ghidra 내부 Python을 전제로 하지 않는다.

### Codex에서 권장
외부 Python + ARM64 disassembler(예: Capstone)를 사용해:
1. ELF/LOAD segment 확인
2. `.text` 분석
3. `BL` 검색
4. 다음 1~4 instruction 안의 `CBZ/CBNZ/TBZ/TBNZ` 검색
5. `BL → CMP → B.EQ/B.NE` 검색
6. 후보의 RVA/target/branch target/instruction sequence 출력

---

## RVA와 파일 offset 주의

ELF에서는 RVA와 file offset을 동일하게 취급하지 않는다.

LOAD segment 기준으로:

```text
file_offset =
    RVA - segment_virtual_address
    + segment_file_offset
```

실제 `libil2cpp.so`의 ELF program headers를 확인한 뒤 계산한다.

Hex editor에서 주소를 수정할 때는 반드시 이 변환을 먼저 검증한다.

---

## 패치 전략

현재는 패치하지 않는다.

가장 좋은 최종 후보는:

```text
업데이트 필요 여부 계산
        ↓
반환값
        ↓
그 직후 조건분기
        ↓
업데이트/실패 경로
```

여기서 **최소한의 분기만** 로컬 정상 경로로 보내는 것.

피해야 할 방식:
- `FUN_00EE86B4` 무조건 1 반환
- `FUN_02104534` 무조건 1 반환
- 전체 CheckAssets return 고정
- Cache/Build 검사 전체 제거

이런 방식은 로컬 리소스 초기화까지 깨뜨릴 수 있다.

---

## 현재 확정 사항

- 버전 체크 이후 리소스 업데이트 확인 단계까지 진행됨
- `noNeed` 관련 처리는 유지
- `FUN_02104534`는 상태 집계
- `FUN_00EE86B4`는 상태 배열 getter
- `FUN_016807A0`은 상태 집계 결과에 따라 분기
- FDE XREF는 호출자가 아님
- Ghidra 함수명은 익명
- `0x01681980`, `0x01681DF0`은 MoveNext/callback으로 확정하지 않음

## 아직 찾아야 하는 것

- 실제 `CheckAssets_d__75::MoveNext` RVA
- 실제 `isManifestNeedUpdate` RVA
- 실제 `isAssetNeedUpdate_CheckCacheAndBuild` code address
- `OnUpdateFail` 호출 지점
- 업데이트 실패 직전 조건분기
- 로컬 Cache/Build 정상 경로

---

## Codex에서 다음 작업

가장 먼저 다음을 자동화한다:

```text
libil2cpp.so
    ↓
ELF LOAD segment 확인
    ↓
AArch64 .text 추출
    ↓
BL → CBZ/CBNZ/TBZ/TBNZ 검색
    ↓
BL → CMP → B.EQ/B.NE 검색
    ↓
후보 CSV/텍스트 출력
```

각 후보 출력 형식:

```text
caller_start
BL_RVA
BL_target_RVA
branch_RVA
branch_target_RVA
instruction_sequence
```

그 결과를 가지고 업데이트 관련 후보만 다시 좁힌다.

## 현재 패치하지 않을 주소/함수

```text
0x016807A0
0x01681958
0x01681980
0x01681DF0
FUN_02104534
FUN_00EE86B4
```

이들은 현재 분석 대상일 뿐 실제 패치 지점으로 확정되지 않았다.
