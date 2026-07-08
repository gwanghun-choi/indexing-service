---
name: report
description: 작업결과서 생성. Phase 완료 후 사용. 사용법 $report [계획서경로] <Phase명>
---

# 작업결과서 생성

입력: $ARGUMENTS

## 절차

### 1. 작업계획서 탐색

**입력 파싱**:
- `Phase1` → 최근 계획서에서 Phase1
- `async-milvus Phase1` → 특정 계획서의 Phase1
- `docs/working_history/260128/plan.md Phase1` → 특정 경로 계획서

**작업계획서 탐색**:
- 경로 미지정 시: `docs/working_history/` 에서 최근 `*_todolist.md` 탐색

---

### 2. 정보 수집

```bash
git diff --name-only
git diff --staged --name-only
```

- 변경된 파일 목록
- 테스트/린터 결과

---

### 3. 결과서 생성

**파일 위치**: `docs/working_history/YYMMDD/<Phase명>_<날짜>.md`

**필수 섹션**:

```markdown
# <Phase명> 작업 결과서

## 작업 개요
- 목표: <목표>
- 범위: <파일 목록>

## 🔴 Red Phase
- 작성한 테스트 설명

## 🟢 Green Phase
- 구현 내용 설명

## 🔵 Refactor Phase
- 개선 내용 설명

## 검증 결과
- 테스트: PASS/FAIL
- 린터: 경고 0개

## 변경 파일
| 파일 | 변경 내용 |
|------|----------|
| ... | ... |

## 이슈 및 해결
- (있는 경우)

## 다음 단계
- (있는 경우)
```

---

## 체크박스 업데이트

> **중요**: 결과서 생성 후 아래 항목들을 `- [ ]` → `- [x]`로 업데이트

### 사후 작업 체크박스

`**[DOC]**` 체크박스 업데이트

### 진행 현황 테이블

해당 Phase의 Doc 열을 ⬜ → ✅ 로 변경:

```
| Phase 1 | ✅ | ✅ | ✅ | ⬜ | ⬜ |
→
| Phase 1 | ✅ | ✅ | ✅ | ✅ | ⬜ |
```

---

## 완료 조건

- [ ] 결과서 파일 생성
- [ ] 필수 섹션 모두 작성
- [ ] 계획서 `**[DOC]**` 체크박스 업데이트
- [ ] 진행 현황 테이블 업데이트

> 다음 단계: `$commit`

---

## 역할

- 다음 작업의 RAG 컨텍스트
- 다른 AI 리뷰 기준자료
- 지식 축적 및 판단 연속성 유지

참조: docs/working_template/03_work_result_report_template.md
