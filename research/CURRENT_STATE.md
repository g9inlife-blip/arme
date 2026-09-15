# Current State

## Game
- Package: `com.thumbage.heroes.google`
- Engine: Unity / IL2CPP
- Architecture investigated: ARM64

## Runtime observation
기존 APK는 시작 시 업데이트 확인을 수행한다. 관찰된 흐름은 대략 다음과 같다.

`startup → update check → resource file update message → failure`

따라서 단일 버전 체크만 우회해서는 충분하지 않다.

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

## Immediate investigation target
Do not patch yet. Prove the actual scene transition path from the existing startup/entry functions to the real Unity scene-loading implementation. See `research/targets/TASK-001.md`.
