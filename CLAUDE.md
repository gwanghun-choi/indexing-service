# indexing-service 프로젝트 가이드

## R2-D2 방법론
> TDD로 AI의 가드레일을 세우고, 다른 AI가 교차 검증하며, 인간이 최종 승인하는 설계 중심 순환 개발

**핵심 원칙**:
- 테스트 = AI를 위한 설계 명세이자 가드레일
- 최종 판단은 항상 인간
- 커밋은 사용자 승인 완료 후에만 수행

## 환경

**패키지 관리**: uv (pyproject.toml + uv.lock)

```bash
# 테스트 명령어
uv run pytest tests/ -v

# 린터 명령어
uv run ruff check app/ tests/

# 의존성 동기화
uv sync

# 패키지 추가/제거
uv add <package>
uv remove <package>

# 인프라 접속 정보는 .env 참조 (.env.example 복사 후 설정)
# 기본 포트: Milvus:19530, Redis:6379, OpenSearch:19200, PostgreSQL:5432
```

> ⚠️ 모든 테스트/린터 실행 시 위 명령어 형식 사용

## TDD 사이클
```
🔴 Red    → 실패 테스트 작성 (설계 정의)
🟢 Green  → 최소 구현 (Make it work)
🔵 Refactor → 구조/성능 개선 (Make it right, Make it fast)
```

## 커밋 규율
- 모든 테스트 통과 + 린터 경고 0개 + 사용자 승인 후에만 커밋
- 잘못된 방향 시 즉시 `git reset --hard HEAD`

## 코드 컨벤션
- Dict 접근: `data["key"]` (Fail Fast, `.get()` 지양)
- 출력: `logger.info()` (print 금지)
- Import: 표준 → 서드파티 → 로컬
- Env Vars: `os.getenv("VAR")` (기본값 금지)
- String: f-string 우선 (`.format()`, `%` 지양)
- 네이밍: `verb_object` (예: `get_user`, `create_document`)
- Type Hints: 함수 시그니처 필수

## 코딩/리뷰 체크리스트 (요약)
**기본 규칙**
- Dict 접근은 `data["key"]` 사용, `.get()` 지양 (예외: 외부/불완전 데이터는 명시적 기본값 필요 시 허용)
- 출력은 `logger.info()` (print 금지)
- Import 순서: 표준 → 서드파티 → 로컬, 섹션 간 1줄 공백
- Env vars: `os.getenv("VAR")`만 사용, 기본값 금지
- 문자열: f-string 우선, `.format()`/`%` 지양
- 테스트 네이밍: `test_<method>_<scenario>_<expected>`

**클린 코드**
- 함수 길이 ≤ 20줄, 파라미터 ≤ 4, 중첩 ≤ 2 (권장)
- 조기 반환으로 중첩 최소화
- 매직 넘버 상수화, 축약/의미 없는 변수명 금지

**타입/문서화**
- 타입 힌트 + docstring 포함
- 예외는 구체적 타입으로 처리, AppError 계층 유지

**구조**
- 재사용 2회+ 또는 단순 변환 로직은 utils로 분리
- 리소스 해제는 contextmanager 사용

**성능 가이드(요약)**
- 성능 최적화는 측정 후 수행 (조기 최적화 금지)
- 멤버십 반복 조회는 list 대신 set/dict 고려
- 루프 내 문자열 연결은 `join()` 사용
- 대량 인스턴스는 `__slots__` 고려
- async는 I/O 바운드에만 사용
- 큰 파일은 스트리밍 처리, 전체 로드 지양

## Skills 사용법

TDD 워크플로우를 위한 skills가 제공됩니다:

| Skill | 설명 | 사용법 |
|-------|------|--------|
| `$prd` | PRD(요구사항) 생성 | `$prd <작업명>` |
| `$plan` | 작업계획서 생성 | `$plan <작업명>` |
| `$tdd` | TDD 워크플로우 실행 | `$tdd [계획서] <Phase>` |
| `$review` | 코드 리뷰 | `$review [계획서] <Phase>` |
| `$report` | 작업결과서 생성 | `$report [계획서] <Phase>` |
| `$commit` | 커밋 실행 | `$commit [계획서] <Phase> [PROJ-XXXX]` |

**워크플로우 순서**: `$prd` → `$plan` → `$tdd` → `$review` → `$report` → `$commit`

## 상세 가이드
- TDD 방법론: docs/working_template/99_TDD_plan.md
- 성능 가이드: docs/working_template/100_Python_Performance_Guide.md
- 전체 워크플로우: docs/working_template/00_vibecoding_workflow.md
