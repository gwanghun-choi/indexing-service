---
name: review
description: 코드 리뷰 체크리스트 실행. 사용법 /review [계획서경로] <Phase명> 또는 /review <파일경로>
allowed-tools: Read, Grep, Bash, Glob, Edit
---

# 코드 리뷰

입력: $ARGUMENTS

## 절차

### 1. 리뷰 대상 탐색

**입력 파싱**:
- `Phase1` → 최근 계획서에서 Phase1의 작업 범위 파악
- `async-milvus Phase1` → 특정 계획서의 Phase1
- `docs/working_history/260128/plan.md Phase1` → 특정 경로 계획서
- `app/services/foo.py` → 특정 파일 직접 리뷰
- (미지정) → 최근 변경 파일

**리뷰 대상 파악**:
- Phase 지정 시: 작업계획서에서 해당 Phase의 파일 목록 확인
- 경로 지정 시: 해당 경로 직접 사용
- 미지정 시: `git diff --name-only` 또는 `git diff --staged --name-only`

---

### 2. 코드 품질 검토

- [ ] 타입 힌트 적용
- [ ] docstring 작성 (공개 함수/클래스)
- [ ] 적절한 로그 레벨 사용
- [ ] Import 순서 (표준 → 서드파티 → 로컬)

---

### 3. 아키텍처 검토

- [ ] async/await 올바른 사용
- [ ] 기존 패턴과 일관성
- [ ] N+1 쿼리 문제 없음
- [ ] 리소스 정리 (연결, 파일 등)

---

### 4. 성능 검토

- [ ] 불필요한 DB 쿼리 없음
- [ ] 대용량 처리 시 배치 적용
- [ ] 멤버십 검사에 set/dict 사용

참조: @docs/working_template/100_Python_Performance_Guide.md

---

### 5. 보안 검토

- [ ] 하드코딩된 시크릿 없음
- [ ] SQL 인젝션 방지 (ORM 사용)
- [ ] 입력 검증 (Pydantic)

---

### 6. 테스트 검증

- [ ] 새 코드에 테스트 있음
- [ ] 엣지 케이스 테스트
- [ ] 모든 테스트 통과

`CLAUDE.md`에 명시된 테스트/린터 명령어로 실행

---

## 체크박스 업데이트

> **중요**: 리뷰 완료 시 **즉시** 해당 Phase 내의 체크박스 업데이트

```
file_path: <계획서 경로>
old_string: "- [ ] **[TEST]** 전체 테스트 실행"
new_string: "- [x] **[TEST]** 전체 테스트 실행"
```

| 태그 | 완료 시점 |
|------|----------|
| `**[TEST]**` | 전체 테스트 통과 확인 |
| `**[LINT]**` | 린터 경고 0개 확인 |

---

## 완료 조건

- [ ] 체크리스트 항목 모두 검토
- [ ] 문제 발견 시 수정 완료
- [ ] 테스트 통과 확인
- [ ] 린터 경고 0개 확인
- [ ] 계획서 체크박스 업데이트

> 다음 단계: `/report` → `/commit`

참조: @docs/working_template/02_code_review_template.md
