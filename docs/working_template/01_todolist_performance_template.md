# [프로젝트명] 작업 계획서

> **TDD 방법론 기반**: Red → Green → Refactor 사이클 적용  
> **작업 원칙**: 테스트 먼저 작성 → 최소 코드 구현 → 리팩터링 (성능 검증 포함)  
> **리팩터링 원칙**: "Make it work → Make it right → Make it fast"  
> **참고 문서**: 
>   - [99_TDD_plan.md](../99_TDD_plan.md) - TDD 방법론  
>   - [100_Python_Performance_Guide.md](../100_Python_Performance_Guide.md) - 성능 가이드  
> **작업 결과서 템플릿**: [template.md](./working_history/{버전}/template.md)  
> **버전**: v2.0 (TDD + Performance)

---

## 📋 작업 개요

| 항목 | 내용 |
|------|------|
| 프로젝트 | [프로젝트 설명] |
| 영향 범위 | [영향받는 파일/모듈 목록] |
| 위험 수준 | 🔴 Critical / 🟠 High / 🟡 Medium / 🟢 Low |
| **성능 민감도** | 🔴 High (대용량/실시간) / 🟠 Medium / 🟢 Low |
| 참고 PRD | [PRD 문서 링크](./path/to/prd.md) |
| 작업 브랜치 | `FEAT/[브랜치명]` |

---

## 🚨 핵심 리스크 요약

| 리스크 | 영향 | 대응 방안 | 상태 |
|--------|------|----------|------|
| [리스크 1] | 🔴 High | [대응 방안] | ⬜ |
| [리스크 2] | 🟠 Medium | [대응 방안] | ⬜ |
| **[성능] 대용량 데이터 처리** | 🟠 Medium | Refactor 단계에서 최적화 | ⬜ |

---

## 🔄 Phase 1: [Phase 제목]

> 📄 **상세 참고**: [detail_prd/step01_xxx.md](./detail_prd/step01_xxx.md) (있는 경우)

### 1.1 사전 작업 (Pre-Work)

> **목적**: 본작업의 실패를 줄이기 위한 작업 준비 과정  
> **원칙**: 전체 작업의 목적과 배경, 이전 작업결과서를 참고하여 작업의 맥락 이해 및 일관성 유지

- [ ] **[CONTEXT]** 작업 목적 및 배경 확인
  - PRD 문서 검토: [PRD 문서 링크](./path/to/prd.md)
  - 관련 이슈/티켓 확인: [이슈 링크]

- [ ] **[REVIEW]** 이전 작업 결과서 검토 *(Phase 2 이후)*
  - 파일: `./working_history/{버전}/Phase{N-1}_{이전타이틀}_{작업일자}.md`
  - 확인: 이전 체크리스트 완료 여부, 미해결 이슈 확인

- [ ] **[ANALYSIS]** 현재 코드/설정 분석
  - 파일: `[분석 대상 파일]`
  - 확인 내용: [분석할 내용]
  - 예상 데이터 규모: [항목 수, 빈도] *(성능 민감 시)*

- [ ] **[BACKUP]** 기존 파일 백업 (필요시)
  ```bash
  cp [원본 파일] [백업 파일]
  ```

---

### 1.2 🔴 RED Phase: 실패 테스트 작성

> **목적**: 구현할 기능을 정의하는 실패 테스트 작성  
> **원칙**: 테스트가 실패하는 것을 확인한 후에만 구현 시작

- [ ] **[RED]** 기능 테스트 작성
  ```python
  def test_xxx():
      """[테스트 설명]"""
      # 테스트 코드
      assert expected == actual
  ```

- [ ] **[RED-VERIFY]** 테스트 실패 확인
  ```bash
  pytest [테스트 경로] -v  # 반드시 FAIL이어야 함
  ```

---

### 1.3 🟢 GREEN Phase: 최소 코드 구현

> **목적**: 테스트를 통과하는 최소한의 코드 구현  
> **원칙**: "Make it work" - 동작하게 만드는 것이 최우선, 최적화는 Refactor에서

