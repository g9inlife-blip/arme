# 2026-10-02 던전 입장 요청 경로 추적

## 목적
Energy 수치/회복 경로 분석은 중단한다. Energy는 서버 권한 데이터이며 클라이언트의 값 변경은 UI 표시 및 사전 조건에만 영향을 줄 수 있다. 이 작업은 실제 던전 입장 요청과 서버 응답 계약을 확인하는 데 집중한다.

추적 순서:
```
던전/Section 선택
 → Ready 화면
 → 입장 버튼 사전 조건
 → 실제 Request 생성
 → KCP 송신
 → 서버 응답
 → Client response 처리
 → 전투 화면 전환 또는 거절 안내
```

## 1. Git 자료 확인
기준 저장소: `g9inlife-blip/arme`
확인한 기존 문서:
- `research/reports/2026-09-29-인게임-네트워크-경로-분석.md`
- `research/reports/2026-10-02-Bootstrap-OpCode2-Response-계약-초안.md`
- `research/reports/2026-10-02-로컬서버-중심-분석범위-작업원칙.md`
- `research/Ghidra_Listing_txt/RE.txt`
- `research/Ghidra_Listing_txt/DA.txt`
- `research/Ghidra_Listing_txt/CS.txt`
- `research/Ghidra_Listing_txt/CH.txt`
- `research/PCAP`의 기존 PCAP 및 변환 JSON 목록

## 2. 입장 버튼 사전 조건 — 정적 확인

### 2.1 ReadyMono.RefreshBtnState
- RVA: `00e5e86c`
- 목적: Ready 화면 입장 버튼 상태 갱신
- Calls OUT:
  - `ReadyMono.get_sectiondata @ 00e5cdb0`
  - `DataCenter.IsTaskMission @ 016de974`
  - `UserInfo.get_Energy @ 00dd2ce4`
  - ReadyPanel의 `lbl_cost` 접근 및 Text 갱신
- Assembly에서 현재 Energy와 Section 데이터의 `+0xA0` 값을 비교하는 분기가 확인된다.
- 이 경로는 클라이언트의 버튼/비용 표시 및 사전 조건 판단으로 분류한다. 서버의 최종 입장 승인 근거로 해석하지 않는다.

### 2.2 ReadyMono.InitReady
- RVA: `00e5dec0`
- Ready 화면 초기화 함수
- Calls OUT에 다음이 확인된다.
  - `DataCenter.IsSectionOpening @ 016e7f08`
  - `BaseExtensions.IsOpenChapter @ 00e1bf8c`
  - `ReadyMono.RefreshBtnState @ 00e5e86c`
  - `ReadypanelNode.get_btn_startbattle`
  - `ReadypanelNode.get_btn_startbattle_gray`
  - 버튼/이벤트 리스너 연결 계열
- 따라서 Ready 진입 시 Section 개방 상태 및 버튼 UI가 구성된다.

### 2.3 ReadyMono.ClickEnterBattle
- RVA: `00e63570`
- Calls OUT에 `DataCenter.IsSectionOpening`, `BaseExtensions.IsOpenChapter`, Section data 조회, 날짜 비교, TextTips/Notify 등이 확인된다.
- Listing의 클릭 처리 자체에는 `ProtocolGame_SendRequest.CreateBattle`, `CSBehaviour.RequestOp`, `NetworkCenter.Send` 직접 호출이 나타나지 않는다.
- 조건에 따라 안내/Notify 경로로 빠지는 분기가 존재한다.
- 따라서 클릭 함수만으로 실제 서버 요청이 발생한다고 단정하지 않는다. callback/delegate 또는 GoToBattle 계층으로 이어지는 후속 경로를 찾아야 한다.

## 3. 실제 전투 시작 Request — 기존 정적 계약 재확인

기존 `2026-09-29-인게임-네트워크-경로-분석.md`의 Listing 분석 결과:

대상: `ProtocolGame_SendRequest.CreateBattle @ 00dded04`

```
OpInfo +0x14 = 0x16
OpInfo +0x30 = w0
OpInfo +0x34 = w1
CSBehaviour.RequestOp(OpInfo)
```

현재 확정된 계약:
- Opcode: `0x16`
- Payload: 32-bit 인자 2개
- 저장 위치: OpInfo `+0x30`, `+0x34`
- 두 인자의 구체적인 의미는 아직 이 보고서에서 확정하지 않는다.

전송 계층은 기존 보고서의 공통 경로를 따른다.

```
ProtocolGame_SendRequest.CreateBattle
 → CSBehaviour.RequestOp
 → NetworkCenter.Send
 → Request queue
 → Tube Send
```

## 4. 현재 증거와 미확정 사항

| 항목 | 상태 |
|---|---|
| Ready 버튼 상태 갱신 함수 | 정적 확인 |
| Energy/Section의 클라이언트 사전 조건 참조 | 정적 확인 |
| 실제 전투 시작 함수 | CreateBattle @ 00dded04 확인 |
| CreateBattle Opcode | 0x16 확정 |
| Request payload 크기/위치 | u32 2개, +0x30/+0x34 확정 |
| ClickEnterBattle → CreateBattle 호출 연결 | 미확정 |
| 두 payload 인자의 실제 의미 | 미확정 |
| KCP runtime에서 던전 입장 Request/Response 상관관계 | 미확정 |
| 성공 응답 후 전투 화면 전환 조건 | 미확정 |
| 서버 거절 응답과 UI 안내 매핑 | 미확정 |

## 5. 다음 작업

1. `ReadyMono.ClickEnterBattle`가 전달하는 callback/delegate 및 화면 전환 계층을 추적한다.
2. `GoToBattleMono`의 CreateBattle 계열 함수에서 실제 `ProtocolGame_SendRequest.CreateBattle` 호출 및 인자 생성 지점을 찾는다.
3. `CreateBattle`의 두 u32 값이 어떤 Section/Chapter/Mission ID인지 실제 호출자에서 확정한다.
4. 기존 `research/PCAP`의 변환 JSON 중 던전 선택/전투 시작 캡처에서 Opcode `0x16` 요청과 응답을 찾아 시간/SerialNumber 기준으로 연결한다.
5. runtime hook은 `ProtocolGame_SendRequest.CreateBattle`, `KCPTube.Send`, `KCPTube.TryRead`, `NetworkCenter.TryHandleResponse`, `DataCenter.ProccessRequestRes` 경계만 우선 관찰한다.
6. 성공 응답 후 전투 씬 진입, 실패 응답 후 안내 UI를 확인한다.

## 분석 원칙
- Energy의 회복/증가 알고리즘은 더 추적하지 않는다.
- 클라이언트 Energy는 버튼 상태/표시용 사전 조건으로만 기록한다.
- 실제 소모/입장 가능 여부는 서버 권한 처리로 분리한다.
- 정적 Listing, runtime hook, PCAP 관측 결과를 서로 구분해 기록한다.
- 서버 요청/응답 계약이 확정되면 내부 UI 구현의 세부 추적을 종료한다.
