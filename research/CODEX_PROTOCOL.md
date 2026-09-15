# Codex Operating Protocol

## 역할
Codex는 이 프로젝트의 **로컬 역분석/실행 담당자**다. Ghidra, APK, `libil2cpp.so`, `global-metadata.dat`, ADB/emulator 등 실제 파일과 도구를 로컬에서 다룬다.

GPT는 Codex가 수행한 조사 결과를 읽고 다음 조사 방향과 패치 전략을 결정한다.

## 절대 원칙
1. 조사 단계에서는 수정하지 않는다.
2. 주소/함수/호출 관계를 추측으로 확정하지 않는다.
3. `SceneManager.LoadScene` 같은 의미를 이름만으로 단정하지 않는다.
4. 가능하면 Ghidra decompile + assembly + XREF를 함께 기록한다.
5. 간접 호출이면 함수 포인터/테이블/델리게이트/metadata 관계까지 추적한다.
6. 네트워크 함수가 발견되면 호출 위치, 성공 callback, 실패 callback을 함께 기록한다.
7. 패치 전에는 반드시 '무엇을 우회하고 무엇은 유지하는가'를 명시한다.
8. 기존 동작을 덮어쓰기 전에 원본 파일을 로컬에서 보존한다. 원본 바이너리는 Git에 올리지 않는다.

## 조사 결과 문서 규격
모든 TASK 결과는 `research/reports/TASK-xxx-result.md`에 기록한다.

필수 항목:
- 조사 목적
- 실행한 명령/도구
- 대상 주소와 함수명
- callers
- callees
- 관련 문자열/XREF
- 핵심 assembly
- 핵심 decompile
- 확인된 사실
- 아직 불확실한 부분
- 다음 조사 제안

## 주소 표기
가능하면 다음을 모두 기록한다.
- RVA
- Ghidra address
- IL2CPP method name
- 관련 metadata 이름

## 수정 작업 규칙
패치 TASK에서는 다음을 반드시 기록한다.
- 원본 동작
- 변경 지점
- 변경 opcode/바이트 또는 source-level 변경
- 변경 이유
- 예상 효과
- 부작용 가능성
- 빌드/서명 절차
- 자동 검증 결과

## Git 규칙
Git에는 경량 연구 산출물만 저장한다.

저장 금지:
- APK
- `libil2cpp.so`
- `global-metadata.dat`
- Ghidra project
- 수십 MB 이상의 dump/json/dll/so

저장:
- Markdown
- 작은 CSV
- 짧은 decompile text
- XREF/call graph 요약
- runtime log
- patch specification
- scripts

## 작업 종료 조건
조사 TASK는 다음 중 하나가 충족될 때 종료한다.
- 목표가 증거로 확인됨
- 목표가 반증됨
- 추가 조사 없이는 결론 불가하며 그 이유가 명확함

그 후 Codex는 결과 문서를 push하고 작업을 멈춘다. GPT가 다음 TASK를 지정하기 전까지 임의의 추가 패치를 하지 않는다.