- [ ] **[TASK-001]** [작업 제목]
  - 파일: `[파일 경로]`
  - 변경 내용:
    ```python
    # 최소한의 구현 (성능보다 동작 우선)
    [구현 코드]
    ```
  - 예상 소요: X분

- [ ] **[TASK-002]** [작업 제목]
  - 파일: `[파일 경로]`
  - 작업: [작업 설명]
  - 예상 소요: X분

- [ ] **[GREEN-VERIFY]** 테스트 통과 확인
  ```bash
  pytest [테스트 경로] -v  # 반드시 PASS여야 함
  ```

---

### 1.4 🔵 REFACTOR Phase: 코드 개선 + 성능 최적화

> **목적**: 동작을 유지하면서 코드 구조와 성능 개선  
> **원칙**: "Make it right, Make it fast" - 테스트가 통과하는 상태에서만 리팩터링

#### 1.4.1 구조 개선 (Make it right)

- [ ] **[REFACTOR-STRUCTURE]** 코드 구조 개선
  - 중복 코드 제거
  - 네이밍 개선
  - 책임 분리 (SRP)
  - 로깅 추가

- [ ] **[REFACTOR-VERIFY]** 리팩터링 후 테스트 재확인
  ```bash
  pytest [테스트 경로] -v  # 여전히 PASS여야 함
  ```

#### 1.4.2 성능 개선 (Make it fast) ⚡

> **참고**: [100_Python_Performance_Guide.md](../100_Python_Performance_Guide.md)  
> **주의**: 성능 민감도가 🟢 Low인 경우 이 섹션 생략 가능

- [ ] **[REFACTOR-PERF-MEASURE]** 현재 성능 측정 (베이스라인)
  ```python
  import time
  start = time.perf_counter()
  result = target_function(test_data)
  elapsed = time.perf_counter() - start
  print(f"Baseline: {elapsed*1000:.2f}ms")
  ```

- [ ] **[REFACTOR-PERF-ANALYZE]** 성능 체크리스트 검토
  
  | 항목 | 현재 상태 | 개선 필요 | 주의사항 | 적용 |
  |------|----------|----------|----------|------|
  | 데이터 구조 (list→set/dict) | [현재] | ✅/❌ | ⚠️ 반복 검사 시만 유리, 단발성은 변환비용 확인 | ⬜ |
  | 컴프리헨션 사용 | [현재] | ✅/❌ | - | ⬜ |
  | `__slots__` (대량 인스턴스) | [현재] | ✅/❌/N/A | ⚠️ 동적속성/weakref/상속 제약 확인 | ⬜ |
  | JSON 라이브러리 (orjson) | [현재] | ✅/❌/N/A | ⚠️ bytes 반환, 타입 제한 확인, 테스트 필수 | ⬜ |
  | 비동기 적정성 | [현재] | ✅/❌/N/A | I/O 바운드만 적용 | ⬜ |
  | EAFP/LBYL 선택 | [현재] | ✅/❌ | ⚠️ 키 존재 비율에 따라 결정 | ⬜ |

- [ ] **[REFACTOR-PERF-OPTIMIZE]** 성능 최적화 적용
  ```python
  # 변경 전 (Green에서 구현한 코드)
  [기존 코드]
  
  # 변경 후 (성능 최적화)
  [최적화된 코드]
  ```
  - 적용한 최적화: [최적화 내용]
  - 예상 개선: [X배 또는 X% 개선]

- [ ] **[REFACTOR-PERF-VERIFY]** 최적화 후 테스트 + 성능 확인
  ```bash
  pytest [테스트 경로] -v  # 여전히 PASS여야 함
  ```
  ```python
  # 성능 개선 확인
  # Baseline: XXms → Optimized: XXms (XX% 개선)
  ```

---

### 1.5 사후 작업 (Post-Work)

> **목적**: 수정된 코드 검증 및 작업 결과 문서화  
> **원칙**: 모든 검증 완료 후 작업결과서 작성

- [ ] **[TEST]** 전체 테스트 실행
  ```bash
  pytest [테스트 경로] -v
  pytest tests/integration/ -v  # 해당시
  ```

- [ ] **[LINT]** 린터 검사
  ```bash
  ruff check [경로]
  ```

