# 2026-10-02 Energy GetXCount 추적

## 결론

`UserInfo.get_Energy @ 00dd2ce4`는 UserInfo 직접 저장값이 아니다.

```text
UserInfo.get_Energy
  → DataCenter.GetXCount @ 016defb0
  → key 0x029020C3
```

Assembly에서 GetXCount 호출 인자는 다음으로 확인된다.

- w1 = 0x029020C3
- w2 = 0
- w3 = 0

기존 GetXCount 분석에서는 DataCenter `+0x78` Dictionary 계열을 조회하는 것으로 확인됐다.

## Bootstrap 연결

```text
OpInfo +0x98 Items
  ↓
DataCenter.MergeItem @ 016e4700
  ↓
Item/category cache (+0x78 계열)
  ↓
GetXCount(0x029020C3)
  ↓
UserInfo.get_Energy
```

따라서 Local Server에서 Energy를 UserInfo 고정 offset으로 모델링하지 않는다.

## EnergyNextTime

`ProccessRequestRes @ 016e203c`는 `DataCenter.set_EnergyNextTime @ 016ded44`를 직접 호출한다.

`DataCenter.get_EnergyNextTime @ 016decdc`는 GUI update 계층에서 사용된다.

즉:

- Energy 수량: `GetXCount(0x029020C3)`
- Energy 회복시각: `EnergyNextTime`

두 상태를 분리한다.

## 다음 작업

1. `GetXCount @ 016defb0` 본문에서 실제 Dictionary 조회와 기본값 확정
2. `0x029020C3`가 실제 ProtoItem/원본 JSON의 어떤 항목인지 Git 데이터 대조
3. `HomePanelMono.Start @ 00f67adc` 직접 getter 목록 확정
4. 결과를 Bootstrap 필수/선택 필드에 반영
## 2. GetXCount 본문 확인

`DataCenter.GetXCount @ 016defb0`는 `this + 0x78`만 단순 조회하는 함수가 아니다. `itemId`와 내부 BaseData의 type을 함께 사용해 재화/아이템 종류별 조회 경로를 분기한다.

핵심 Assembly:

```text
this              = x19
itemId            = w20
mode/flag         = w21
BaseData lookup   = DataManager.TryGetBaseData(itemId)
BaseData.type     = [BaseData + 0x24]
```

확인된 분기 중 일반 Item 경로는 `this + 0x78` Dictionary를 사용한다.

```text
this + 0x78
  → Dictionary<int, object>
  → key별 collection
  → ProtoItem 계열 값
  → Count @ +0x18
```

또한 type에 따라 `+0x40`, `+0x60`, `+0x80` 등의 다른 DataCenter collection을 사용하며, Stigmata/Weapon/Equip 상태도 이 함수에서 별도 처리한다.

따라서 `GetXCount`는 단순 `Items[itemId].Count` 함수가 아니라 BaseData.type을 기준으로 여러 상태 저장소를 통합 조회하는 공통 수량 함수다.

## 3. Energy / Crystals key

기존 Git 분석과 `UserInfo.get_Energy` Assembly를 결합하면:

```text
Energy   = itemId 0x029020C3
Crystals = itemId 0x029020C2
```

따라서 로그인 직후 Main의 재화 표시를 만들 때 UserInfo의 Coins/Energy/Crystals를 모두 직접 필드로 만들면 안 된다. 최소한 Energy/Crystals는 `GetXCount` 공통 경로를 재현해야 한다.

## 4. HomePanelMono.Start 현재 확인 수준

`HomePanelMono.Start @ 00f67adc` 자체의 전체 Listing은 현재 검색 결과에서 직접 확보하지 못했다.

대신 Calls IN/OUT와 별도 함수 Listing에서 다음은 확정됐다.

- `DataCenter.get_CurrentEquipMax @ 016de53c` → HomePanelMono.Start
- `DataCenter.get_NextEquipMax @ 016de648` → HomePanelMono.Start
- `DataCenter.get_EquipMax @ 016de7cc` → HomePanelMono.Start
- `Ali.get_dataCache @ 00e014f4` → HomePanelMono.Start
- `Ali.GetExcelDic<object> @ 01737100` → HomePanelMono.Start 계열

따라서 현재 Main Bootstrap 우선순위는:

```text
Items / 재화 상태
Energy 0x029020C3
Crystals 0x029020C2
UserInfo Id/Name/Level/Exp
EquipMax / CurrentEquipMax / NextEquipMax
Chapters / Sections
Hero / Weapon / Equipment
```

로 유지한다.

## 5. 다음 작업

1. `0x029020C3`의 BaseData.type과 원본 Item/Excel 데이터 직접 대조
2. `GetXCount`의 type별 collection mapping을 표로 완성
3. `HomePanelMono.Start` body를 함수명/주소 기준으로 직접 확보
4. Main에서 실제 표시되는 Coins/Crystals/Energy를 동일 방식으로 묶어 Bootstrap fixture 설계