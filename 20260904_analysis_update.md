# 2026-09-04 분석 추가 기록

## 1. `AssetInfoManager::get_AssetBundle` 실제 구현 확정

주소:
```text
0x018E75B8
```

native getter 핵심:
```asm
018e75ec 08 23 01 b0     adrp x8,0x3d48000
018e75f0 08 d5 42 f9     ldr  x8,[x8,#0x5a8]
018e75f4 08 01 40 f9     ldr  x8,[x8]
018e75f8 08 5d 40 f9     ldr  x8,[x8,#0xb8]
018e75fc 00 39 40 f9     ldr  x0,[x8,#0x70]
018e7600 c0 00 00 b4     cbz  x0,LAB_018e7618
```

`AssetInfoManager_TypeInfo +0xb8 +0x70`은 `get_AssetBundle`의 Lua delegate slot이다.

delegate가 없으면:
```asm
018e7618 60 1a 40 f9     ldr x0,[x19,#0x30]
018e7624 c0 03 5f d6     ret
```

따라서 native 기준:
```text
AssetInfoManager +0x30 = AssetBundle
```

## 2. `set_AssetBundle`도 동일 backing field 사용

주소:
```text
0x018E7628
```

핵심:
```asm
018e7698 93 1a 00 f9     str x19,[x20,#0x30]
```

즉:
```text
set_AssetBundle(value)
 -> this +0x30 = value
```

따라서 getter/setter 모두 `AssetInfoManager +0x30`을 사용한다.

## 3. `get_AssetBundleInfos`와의 관계

별도로 확인된:
```c
AssetInfoManager::get_AssetBundleInfos()
{
    ...
    return *(undefined8 *)(param_1 + 0x30);
}
```

따라서 native 구현만 놓고 보면:
```text
AssetInfoManager.AssetBundle
AssetInfoManager.AssetBundleInfos
        ↓
      +0x30
```
을 공유한다.

단, 두 getter 모두 Lua delegate override가 가능하므로 런타임에서는 Lua 반환값이 native field와 다를 수 있다.

## 4. `SaveLatestVersion`과의 연결

`GameUpdateService::SaveLatestVersion`에서:
```asm
0177f064  bl  AssetInfoManager$$get_AssetBundle
0177f068  cbz x0,LAB_0177f0c8
...
0177f0b0  ldr x0,[x19,#0x10]
0177f0c4  b   AssetVersionManager$$set_AssetVersionSaved
```

따라서 native 의미는:
```c
var bundle = AssetInfoManager.get_AssetBundle();
if (bundle != null)
    AssetVersionManager.set_AssetVersionSaved(
        *(string *)(bundle + 0x10)
    );
```

즉 `AssetVersionSaved`는 업데이트 성공 후 `AssetInfoManager.AssetBundle` 객체의 `+0x10` 값을 PlayerPrefs에 저장한다.

**아직 미확정:** `AssetInfoManager +0x30`에 들어가는 실제 객체의 class/type과 그 객체 `+0x10` 필드의 정확한 이름/의미.

## 5. `SaveLatestVersion` 호출 시점

`GameUpdateService.<>d__66::MoveNext`에서 `UpdateType == 2`일 때 리소스 업데이트 단계로 진입하고, 성공 후 state 1에서 `SaveLatestVersion()`이 호출된다.

정확한 순서:
```text
UpdateType 2 결정
    ↓
실제 리소스 업데이트
    ↓
업데이트 성공
    ↓
SaveLatestVersion()
    ↓
AssetInfoManager.AssetBundle +0x10
    ↓
PlayerPrefs["AssetVersionSaved"] 갱신
```

따라서 `SaveLatestVersion()`은 최초 UpdateType 2 발생 원인이 아니며, 선행 호출하도록 패치하지 않는다.

## 6. 현재 핵심 추적 대상

다음 순서로 분석한다.

1. `AssetInfoManager.set_AssetBundle()` 호출 XREF를 찾아 AssetBundle 객체가 언제 생성/설정되는지 확인.
2. 해당 객체의 실제 class/type을 확인하고 `+0x10` 필드가 version string인지 확인.
3. `GameUpdateService::DownloadUpdate`에서 생성하는 `System.Action<bool>`의 실제 callback method body를 추적.
4. callback(false)가 어떤 경로로 `OnUpdateFail`까지 전달되는지 확인.
5. `GameUpdateService_TypeInfo +0xb8 +0x158 / +0x160` Lua delegate 존재 여부를 확인.
6. 실제 런타임 cache의 다음 파일 상태를 확인:
```text
persistentDataPath/AssetBundles/Android/Android.version
persistentDataPath/AssetBundles/Android/AssetBundleInfoFile.json.version
```

## 7. 패치 보류

다음은 현재 원인 확인 전 수정하지 않는다.
- `get_AssetBundle()` 수정
- `AssetInfoManager +0x30` 수정
- `AssetBundle +0x10` 임의 수정
- `SaveLatestVersion()` 선행 호출
- callback 성공 flag 강제

현재 목표는 **실제 callback 실패 경로를 먼저 확정하는 것**이다.