- [ ] **[VERIFY]** 기능 검증
  - 확인 항목 1: [검증 내용]
  - 확인 항목 2: [검증 내용]

- [ ] **[DOC]** 작업 결과서 작성
  - 파일: `./working_history/{버전}/Phase1_{작업타이틀}_{작업일자}.md`
  - 템플릿: [template.md](./working_history/{버전}/template.md)
  - 내용:
    - 작업 목표 및 범위
    - Red/Green/Refactor 각 단계 결과
    - **성능 개선 결과** (Refactor에서 적용한 최적화)
    - 테스트 실행 결과 및 커버리지
    - 이슈 및 해결 방법
    - 다음 단계 안내

- [ ] **[COMMIT]** 변경사항 커밋
  ```bash
  git add .
  git commit -m "[Phase1] {작업타이틀} 완료"
  ```

---

## 🔄 Phase 2: [Phase 제목]

> 📄 **상세 참고**: [detail_prd/step02_xxx.md](./detail_prd/step02_xxx.md) (있는 경우)

### 2.1 사전 작업

- [ ] **[REVIEW]** 이전 Phase 작업 결과서 검토
  - 파일: `./working_history/{버전}/Phase1_{이전타이틀}_{작업일자}.md`
  - 확인: 체크리스트 완료, 미해결 이슈, **성능 개선 결과**

- [ ] **[CONTEXT]** Phase 2 작업 목적 확인

- [ ] **[ANALYSIS]** [분석 대상] 확인

### 2.2 🔴 RED Phase

- [ ] **[RED]** 실패 테스트 작성
- [ ] **[RED-VERIFY]** 테스트 실패 확인

### 2.3 🟢 GREEN Phase

- [ ] **[TASK-001]** [작업 제목]
- [ ] **[GREEN-VERIFY]** 테스트 통과 확인

### 2.4 🔵 REFACTOR Phase

- [ ] **[REFACTOR-STRUCTURE]** 코드 구조 개선
- [ ] **[REFACTOR-PERF-ANALYZE]** 성능 체크리스트 검토 *(성능 민감 시)*
- [ ] **[REFACTOR-PERF-OPTIMIZE]** 성능 최적화 적용 *(해당 시)*
- [ ] **[REFACTOR-VERIFY]** 테스트 재확인

### 2.5 사후 작업

- [ ] **[TEST]** 테스트 실행 및 검증
- [ ] **[DOC]** 작업 결과서 작성
- [ ] **[COMMIT]** 변경사항 커밋

---

## 🔄 Phase N: [Phase 제목]

*(필요한 만큼 Phase 추가 - 동일 구조)*

### N.1 사전 작업
### N.2 🔴 RED Phase
### N.3 🟢 GREEN Phase
### N.4 🔵 REFACTOR Phase
### N.5 사후 작업

---

## ✅ 최종 체크리스트

### TDD 사이클 완료
- [ ] 모든 Phase의 Red → Green → Refactor 사이클 완료
- [ ] 전체 테스트 통과 (`pytest tests/ -v`)
- [ ] 통합 테스트 통과 (`pytest tests/integration/ -v`)
- [ ] 린터 경고 0개

### 성능 최적화 결과 (Refactor 단계 요약)
| Phase | 적용한 최적화 | 개선 효과 |
|-------|-------------|----------|
| Phase 1 | [예: list→set 변경] | [예: 조회 200배↑] |
| Phase 2 | [예: 컴프리헨션 적용] | [예: 26%↑] |
| Phase N | [예: orjson 적용] | [예: 8배↑] |

### 문서화
- [ ] 각 Phase별 작업 결과서 작성 완료
- [ ] README.md 업데이트 (필요시)
- [ ] API 문서 업데이트 (필요시)
- [ ] 변경 로그 업데이트

### 최종 커밋 및 PR
- [ ] 모든 변경사항 커밋 완료
- [ ] PR 생성 및 코드 리뷰 요청
- [ ] CI/CD 파이프라인 통과

---

## 📊 진행 체크리스트

