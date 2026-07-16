---
name: commit
description: 변경사항 커밋. Phase 완료 후 사용. 사용법 $commit [계획서경로] <Phase명> [PROJ-XXXX]
---

# 커밋 실행

입력: $ARGUMENTS

## 절차

### 1. 입력 파싱

**입력 형식**:
- `Phase1` → 최근 계획서에서 Phase1
- `async-milvus Phase1` → 특정 계획서의 Phase1
- `docs/working_history/260128/plan.md Phase1` → 특정 경로 계획서
- `Phase1 PROJ-1234` → Phase1 + JIRA 코드
- `PROJ-1234` → JIRA 코드만 (전체 staged 파일)
- (미지정) → 최근 변경 파일 전체

**JIRA 코드 추출**:
- 패턴: `[A-Z]+-\d+` (예: PROJ-1234)
- 커밋 메시지 접두어로 사용

---

### 2. 선행 조건 확인

> ⚠️ **R2-D2 방법론**: 커밋은 모든 단계 완료 후에만 실행

**계획서에서 진행 현황 테이블 확인**:

| 열 | 요구 상태 |
|----|----------|
| 🔴 Red | ✅ |
| 🟢 Green | ✅ |
| 🔵 Refactor | ✅ |
| 📝 Doc | ✅ |

**확인 방법**:
1. 계획서 파일 읽기
2. 해당 Phase 행에서 Red/Green/Refactor/Doc 열 확인
3. 하나라도 ⬜이면 → **커밋 중단**, 해당 단계 먼저 완료 안내

```
예: Phase 1 | ✅ | ✅ | ✅ | ⬜ | ⬜
→ "📝 Doc이 완료되지 않았습니다. `$report Phase1`을 먼저 실행하세요."
```

---

### 3. 변경사항 확인

```bash
git status
git diff --stat
```

- 변경사항 없으면 커밋 중단
- staged 파일 없으면 staging 여부 질문

---

### 4. 커밋 메시지 생성

**메시지 형식**:

```
[Phase{N}-{단계}] <type>: <한글 설명>
```

JIRA 코드가 있으면:

```
PROJ-XXXX [Phase{N}-{단계}] <type>: <한글 설명>
```

**단계 구분** (Tidy First 원칙):

| 단계 | 의미 | 변경 유형 |
|------|------|----------|
| Red | 테스트 작성 | Behavioral |
| Green | 최소 구현 | Behavioral |
| Refactor | 구조/성능 개선 | Structural |

**커밋 타입**:

| 타입 | 설명 |
|------|------|
| feat | 새 기능 추가 |
| fix | 버그 수정 |
| refactor | 리팩터링 |
| test | 테스트 추가/수정 |
| docs | 문서 변경 |
| chore | 기타 변경 |

**예시**:

```
PROJ-1234 [Phase1-Green] feat: Milvus 비동기 클라이언트 구현
PROJ-1234 [Phase1-Refactor] refactor: 연결 풀 구조 개선
[Phase2-Red] test: 배치 처리 실패 케이스 테스트 추가
```

---

### 5. 사용자 승인 요청

> ⚠️ **필수**: 커밋 실행 전 반드시 사용자 확인

**승인 요청 내용**:
- 변경 파일 목록
- 커밋 메시지 미리보기
- "이 내용으로 커밋을 진행할까요?"

**승인 후에만** 다음 단계 진행

---

### 6. 커밋 실행

```bash
git add <파일목록>
git commit -m "<메시지>"
git log -1 --oneline
```

---

## 체크박스 업데이트

> **중요**: 커밋 완료 후 아래 항목들을 `- [ ]` → `- [x]`로 업데이트

### 사후 작업 체크박스

`**[COMMIT]**` 체크박스 업데이트

### 진행 현황 테이블

해당 Phase의 Commit 열을 ⬜ → ✅ 로 변경:

```
| Phase 1 | ✅ | ✅ | ✅ | ✅ | ⬜ |
→
| Phase 1 | ✅ | ✅ | ✅ | ✅ | ✅ |
```

---

## 완료 조건

- [ ] 선행 조건 확인 (Red/Green/Refactor/Doc 모두 ✅)
- [ ] 변경사항 존재 확인
- [ ] 커밋 메시지 생성 (Phase 정보 포함)
- [ ] 사용자 승인 완료
- [ ] 커밋 성공
- [ ] 계획서 `**[COMMIT]**` 체크박스 업데이트
- [ ] 진행 현황 테이블 업데이트

> 다음 단계: 다음 Phase `$tdd` 또는 릴리즈

---

## 롤백 가이드라인

| 상황 | 조치 |
|------|------|
| 커밋 직후 실수 발견 | `git reset --soft HEAD~1` (변경사항 유지) |
| 커밋 내용 완전 폐기 | `git reset --hard HEAD~1` |
| 작업 방향 자체가 잘못됨 | 작업 직전 커밋으로 `git reset --hard <commit>` |
| pre-commit hook 실패 | 문제 수정 후 **새 커밋** 생성 (amend 금지) |

> 💡 **핵심**: 잘못된 방향으로 계속 진행하는 것보다 **빠르게 롤백하고 재시작**

---

## 주의사항

> ⚠️ **R2-D2 방법론 핵심**
> - 커밋은 **사용자 승인 후에만** 실행
> - `$tdd` → `$review` → `$report` **완료 확인 후** 실행
> - 선행 조건 미충족 시 커밋 진행 금지
