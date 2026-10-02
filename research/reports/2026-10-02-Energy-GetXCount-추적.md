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