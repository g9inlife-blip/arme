# Current State

## Game
- Package: `com.thumbage.heroes.google`
- Engine: Unity / IL2CPP
- Architecture investigated: ARM64

## Runtime status (latest verified)
현재까지의 실제 실행 결과를 기준으로 다음 상태를 확정한다.

### 1. 업데이트 우회
- 업데이트 진입/실패를 일으키는 기존 온라인 업데이트 경로에 대한 우회 패치가 적용된 상태다.
- 따라서 **업데이트 우회 자체는 현재 성공(O)** 으로 기록한다.
- 단, 이것은 게임 전체의 온라인 의존성을 제거했다는 의미가 아니다.

### 2. 온라인 실행
- 온라인 상태에서는 기존에 등록되어 있는 계정정보를 이용해 로그인된다.
- 즉, 현재 빌드에서는 등록 계정정보와 온라인 서버를 이용하는 기존 로그인/데이터 처리 경로가 살아 있다.

### 3. 오프라인 실행
- 오프라인 상태에서는 업데이트 우회 후에도 메인 메뉴 접근에 실패한다.
- 따라서 업데이트 게이트를 제거한 뒤에도 **로그인 이후 또는 메인 메뉴 진입 과정에서 필요한 네트워크 데이터/상태 처리가 남아 있음**을 확인했다.

### 4. 현재 해석
현재 상태는 다음과 같이 정의한다.

`업데이트 우회 O → 게임 실행 경로 진입 O → 네트워크 데이터 처리 의존성 잔존 → 오프라인 메인 메뉴 진입 실패`

즉, 현재 패치는 '업데이트 서버 의존성'만 일부 제거했으며, **게임 서비스/계정/메뉴 데이터의 온라인 의존성은 아직 처리 중**이다.

---

## 핵심 아키텍처 가설
최근 실제 실행 관찰에 따라 기존의 단순 '업데이트 서버 우회' 관점에서 다음 구조를 조사 기준으로 채택한다.

온라인 상태에서 관찰되는 패턴:

`로그인 → 네트워크 로딩 → 메인 화면 → 네트워크 로딩 → 상점 → 네트워크 로딩 → 맵 → 네트워크 로딩 → 맵 상세 → 네트워크 로딩 → 전투 → 네트워크 로딩 → 전투 결과 → 네트워크 로딩 → 특가상점 → 네트워크 로딩 → 뽑기 ...`

메뉴가 표시된 이후에는 데이터를 메모리에서 사용하더라도, **메뉴/기능 진입과 행동 결과의 경계에서 서버 통신이 반복되는 구조**로 보인다.

특히 다음 관찰을 중요한 증거로 취급한다.

- 로컬에서 보이는 재화 값을 변경해도 결과 처리 시 서버 상태가 기준이 되는 현상이 관찰됨.
- 따라서 클라이언트의 현재 메모리 값만 변경하는 것으로는 서버 authoritative state를 대체할 수 없다.
- 로컬 Save 파일이 존재하는지 여부는 아직 미확정이며, 존재한다고 가정하지 않는다.
- 오프라인화의 핵심은 단순 Save 파일 생성이 아니라 **서버가 제공하던 상태 조회, 상태 변경, 결과 판정, 영속 저장 역할을 로컬에서 대체하는 것**으로 정의한다.

### 오프라인 목표 구조

`Static Game Data`

`+ Local Game State / Save Data`

`+ 기존 Game Manager / Data Model`

`+ 필요한 경우 기존 게임 로직`

`→ 기존 UI / Gameplay`

온라인의 `Server Request → Response → Deserialize → Manager → UI/Game Logic` 흐름을 가능한 한 유지하고, 서버가 제공하던 입력을 로컬 데이터/로컬 결과로 공급하는 방향을 우선한다.

---

## Confirmed GameUpdateService structure
`AliothEngine.GameUpdateService`

주요 필드:
- `m_isReady` @ `0x19`
- `downloaders` @ `0x20`
- `downloadedCount` @ `0x28`
- `AllNeedDownloadCount` @ `0x2C`
- `downloadedSize` @ `0x30`
- `AllNeedDownloadSize` @ `0x38`
- `m_Download_Percentage` @ `0x40`
- `OnUpdateSucess` @ `0x48`
- `OnPackUpdate` @ `0x50`
- `OnAssetUpdate` @ `0x58`
- `OnUpdateFailed` @ `0x60`
- `OnStepChanged` @ `0x68`
- `AssetBundlesNeedUpdateList` @ `0x70`
- `UpdateTypeResult` @ `0x78`
- `m_UpdateSteping` @ `0x7C`
- `UpdateStepDescription` @ `0x80`
- `BuildVersion` @ `0x88`
- `remoteAssetVersion` @ `0x90`
- `remoteBaseAssetURL` @ `0x98`

### UpdateStep
`WaitEngineInit=0`, `GetNativeVersion=1`, `VersionCheck=2`, `GetBestCDN=3`, `DownloadAssetBundleMainfest=4`, `GetAssetBundleNeeds=5`, `StartAssetBundleUpdate=6`, `Finish=7`

### UpdateType
`NoNeed=0`, `PackUpdate=1`, `AssetUpdate=2`

## Confirmed network-dependent methods
- `StartDownLoadAssetBundleMainfest.MoveNext` = `0x16834D8`
- `StartGetAssetNeedUpdate.MoveNext` = `0x168369C`

두 coroutine 모두 원격 요청을 구성하고 `0x291A9E8` 계열 호출 및 callback 경로를 사용한다.

## Confirmed startup state machine
`GameUpdateService.Start.MoveNext` = `0x1682CA0`

