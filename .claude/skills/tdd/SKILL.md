---
name: tdd
description: TDD 워크플로우 실행. 기능 구현 시 사용. 사용법 /tdd [계획서경로] <Phase명>
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

# TDD 워크플로우

입력: $ARGUMENTS

## 환경

- 테스트/린터 명령어는 `CLAUDE.md`의 환경 섹션을 참조

## 절차

### 1. 작업계획서 탐색

**입력 파싱**:
- `Phase1` → 최근 계획서에서 Phase1 탐색
- `async-milvus Phase1` → async-milvus_todolist.md에서 Phase1
- `docs/working_history/260128/plan.md Phase1` → 특정 경로 계획서

**작업계획서 탐색**:
- 경로 미지정 시: `docs/working_history/` 에서 최근 `*_todolist.md` 파일 탐색
- 계획서명만 지정 시: `docs/working_history/**/` 에서 해당 파일 검색
- 전체 경로 지정 시: 해당 파일 직접 사용

**Phase 섹션 구조 확인**:
- N.1 사전 작업 (Pre-Work)
- N.2 🔴 RED Phase
- N.3 🟢 GREEN Phase
- N.4 🔵 REFACTOR Phase
- N.5 사후 작업 (Post-Work)

> **중요**: 계획서에 작성된 테스트 코드, 구현 코드를 그대로 참조하여 작업

---

### 2. 사전 작업 (Pre-Work)

> Phase 내 `### N.1 사전 작업` 섹션의 항목들 처리

- **[CONTEXT]** - 작업 목적 및 배경 파악
- **[REVIEW]** - 이전 Phase 결과서 검토 (Phase 2 이상인 경우)
- **[ANALYSIS]** - 현재 코드/설정 분석

---

### 3. 🔴 RED Phase (실패 테스트 작성)

> Phase 내 `### N.2 🔴 RED Phase` 섹션의 항목들 처리

- **[RED]** 테스트 작성
  - 계획서에 작성된 테스트 코드를 참고하여 작성
  - 테스트 파일 위치: `tests/` 하위 적절한 경로

- **[RED-VERIFY]** 실패 확인
  - `CLAUDE.md`에 명시된 테스트 명령어로 실행
  - **반드시 FAIL 확인 후** 다음 단계 진행

---

### 4. 🟢 GREEN Phase (최소 구현)

> Phase 내 `### N.3 🟢 GREEN Phase` 섹션의 항목들 처리

- **[TASK-XXX]** 구현
  - 계획서에 작성된 구현 코드를 참고하여 작성
  - 테스트 통과하는 **최소한의 코드만** 구현 (Make it work)
  - 최적화하지 않음

- **[GREEN-VERIFY]** 통과 확인
  - `CLAUDE.md`에 명시된 테스트 명령어로 실행
  - **반드시 PASS 확인 후** 다음 단계 진행

---

### 5. 🔵 REFACTOR Phase (개선)

> Phase 내 `### N.4 🔵 REFACTOR Phase` 섹션의 항목들 처리

- **[REFACTOR-STRUCTURE]** 구조 개선 (Make it right)
  - 중복 제거, 네이밍 개선, 책임 분리

- **[REFACTOR-PERF-*]** 성능 개선 (Make it fast) - 해당 시
  - docs/working_template/100_Python_Performance_Guide.md 참조

- **[REFACTOR-VERIFY]** 테스트 재확인
  - `CLAUDE.md`에 명시된 테스트 명령어로 실행
  - **여전히 PASS 확인**

---

### 6. 사후 작업 (Post-Work)

> Phase 내 `### N.5 사후 작업` 섹션의 항목들 처리

- **[TEST]** 전체 테스트 실행
  - `CLAUDE.md`에 명시된 테스트 명령어로 실행

- **[LINT]** 린터 검사
  - `CLAUDE.md`에 명시된 린터 명령어로 실행

---

## 체크박스 업데이트

> **중요**: 각 단계 완료 직후 **즉시** Edit 도구로 해당 체크박스 업데이트

```
file_path: <계획서 경로>
old_string: "- [ ] **[RED-VERIFY]** 테스트 실패 확인"
new_string: "- [x] **[RED-VERIFY]** 테스트 실패 확인"
```

| 태그 | 완료 시점 |
|------|----------|
| `**[CONTEXT]**` | 사전 작업 완료 |
| `**[ANALYSIS]**` | 사전 작업 완료 |
| `**[RED]**` | 테스트 작성 완료 |
| `**[RED-VERIFY]**` | 테스트 실패 확인 |
| `**[TASK-XXX]**` | 각 구현 완료 |
| `**[GREEN-VERIFY]**` | 테스트 통과 확인 |
| `**[REFACTOR-STRUCTURE]**` | 구조 개선 완료 |
| `**[REFACTOR-VERIFY]**` | 리팩터링 후 테스트 |
| `**[TEST]**` | 전체 테스트 통과 |
| `**[LINT]**` | 린터 경고 0개 |

---

## 완료 조건

- [ ] 사전 작업 체크박스 모두 완료
- [ ] RED Phase 체크박스 모두 완료
- [ ] GREEN Phase 체크박스 모두 완료
- [ ] REFACTOR Phase 체크박스 모두 완료
- [ ] 사후 작업 체크박스 모두 완료 (TEST, LINT)
- [ ] 모든 테스트 통과
- [ ] 린터 경고 0개

> 다음 단계: `/review` → `/report` → `/commit`

참조: docs/working_template/99_TDD_plan.md
