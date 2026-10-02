# 2026-10-02 ProtoUser / DictI32 / ItemRecord 후속 분석

## 범위
- 서버 데이터 생성/수정 제외
- 클라이언트의 Deserialize 이후 객체 변환, 상태 저장, Main UI 소비 경로만 분석
- 기준 Git 자료: `research/reports/2026-10-02-Bootstrap-Client-State-MainUI-연결분석.md`, `research/reports/2026-10-02-Bootstrap-OpCode2-Response-계약-초안.md`, `research/Ghidra_Listing_txt/AL`, `research/Ghidra_Listing_txt/US.txt`

## A. ProtoUser → UserInfo

### 확인된 ProtoUser getter / 객체 offset
| ProtoUser property | getter RVA | object offset |
|---|---:|---:|
| Id | 015adb0c | +0x10 |
| Level | 015adb2c | +0x1C |
| Exp | 015adb3c | +0x20 |
| HeadIcon | 015adb6c | +0x2C |
| Name | 015adb7c | +0x30 |

각 getter Listing은 해당 객체의 offset에서 값을 읽어 반환한다.

### 변환 경로
```
OpInfo +0x88 (field 35 User / ProtoUser)
  → UserInfo.ctor @ 00dd2f44
  → DataTool.CopyTo<ProtoUser, UserInfo>
  → DataCenter +0x28 (UserInfo)
```

UserInfo 기본 속성과 DictI32 vary 값은 같은 UserInfo 객체에 서로 다른 경로로 반영된다.

- ProtoUser 기본 필드: CopyTo 경로
- DictI32: UserInfo.MergeVaryData @ 00dd3030 경로

**미확정:** 위 ProtoUser 객체 offset은 C# 객체 메모리 배치다. protobuf wire tag 번호와 동일하지 않다. 현재 확보한 getter Listing만으로 ProtoUser의 tag 번호를 단정하지 않는다. 다음 단계는 ProtoUser의 generated serializer/parser 또는 protobuf metadata에서 tag ↔ property 대응을 찾는 것이다.

## B. DictI32 음수 Key 및 Main UI 소비처

운영 PCAP 기준 field 21 DictI32 음수 key 13종:
- MergeVaryData 처리 key: -9, -10, -11, -12, -13, -14, -15, -16, -18, -30, -31, -32, -34
- PCAP에서 실제 확인된 MergeVaryData 대상: -18=ExamTimes(15), -30=EquipMax(0), -31=ChargeTotalPerMonth(0), -32=Age(27), -34=ChatChannel(1)
- MergeVaryData 대상이지만 해당 캡처에 없는 key: -9, -10, -11, -12, -13, -14, -15, -16
- 그 외 field 21 음수 key: -29, -28, -27, -23, -22, -20, -33, -36. 이들은 MergeVaryData Listing에서 처리되지 않으므로 UserInfo 속성으로 연결하지 않는다.

### Main UI에서 확인된 유사 key 소비 사례
`HomePanelMono.Start @ 00f67adc` → `RefreshPoint_Mail` 경로에서 DataCenter cache +0xC0 Dictionary의 key -27 검사 및 메일 숫자 표시가 확인된다.

주의: 이 DataCenter +0xC0 Dictionary는 OpInfo +0x70 DictI32와 다른 저장 객체/offset 문맥이다. key 숫자가 -27로 같다는 이유만으로 field 21 DictI32의 -27이 Mail badge로 직접 연결된다고 결론 내리지 않는다.

그 외 field 21의 미분류 음수 key 7종(-29, -28, -23, -22, -20, -33, -36)의 Main UI 소비처는 아직 미확정이다. 양수 key도 263개이며, 개별 소비처는 추가 추적 대상이다.

## C. ItemRecord type 8 참조 ID

현재 Git의 `10_record_type_inventory.md`에서는 ItemRecord가 952개이고 필드에 `m_id`, `m_itemPackageId`, `m_type` 등이 존재하는 것까지 확인된다.

기존 원본 Record 재검증 보고서의 Chapter Box 표본은 다음과 같다.
| Item ID | m_type | m_itemPackageId |
|---:|---:|---|
| 43000001 | 0 | empty |
| 43000002 | 0 | empty |
| 43001000 | 7 | empty |
| 43100002 | 1 | 45100020\|45100021\|45100022 |
| 43200003 | 4 | empty |

이 표본에는 m_type=8인 ItemRecord가 없다. 따라서 type 8의 의미나 참조 ID namespace를 현재 표본으로 추정하지 않는다.

다음에는 Git에 등록된 원본 ItemRecord JSON의 blob SHA를 확보해 m_type=8 레코드 전체를 추출하고, 해당 레코드의 m_id / m_itemPackageId / m_location / m_nameId / m_describeId를 교차 확인한다. 이후 참조 대상 ID가 ItempackageRecord, ItemboxRecord 또는 다른 Record인지 실제 ID 일치로 판정한다.

## 다음 작업
1. ProtoUser의 generated protobuf tag metadata/parser를 찾아 Id/Level/Exp/HeadIcon/Name의 wire tag 확정.
2. field 21의 미분류 음수 key와 양수 key 중 Main UI getter/Calls IN에 연결되는 항목만 추적.
3. HomePanel의 Mail badge key -27은 field 21과 분리된 DataCenter cache 입력/생성 경로를 확인.
4. ItemRecord 원본 blob에서 m_type=8 전체 레코드와 참조 ID를 추출하고 대상 Record type까지 닫는다.

## 판정 원칙
- 객체 offset ≠ protobuf tag
- 동일한 숫자 key라도 서로 다른 Dictionary/cache이면 별도 경로로 취급
- Record의 필드명만으로 참조 의미를 확정하지 않고 실제 ID join 및 호출/소비 증거를 요구
- 서버 데이터 생성/수정은 분석 범위에서 제외