확인된 흐름:
- ready 상태 확인
- UpdateStep 4 설정
- `StartDownLoadAssetBundleMainfest` 진입
- 이후 UpdateStep 5 설정
- `StartGetAssetNeedUpdate` 진입

즉 manifest 단계와 asset-needs 단계가 독립적인 온라인 게이트다.

## Version-check callback
`<StartVersionCheckUpdate>b__57_0` = `0x1680F68`
- result 0 → `OnUpdateSucess`
- result 1 → `OnPackUpdate`
- result 2 → `OnAssetUpdate`

`<StartVersionCheckUpdate>b__57_1` = `0x1681158`는 Exception 처리 및 `_OnUpdateFail` 경로와 연결된다.

## Important caution
`get_isUseRemoteAsset` = `0x167E380`은 hotfix delegate를 먼저 확인하고 없으면 `true`를 반환하는 bridge다. 단순히 false로 패치한다고 해서 전체 업데이트 흐름이 오프라인화된다고 가정하면 안 된다.

## Known method RVAs
- `StartAssetCheck` = `0x16802F8` (decimal 23588184)
- `StartGetAssetNeedUpdate` = `0x1680D58` (23590840)
- `StartCheckAssets` = `0x1681B40` (23594304)
- `CheckAssets` = `0x1681BD8` (23594456)
- `isPackNeedUpdate` = `0x1681CD0` (23594704)
- `isAssetNeedUpdate_OnlyCheckVerion` = `0x1681D54` (23594836)
- `isAssetNeedUpdate_CheckCacheAndBuild` = `0x1681E68` (23595112)
- `<StartGetAssetNeedUpdate>b__58_0` = `0x16828AC` (23597804)
- `GameUpdateService.<>c::<CheckAssets>b__75_2` = `0x1682F40` (23599488)
- `GameUpdateService.<>c::<CheckAssets>b__75_1` = `0x1682FA0` (23599584)
- `DisplayClass75_0::<CheckAssets>b__0` = `0x1683028` (23599720)
- `CheckAssets.d__75.MoveNext` = `0x1683230` (23600624)
- `StartAssetCheck.d__49.MoveNext` = `0x1684514` (23604948)
- `StartGetAssetNeedUpdate.d__58.MoveNext` = `0x168521C` (23606940)
- `StartVersionCheckUpdate` factory = `0x167F6EC`
- `<StartVersionCheckUpdate>b__57_0` = `0x1680F68`
- `<StartVersionCheckUpdate>b__57_1` = `0x1681158`
- `<StartVersionCheckUpdate>b__57_2` = `0x16812EC`
- `Start.d__68.MoveNext` = `0x1682CA0`
- `StartDownLoadAssetBundleMainfest.d__62.MoveNext` = `0x16834D8`
- `StartGetAssetNeedUpdate.d__58.MoveNext` = `0x168369C`
- `_OnUpdateSuccessIE.d__66.MoveNext` = `0x1684C00`

---

## Revised development plan
### Phase 1 — Update gate
Status: **O / bypass patched**

목표: 초기 업데이트 실패 때문에 게임 진입 자체가 막히는 문제를 제거한다.

### Phase 2 — Online Data Flow Discovery
Status: **NEXT**

목표: 업데이트 이후 오프라인 메인 메뉴 진입을 막는 네트워크 데이터 처리의 실제 흐름을 증명한다.

우선 다음 공통 경로를 찾아야 한다.

`Request → Network → Response/Callback → Deserialize/Parser → Data Object → Manager/Singleton → UI or next state`

특히 로그인/메인 메뉴 진입 경계부터 조사한다.

### Phase 3 — Local State Bootstrap
목표: 서버에서 처음 받아오던 계정/플레이어 상태를 로컬에서 초기화할 수 있는 최소 데이터 세트를 만든다.

### Phase 4 — Menu Data Providers
목표: 상점/맵/맵 상세 등 메뉴 진입 시 서버에서 받는 데이터를 기존 Data Model/Manager에 로컬로 공급한다.

### Phase 5 — State Mutation / Result Processing
목표: 구매, 전투 결과, 보상, 뽑기 등에서 서버가 수행하던 상태 변경/판정 결과를 로컬에서 처리한다.

### Phase 6 — Persistence
목표: 플레이어 상태를 로컬 Save/Load로 영속화한다.

주의: 실제로 어떤 데이터를 저장해야 하는지는 Phase 2~5에서 확인한 Data Model을 근거로 결정한다. 처음부터 임의의 거대 Save 파일을 만들지 않는다.

### Phase 7 — Runtime Validation
목표: 재실행 후에도 계정/재화/캐릭터/진행도/인벤토리 등 필요한 상태가 유지되는지 사용자 화면 확인으로 검증한다.

---

## Immediate next target
**TASK-003 — 로그인 → 메인 메뉴 데이터 흐름 및 네트워크 의존성 증명**

이번 단계에서는 수정하지 않는다.

핵심 질문:
1. 온라인 로그인 성공 응답이 어떤 데이터 객체로 변환되는가?
2. 그 데이터가 어느 Manager/Singleton에 저장되는가?
3. 메인 메뉴 진입 직전/직후 어떤 네트워크 요청이 발생하는가?
4. 그 응답이 어떤 객체/상태를 채우는가?
5. 오프라인에서 메인 메뉴 진입 실패가 어느 callback/state transition에서 발생하는가?
6. 해당 데이터가 기존 로컬 캐시/PlayerPrefs/DB/파일에 이미 일부 존재하는가?
7. 존재하지 않는다면 최소한 어떤 서버 응답을 로컬에서 공급해야 하는가?

**수정 금지. 먼저 데이터 흐름을 증명한다.**