### 사전 준비
- [ ] 작업 브랜치 생성 (`git checkout -b FEAT/[브랜치명]`)
- [ ] 기존 테스트 전체 실행 및 결과 기록
- [ ] 관련 PRD 문서 검토
- [ ] 성능 가이드 검토 ([100_Python_Performance_Guide.md](../100_Python_Performance_Guide.md))

### Phase 완료 조건
| Phase | 🔴 Red | 🟢 Green | 🔵 Refactor | 결과서 | 커밋 | 상태 |
|-------|--------|---------|------------|--------|------|------|
| Phase 1 | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| Phase 2 | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| Phase N | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |

---

## ⚠️ 주의사항

### TDD 사이클 원칙
1. **Red First**: 반드시 실패하는 테스트를 먼저 작성
2. **Minimal Green**: 테스트를 통과하는 최소한의 코드만 구현 (최적화 X)
3. **Safe Refactor**: 테스트가 통과하는 상태에서만 리팩터링 진행

### Refactor 단계 원칙 (구조 + 성능)
4. **Make it right**: 먼저 코드 구조를 개선 (중복 제거, 네이밍, 책임 분리)
5. **Make it fast**: 그 다음 성능 최적화 적용 (측정 → 분석 → 최적화 → 검증)
6. **테스트 보호**: 모든 리팩터링 후 테스트 재실행으로 동작 유지 확인

### 작업 관리 원칙
7. **작업 결과서 필수**: 각 Phase 완료 시 결과서 작성
8. **이전 결과서 검토**: Phase 2 이후 반드시 이전 결과서 확인
9. **커밋 단위**: Phase 단위로 커밋하여 롤백 용이하게 관리
10. **린터 통과**: 커밋 전 반드시 린터 검사 통과

---

## ⚡ 성능 최적화 Quick Reference (Refactor 시 참조)

> [100_Python_Performance_Guide.md](../100_Python_Performance_Guide.md) 발췌  
> ⚠️ **주의**: 수치는 상대 비교용이며, **본인 환경에서 측정 후 적용** 권장

| 패턴 | Before | After | 개선 | ⚠️ 주의사항 |
|------|--------|-------|------|-------------|
| 멤버십 검사 | `if x in list` | `if x in set` | O(1) | 반복 검사 시만! 단발성은 변환비용 확인 |
| 리스트 생성 | `for` + `append` | 컴프리헨션 | ~20-30%↑ | - |
| JSON 처리 | `json.dumps()` | `orjson.dumps()` | ~8배↑ | **bytes 반환**, 타입 제한, 테스트 필수 |
| 대량 인스턴스 | 일반 클래스 | `__slots__` | 메모리 50%↓ | 동적속성/weakref/상속 제약 확인 |
| 딕셔너리 접근 | `try: d[k]` | `d.get(k, default)` | 상황별 | 키 존재 비율에 따라 다름 |
| 비동기 선택 | 무조건 async | I/O 바운드만 | 오버헤드 방지 | CPU 바운드는 동기로 |
| 직렬화 | json | pickle | ~2배↑ | 🔴 **신뢰된 내부 데이터만!** 보안 위험 |

---

## 🔗 관련 문서

- [PRD 문서](./path/to/prd.md) - 기획설계 문서
- [99_TDD_plan.md](../99_TDD_plan.md) - TDD 방법론 가이드
- [100_Python_Performance_Guide.md](../100_Python_Performance_Guide.md) - 파이썬 성능 가이드 (Refactor 참조)
- [template.md](./working_history/{버전}/template.md) - 작업 결과서 템플릿

---

## 📅 예상 일정

| Phase | 예상 소요 | 시작일 | 완료일 | 비고 |
|-------|----------|--------|--------|------|
| Phase 1 | X일 | YYYY-MM-DD | - | [비고] |
| Phase 2 | X일 | - | - | [비고] |
| Phase N | X일 | - | - | [비고] |
| **Total** | **X일** | - | - | - |

---

**작성일**: YYYY-MM-DD  
**작성자**: [작성자]  
**최종 수정일**: YYYY-MM-DD  
**상태**: ⬜ 작성 중 / 🔄 검토 대기 / ✅ 승인됨
