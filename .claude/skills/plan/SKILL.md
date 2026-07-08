---
name: plan
description: TDD 기반 작업계획서 생성. 새 작업 시작 시 사용. 사용법 /plan <작업명>
allowed-tools: Read, Write, Glob, Grep
---

# 작업계획서 생성

작업명: $ARGUMENTS

## 절차

### 1. 컨텍스트 수집

- **PRD 확인**: 관련 PRD 문서 확인 (없으면 `/prd <작업명>` 실행 권장)
- **이전 결과서**: 이전 작업 결과서 검토 (있는 경우)
- **영향 범위**: 영향받는 파일/모듈 파악

### 2. 작업계획서 생성

**파일 위치**: `docs/working_history/YYMMDD/<작업명>_todolist.md`

### 3. 계획서 구조

아래 템플릿을 사용하여 계획서 생성:

```markdown
# <작업명> 작업 계획서

> **TDD 방법론**: Red → Green → Refactor
> **워크플로우**: `/tdd` → `/review` → `/report` → `/commit`

---

## 작업 개요

| 항목 | 내용 |
|------|------|
| 관련 PRD | `docs/working_history/YYMMDD/<작업명>_prd.md` (있는 경우) |
| 프로젝트 | <프로젝트 설명> |
| 영향 범위 | <파일 목록> |
| 위험 수준 | 🟢 Low / 🟡 Medium / 🔴 High |

---

## Phase 1: <Phase 제목>

> **목표**: <목표 설명>

### 1.1 사전 작업

- [ ] **[CONTEXT]** 작업 목적 및 배경 확인
- [ ] **[ANALYSIS]** 현재 코드/설정 분석

### 1.2 🔴 RED Phase

- [ ] **[RED]** 테스트 작성
  - 테스트 파일: `tests/<경로>`
  - 테스트 내용 설명
- [ ] **[RED-VERIFY]** 테스트 실패 확인

### 1.3 🟢 GREEN Phase

- [ ] **[TASK-001]** <구현 내용 1>
  - 파일: `<경로>`
- [ ] **[TASK-002]** <구현 내용 2> (필요시)
- [ ] **[GREEN-VERIFY]** 테스트 통과 확인

### 1.4 🔵 REFACTOR Phase

- [ ] **[REFACTOR-STRUCTURE]** 코드 구조 개선
- [ ] **[REFACTOR-VERIFY]** 테스트 재확인

### 1.5 사후 작업

- [ ] **[TEST]** 전체 테스트 실행
- [ ] **[LINT]** 린터 검사
- [ ] **[DOC]** 작업 결과서 작성
- [ ] **[COMMIT]** 커밋 완료

---

## Phase 2: <Phase 제목> (필요시)

> **목표**: <목표 설명>

### 2.1 사전 작업

- [ ] **[REVIEW]** Phase 1 결과서 검토
- [ ] **[ANALYSIS]** 현재 코드/설정 분석

### 2.2 🔴 RED Phase
(Phase 1과 동일 구조)

### 2.3 🟢 GREEN Phase
(Phase 1과 동일 구조)

### 2.4 🔵 REFACTOR Phase
(Phase 1과 동일 구조)

### 2.5 사후 작업
(Phase 1과 동일 구조)

---

## 진행 현황

| Phase | 🔴 Red | 🟢 Green | 🔵 Refactor | 📝 Doc | ✅ Commit |
|-------|--------|---------|-------------|--------|----------|
| Phase 1 | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| Phase 2 | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |

---

**작성일**: YYYY-MM-DD
**상태**: 🔄 진행 중
```

---

## 체크박스 형식 규칙

> **중요**: 다른 skill들과 연동을 위해 반드시 아래 형식 사용

| 태그 | 담당 skill | 설명 |
|------|-----------|------|
| `**[CONTEXT]**` | /tdd | 작업 배경 확인 |
| `**[REVIEW]**` | /tdd | 이전 결과서 검토 |
| `**[ANALYSIS]**` | /tdd | 코드 분석 |
| `**[RED]**` | /tdd | 테스트 작성 |
| `**[RED-VERIFY]**` | /tdd | 테스트 실패 확인 |
| `**[TASK-XXX]**` | /tdd | 구현 작업 |
| `**[GREEN-VERIFY]**` | /tdd | 테스트 통과 확인 |
| `**[REFACTOR-STRUCTURE]**` | /tdd | 구조 개선 |
| `**[REFACTOR-VERIFY]**` | /tdd | 리팩터링 후 테스트 |
| `**[TEST]**` | /tdd, /review | 전체 테스트 실행 |
| `**[LINT]**` | /tdd, /review | 린터 검사 |
| `**[DOC]**` | /report | 결과서 작성 |
| `**[COMMIT]**` | /commit | 커밋 완료 |

---

## 완료 조건

- [ ] PRD 확인 (없으면 `/prd <작업명>` 실행 권장)
- [ ] 컨텍스트 수집 완료
- [ ] 계획서 파일 생성
- [ ] Phase별 체크박스 항목 작성
- [ ] 진행 현황 테이블 작성

---

## 워크플로우 연결

```
/prd → /plan → /tdd → /review → /report → /commit
(WHY)  (WHAT)  (Implementation & Verification)
```

> **이전 단계**: `/prd <작업명>`으로 작업 배경 정의 (선택사항)
> **다음 단계**: Phase별로 `/tdd` → `/review` → `/report` → `/commit` 반복
