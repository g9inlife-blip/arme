# Heroes Offline Research

이 저장소는 `com.thumbage.heroes.google` Unity/IL2CPP 게임의 **오프라인 전환 역분석 작업용 경량 연구 저장소**다.

## 역할 분담
- **GPT**: 분석 방향 결정, 가설 수립, 증거 해석, 다음 조사 TASK 정의.
- **Codex**: 로컬 APK/Ghidra/ADB를 실제로 조작하고, 조사 결과를 문서화하며 필요할 때만 파일을 수정/빌드.
- **사용자**: 수정 APK를 실제 실행하고 화면/로그 결과를 알려줌.

## 저장 원칙
Git에는 거대한 원본 바이너리를 넣지 않는다.
- 저장하지 않음: APK, `libil2cpp.so`, `global-metadata.dat`, Ghidra 프로젝트, 대형 dump/json
- 저장함: TASK, decompile 핵심 구간, XREF/call graph 요약, 문자열 증거, 패치 명세, 빌드/런타임 결과, 현재 상태

## 기본 루프
1. GPT가 `research/targets/TASK-xxx.md` 작성/지시
2. Codex가 로컬 Ghidra/ADB에서 **조사만 수행**
3. Codex가 `research/reports/TASK-xxx-result.md` 작성 후 push
4. GPT가 결과를 읽고 다음 조사 지점 결정
5. 증거가 충분해지면 PATCH 문서 작성
6. Codex가 패치/빌드/자동 검증
7. 사용자가 APK를 실행하고 결과 전달

## 현재 핵심 목표
온라인 업데이트 의존성을 제거하면서 기존 로컬 리소스로 정상 진입하는 경로를 확보한다.

시작점과 주요 조사 대상은 `research/CURRENT_STATE.md`를 참조한다.
