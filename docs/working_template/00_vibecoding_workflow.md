## _TDD 기반 설계 중심 · 인간 검증 중심 · 다중 AI 순환 개발 방법론_

> "빠르게 짜는 방법"이 아니라  

> **"빠르게 설계하고, 빠르게 검증하고, 빠르게 수정하는 구조"**

---

## 슬라이드 1. 기존 바이브코딩의 진짜 문제

❌ 문제의 본질은 **속도**가 아니다  

❌ 문제의 본질은 **검증 구조의 부재**

**정리**

- AI는 빠르다
    
- 하지만 **틀린 방향으로도 매우 빠르다**
    
- 방향을 잡는 구조가 없으면 → 실패 속도만 빨라진다
    

> 👉 그래서 이 방법론은 "속도"가 아니라 **"짧은 검증 순환"을 목표로 한다**

---

## 슬라이드 2. R2-D2란 무엇인가?

### **R**ecursive **R**eview - **D**esign **D**riven (TDD)

|   |   |   |
|---|---|---|
|약어|의미|설명|
|R2|Recursive Review|다중 AI 순환 검증 구조|
|D2|Test Design Driven|TDD 기반 설계 중심 개발|

**핵심 정의**

> R2-D2는 AI가 생성한 결과물을    
> **다른 AI로 교차 검증**하고,    
> **인간이 최종 승인**하는    
> **설계 중심 순환 개발 프레임워크**이다.

---

## 슬라이드 3. 이 방법론의 핵심은 3가지다

### ❌ "AI를 잘 쓰는 방법론" 아님

### ⭕ **"검증을 구조화한 TDD 기반 개발 방법론"**

|핵심 원칙|설명|
|---|---|
|TDD 기반|테스트 = AI를 위한 설계 명세이자 가드레일|
|인간 검증 중심|최종 판단은 항상 인간|
|다중 AI 순환|교차 검증으로 편향 제거|

---

## 슬라이드 4. R2-D2 방법론의 기반 문서 체계

|문서|역할|파일|
|---|---|---|
|TDD 방법론|Kent Beck TDD + Tidy First 원칙|[99_TDD_plan.md](./99_TDD_plan.md)|
|성능 가이드|파이썬 성능 최적화 기준|[100_Python_Performance_Guide.md](./100_Python_Performance_Guide.md)|
|작업계획서 템플릿|단계별 작업 계획 구조|[01_todolist_performance_template.md](./01_todolist_performance_template.md)|
|코드리뷰 템플릿|AI 코드 리뷰 구조|[02_code_review_template.md](./02_code_review_template.md)|
|작업결과서 템플릿|작업 결과 기록 구조|[03_work_result_report_template.md](./03_work_result_report_template.md)|

> 💡 이 문서들이 **AI 에이전트의 가드레일**이자 **인간 검증의 기준**이 된다

---

## 슬라이드 5. 왜 TDD가 이 방법론의 중심인가

**일반적인 오해**

- TDD = 테스트 많이 쓰는 개발 방식 ❌
    

**R2-D2에서의 TDD**

- **설계 중심 개발** — 테스트가 "무엇을 만들어야 하는지" 정의
    
- **빠른 실패 → 빠른 수정** — 짧은 사이클로 방향 검증
    
- **AI의 가드레일** — 테스트 범위 안에서만 AI가 작동
    

---

## 슬라이드 6. TDD = AI를 위한 설계 명세이자 가드레일

R2-D2에서 TDD는:

- "이 기능을 어떻게 구현할까?" ❌ (구현 중심 사고)
    
- **"이 기능의 설계를 어떻게 정의하고, AI가 이를 따르게 할까?" ⭕** (설계 + 가드레일)
    

👉 테스트는 단순 검증이 아니라 **AI를 위한 설계 명세이자 가드레일**

**TDD의 3가지 역할**

|역할|설명|
|---|---|
|설계 정의|테스트 = "무엇을 만들어야 하는지"의 명세|
|빠른 검증|작은 단위로 설계 의도대로 구현됐는지 확인|
|가드레일|AI가 설계 범위를 벗어나지 않도록 경계 설정|

**한 문장 정의**

> _TDD는 AI가 코드를 쓰는 시대에,_    
> _인간이 설계를 정의하고, AI가 그 안에서만 움직이도록_    
> _가드레일을 세우는 장치다._

📄 참고: [99_TDD_plan.md](./99_TDD_plan.md)

---

## 슬라이드 7. TDD의 짧은 순환 구조 (Red → Green → Refactor)

`설계 가설     ↓ 🔴 실패 테스트 작성 (Red)     ↓ 🟢 최소 구현 (Green) — "Make it work"     ↓ 🔵 구조/성능 개선 (Refactor) — "Make it right, Make it fast"     ↓ 다음 설계 가설`

**TDD 핵심 원칙** ([99_TDD_plan.md](./99_TDD_plan.md) 발췌)

|원칙|설명|
|---|---|
|Red First|반드시 **실패하는 테스트**를 먼저 작성|
|Minimal Green|테스트를 통과하는 **최소한의 코드만** 구현|
|Safe Refactor|테스트가 **통과하는 상태에서만** 리팩터링|
|Tidy First|구조 변경(Structural)과 동작 변경(Behavioral) 분리|
|**Commit Discipline**|**작업 단계 완료 시에만** 커밋 (아래 조건 충족 필수)|

**커밋 규율** (Commit Discipline)

> ⚠️ **커밋은 반드시 사용자 승인 완료 후에만 수행**

|조건|설명|
|---|---|
|✅ 모든 테스트 통과|테스트가 실패한 상태로 커밋 금지|
|✅ 린터 경고 0개|모든 경고 해결 후 커밋|
|✅ 다중 AI 리뷰 완료|리뷰 피드백 반영 완료 ([02_code_review_template.md](./02_code_review_template.md) 활용)|
|✅ 사용자 최종 승인|인간이 검토하고 승인한 후에만 커밋|
|✅ 단일 논리 단위|하나의 변경 목적만 포함|

`# ❌ BAD: 테스트 실패 상태로 커밋 git commit -m "WIP: 작업 중"  # ✅ GOOD: 단계 완료 후 커밋 git commit -m "[Phase1-Green] 사용자 인증 최소 구현 완료" git commit -m "[Phase1-Refactor] 인증 로직 구조 개선"`

**롤백 규율** (Rollback Discipline)

> 🔄 **작업이 잘못된 방향으로 진행 시 즉시 롤백**

|상황|조치|
|---|---|
|AI가 지속적으로 잘못된 방향으로 진행|git reset --hard HEAD 후 재시작|
|테스트가 계속 실패하고 해결 불가|작업 직전 커밋으로 롤백|
|설계 방향 자체가 잘못됨|PRD 또는 작업계획서 재검토 후 롤백|

`# 작업 직전 상태로 롤백 (변경사항 폐기) git reset --hard HEAD  # 특정 커밋으로 롤백 git reset --hard <commit-hash>  # 변경사항 보존하며 롤백 (재작업용) git reset --soft HEAD~1`

> 💡 **핵심**: 잘못된 방향으로 계속 진행하는 것보다 **빠르게 롤백하고 재시작**하는 것이 효율적

**권장 사이클 시간**

|작업 유형|권장 시간|
|---|---|
|단순 기능|15-30분|
|복잡 로직|30-60분|
|아키텍처 변경|60-120분 (분할 권장)|

---

## 슬라이드 8. AI 검증의 핵심 원칙

> **같은 AI가 자신의 결과를 검증하면 안 된다.**    
> **다른 AI가 교차 검증 도구로 사용되어야 한다.**    
> **최종 검증 주체는 항상 인간이다.**

**왜 다른 AI로 검증하는가?**

|문제|해결|
|---|---|
|동일 모델 → 동일 편향|서로 다른 모델로 교차 검증|
|같은 프롬프트 → 같은 실수|다른 관점의 프롬프트 사용|

👉 결과가 같으면 **신뢰도 상승**  

👉 결과가 다르면 **설계 의심 신호**

---

## 슬라이드 9. R2-D2 전체 프로세스 (10단계)

```mermaid
flowchart TD
  subgraph PHASE1["Phase 1: PRD 작성 및 검증"]
    A1[1. 사용자: PRD 초안 작성<br/>01_basic_project_plan]
    A2[2. 다른 AI: PRD 리뷰 및 개선]
    A3[3. 사용자: PRD 최종 승인]
    A1 --> A2 --> A3
    A2 -.->|개선 필요| A1
  end

  subgraph PHASE2["Phase 2: 작업계획서 작성 및 검증"]
    B1[4. 작업계획서 작성<br/>01_todolist_performance_template.md]
    B2[5. 다른 AI: 작업계획서 리뷰]
    B3[6. 사용자: 작업계획서 승인]
    B1 --> B2 --> B3
    B2 -.->|개선 필요| B1
  end

  subgraph PHASE3["Phase 3: 작업 실행 (TDD 순환)"]
    C1[7. 사전작업 🔴<br/>컨텍스트 수집 + 테스트 작성]
    C2[8. 본작업 🟢<br/>최소 구현]
    C3[9. 사후작업 🔵<br/>리팩터링 + 결과서 작성]
    C1 --> C2 --> C3
  end

  subgraph PHASE4["Phase 4: 검증 및 순환"]
    D1[10. 다른 AI: 작업결과서 기반 리뷰]
    D2{문제 발견?}
    D3[사용자: Step 완료 승인]
    D4[✅ 커밋]
    D1 --> D2
    D2 -->|YES 수정가능| C2
    D2 -->|NO| D3
    D3 --> D4
  end

  subgraph ROLLBACK["롤백 분기"]
    R1{방향이 잘못됨?}
    R2[git reset --hard]
    R3[작업 직전 상태로 복원]
    R1 -->|YES| R2 --> R3
  end

  A3 --> B1
  B3 --> C1
  C3 --> D1
  D2 -->|YES 방향 잘못| R1
  R3 -->|재시작| C1
  D4 -->|다음 Step| C1
  D4 -->|완료| E[릴리즈]
```

---

## 슬라이드 10. Phase 1 — PRD 작성 및 다중 AI 검증

### Step 1-3: PRD 순환

|Step|담당|내용|
|---|---|---|
|1|사용자|PRD 초안 작성 (01_basic_project_plan)|
|2|다른 AI|PRD 리뷰 및 개선 의견 도출|
|3|사용자|PRD 최종 검증 및 승인|

**PRD 리뷰 포인트**

- 요구사항의 명확성
    
- 기술적 실현 가능성
    
- 누락된 케이스/예외 상황
    
- 성능 요구사항 명시 여부
    

> 💡 PRD가 명확해야 **테스트(가드레일)도 명확**해진다

---

## 슬라이드 11. Phase 2 — 작업계획서 작성 및 검증

### Step 4-6: 작업계획서 순환

|Step|담당|내용|
|---|---|---|
|4|사용자/AI|작업계획서 작성 ([01_todolist_performance_template.md](./01_todolist_performance_template.md))|
|5|다른 AI|작업계획서 리뷰 및 검증|
|6|사용자|작업계획서 최종 승인|

**작업계획서 구조** ([01_todolist_performance_template.md](./01_todolist_performance_template.md) 기반)

`Phase N: [Phase 제목] ├── N.1 사전 작업 (Pre-Work) │   ├── [CONTEXT] 작업 목적 및 배경 확인 │   ├── [REVIEW] 이전 작업 결과서 검토 │   └── [ANALYSIS] 현재 코드/설정 분석 ├── N.2 🔴 RED Phase: 실패 테스트 작성 ├── N.3 🟢 GREEN Phase: 최소 코드 구현 ├── N.4 🔵 REFACTOR Phase: 코드 개선 + 성능 최적화 └── N.5 사후 작업 (Post-Work)     ├── [TEST] 전체 테스트 실행     ├── [DOC] 작업 결과서 작성     └── [COMMIT] 변경사항 커밋`

---

## 슬라이드 12. Phase 3 — 작업 실행 (사전 → 본작업 → 사후)

### 작업 단위의 3단계 = TDD 사이클

|단계|TDD 매핑|역할|원칙|
|---|---|---|---|
|**사전 작업**|🔴 Red|컨텍스트 수집 + 테스트 작성|이전 결과서 참조, 실패 테스트 먼저|
|**본 작업**|🟢 Green|최소 구현|"Make it work" — 동작 우선|
|**사후 작업**|🔵 Refactor|구조/성능 개선 + 결과서 작성|"Make it right, Make it fast"|

**사전 작업 체크리스트**

PRD 문서 검토

**이전 작업 결과서 확인** (Phase 2 이후 필수)

현재 코드/설정 분석

🔴 실패 테스트 작성 및 실패 확인

**본 작업 체크리스트**

🟢 테스트를 통과하는 **최소한의 코드** 구현

테스트 통과 확인

**사후 작업 체크리스트**

🔵 코드 구조 개선 (중복 제거, 네이밍, 책임 분리)

🔵 성능 최적화 적용 ([100_Python_Performance_Guide.md](./100_Python_Performance_Guide.md) 참조)

테스트 재확인 (여전히 PASS)

린터 검사 통과 (경고 0개)

**작업 결과서 작성** ([03_work_result_report_template.md](./03_work_result_report_template.md))

다중 AI 리뷰 요청 → 피드백 반영 ([02_code_review_template.md](./02_code_review_template.md))

**사용자 최종 승인** ← 여기서 검토!

**커밋** (승인 완료 후에만)

  `git commit -m "[Phase{N}-{단계}] {작업 내용} 완료"`

> 🔄 **롤백 판단**: 작업이 잘못된 방향이면 즉시 git reset --hard HEAD 후 재시작

---

## 슬라이드 13. Refactor 단계의 성능 최적화 (Make it fast)

> 📄 참고: [100_Python_Performance_Guide.md](./100_Python_Performance_Guide.md)

**Refactor 원칙**: 먼저 동작(Green) → 구조 개선(Right) → **성능 최적화(Fast)**

|패턴|Before|After|개선|⚠️ 주의|
|---|---|---|---|---|
|멤버십 검사|if x in list|if x in set|O(1)|반복 검사 시만!|
|리스트 생성|for + append|컴프리헨션|~20-30%↑||
|JSON 처리|json.dumps()|orjson.dumps()|~8배↑|**bytes 반환**|
|대량 인스턴스|일반 클래스|__slots__|메모리 50%↓|제약사항 확인|

**성능 최적화 프로세스**

`1. 측정 (Baseline) → 2. 분석 (체크리스트) → 3. 최적화 → 4. 검증 (테스트 + 성능)`

> ⚠️ **주의**: 성능 수치는 환경별로 다름. **본인 환경에서 측정 후 적용**

---

## 슬라이드 14. Phase 4 — 작업결과서와 다중 AI 리뷰

### Step 10: 작업결과서 기반 검증

**작업결과서의 2가지 역할**

|역할|설명|
|---|---|
|**RAG 컨텍스트**|다음 작업의 사전작업에서 참조 → 판단의 연속성 유지|
|**리뷰 기준자료**|다른 AI가 코드를 리뷰하는 기준|

**작업결과서 구조** ([03_work_result_report_template.md](./03_work_result_report_template.md) 기반)

`Step X.X: [작업명] 작업 기록 ├── 📋 작업 개요 (목표, 범위) ├── 🔴 Red Phase (테스트 작성) ├── 🟢 Green Phase (구현) ├── ✅ 검증 결과 (테스트, 커버리지, Linter) ├── 🐛 이슈 및 해결 ├── 📝 다음 단계 └── 📊 커밋 요약`

**다중 AI 리뷰 프로세스**

`작업결과서 + 변경 코드         ↓ 다른 AI 에이전트 리뷰 (Codex, Claude, Gemini 등) ([02_code_review_template.md](./02_code_review_template.md) 활용)         ↓     문제/리팩터링 포인트 도출         ↓     YES → 수정 작업 → 결과서에 추가 기록     NO  → 사용자 최종 승인`

---

## 슬라이드 15. 작업결과서 = 지식 순환의 핵심

❌ 단순 보고서    
⭕ **다음 작업을 위한 RAG 컨텍스트**

**활용 흐름**

`이전 작업 결과서     ↓ 다음 작업의 [REVIEW] 사전작업에서 참조     ↓ "왜 이렇게 했는지" AI가 이해     ↓ 판단의 연속성 유지`

**필수 확인 항목** (Phase 2 이후)

- 이전 체크리스트 완료 여부
    
- 미해결 이슈
    
- 성능 개선 결과
    
- 다음 단계 안내 사항
    

> 💡 **사람의 기억을 문서화 → AI의 컨텍스트로 확장**

---

## 슬라이드 16. TDD 적용 예시: 사용자 인증 기능

|단계|TDD|내용|
|---|---|---|
|사전|🔴 Red|"로그인 실패 시 401 반환" 테스트 작성 (실패 확인)|
|본작업|🟢 Green|AI에게 최소 구현 요청, 테스트 통과|
|사후|🔵 Refactor|코드 구조 개선, 성능 최적화|
|사후|📝 Record|작업결과서 작성 ([03_work_result_report_template.md](./03_work_result_report_template.md))|
|검증|🔍 Review|다른 AI로 교차 검증|
|승인|✅ Approve|사용자 최종 승인|

**테스트 예시** (가드레일)

`def test_login_fail_returns_401():     """로그인 실패 시 401 반환 - AI가 이 범위 안에서만 구현"""     response = client.post("/login", json={"email": "wrong", "password": "wrong"})     assert response.status_code == 401     assert "error" in response.json()`

---

## 슬라이드 17. R2-D2 도구 스택 예시

|역할|권장 도구|비고|
|---|---|---|
|메인 코딩|Cursor (Claude)|주 개발 환경|
|코드 리뷰|Claude Code, Codex|교차 검증용|
|설계 검증|Gemini|다른 관점 확보|
|문서화|Notion / Obsidian|작업결과서 관리|
|작업 관리|GitHub Issues / Jira|추적성 확보|

**문서 체계**

`docs/working_history/ ├── 99_TDD_plan.md                    # TDD 방법론 ├── 100_Python_Performance_Guide.md   # 성능 가이드 ├── v{버전}/ │   ├── {기능}_todolist.md            # 작업계획서 │   └── working_history/ │       ├── template.md               # 결과서 템플릿 │       └── Phase{N}_{타이틀}_{날짜}.md # 실제 결과서`

---

## 슬라이드 18. R2-D2 Anti-Patterns

### ❌ 하지 말아야 할 것

|Anti-Pattern|문제점|올바른 방법|
|---|---|---|
|**자기 검증**|같은 AI로 작성 → 같은 AI로 검증|다른 AI로 교차 검증|
|**컨텍스트 단절**|작업 결과서 생략|모든 Phase에 결과서 필수|
|**Big Bang 구현**|테스트 없이 대규모 구현|Red → Green → Refactor 순환|
|**무승인 진행**|인간 승인 없이 다음 단계|사용자 최종 승인 필수|
|**Green에서 최적화**|구현하면서 성능 최적화|Refactor 단계에서만 최적화|
|**사전작업 생략**|바로 본작업 진행|이전 결과서 검토 후 진행|
|**승인 전 커밋**|리뷰/승인 없이 커밋|사용자 승인 후에만 커밋|
|**잘못된 방향 고집**|실패해도 계속 같은 방향 진행|즉시 롤백 후 재시작|
|**롤백 지연**|문제 인지 후에도 진행|빠르게 git reset 결정|

---

## 슬라이드 19. 인간 검증의 위치

R2-D2에서 **모든 단계는 인간이 최종 검증**:

|Phase|단계|실행 주체|검증 주체|
|---|---|---|---|
|1|PRD 작성|사용자|사용자|
|1|PRD 리뷰|다른 AI|**사용자**|
|2|작업계획서 작성|사용자/AI|사용자|
|2|작업계획서 리뷰|다른 AI|**사용자**|
|3|작업 실행|AI 에이전트|**사용자**|
|4|코드 리뷰|다른 AI|**사용자**|

> 💡 **AI는 서로 교차 검증하지만,**    
> **최종 승인 책임은 항상 사람에게 있다**

---

## 슬라이드 20. R2-D2는 무엇인가?

|항목|해당 여부|
|---|---|
|Agile|✅|
|TDD (Kent Beck)|✅|
|Tidy First|✅|
|AI Pair Programming|✅|
|문서 중심 개발|✅|
|RAG 기반 지식 순환|✅|
|다중 에이전트 검증|✅|

**정의**

> _AI 에이전트를 포함한 검증 중심 Agile 개발 프레임워크_

---

## 슬라이드 21. 기존 방식과의 차이

|구분|일반 바이브코딩|R2-D2 방법론|
|---|---|---|
|속도|빠름|빠름|
|품질|불안정|안정|
|재현성|없음|있음|
|기록|거의 없음|구조화 (결과서)|
|확장|어려움|쉬움|
|검증|단일/없음|다중 순환|
|AI 가드레일|없음|TDD 테스트|
|지식 축적|없음|결과서 → RAG|

---

## 슬라이드 22. 한 문장 정의

> **"R2-D2는**    
> **TDD로 AI의 가드레일을 세우고,**    
> **다른 AI가 교차 검증하며,**    
> **인간이 최종 승인하는**    
> **설계 중심 순환 개발 프레임워크다."**

---

## 슬라이드 23. AI 시대의 개발자는 무엇을 해야 하는가

- 코드를 많이 짜는 사람 ❌
    
- AI를 잘 다루는 사람 ❌
    

⭕ **설계를 정의하고, 검증하고, 판단을 축적하는 사람**

**개발자의 역할 변화**

|역할|설명|
|---|---|
|과거|R2-D2 시대|
|코드 작성|**설계 정의** (테스트 = 명세)|
|버그 수정|**가드레일 설정** (TDD)|
|코드 리뷰|**다중 AI 리뷰 조율**|
|문서화|**결과서로 지식 축적**|

---

## 슬라이드 24. 마지막 문장

> **TDD는 더 이상 '테스트 방법론'이 아니다.**
> 
> **AI 시대의 개발자에게**    
> **설계를 정의하고, AI를 가드레일 안에서 움직이게 하는**    
> **최소한의 통제 장치다.**

---

## 부록 A. R2-D2 Quick Reference

### 10단계 프로세스 요약

|#|단계|담당|산출물|커밋|
|---|---|---|---|---|
|1|PRD 초안 작성|사용자|01_basic_project_plan|❌|
|2|PRD 리뷰|다른 AI|개선 의견|❌|
|3|**PRD 승인**|사용자|확정 PRD|✅ 가능|
|4|작업계획서 작성|사용자/AI|*_todolist.md|❌|
|5|작업계획서 리뷰|다른 AI|개선 의견|❌|
|6|**작업계획서 승인**|사용자|확정 계획서|✅ 가능|
|7|사전작업 (🔴 Red)|AI|테스트 + 컨텍스트|❌|
|8|본작업 (🟢 Green)|AI|최소 구현|❌|
|9|사후작업 (🔵 Refactor)|AI|개선 코드 + 결과서|❌|
|10|다중 AI 리뷰|다른 AI|리뷰 의견|❌|
|✅|**사용자 승인**|사용자|완료|✅ 필수|

> ⚠️ **커밋 규칙**: **사용자 승인 완료 후에만** 커밋 (테스트 통과 + 린터 0개 + 승인)  

> 🔄 **롤백 규칙**: 작업이 잘못된 방향으로 진행 시 git reset으로 작업 직전 상태로 복원 후 재시작

### 핵심 문서

|문서|용도|
|---|---|
|[99_TDD_plan.md](./99_TDD_plan.md)|TDD 방법론 (Red→Green→Refactor, Tidy First)|
|[100_Python_Performance_Guide.md](./100_Python_Performance_Guide.md)|Refactor 단계 성능 최적화 기준|
|[01_todolist_performance_template.md](./01_todolist_performance_template.md)|작업계획서 템플릿|
|[02_code_review_template.md](./02_code_review_template.md)|코드 리뷰 템플릿|
|[03_work_result_report_template.md](./03_work_result_report_template.md)|작업결과서 템플릿|

---

## 부록 B. 전체 프로세스 통합 다이어그램

```mermaid
flowchart TD
  %% =========================
  %% R2-D2 Framework Process
  %% Recursive Review - Design Driven (TDD)
  %% =========================

  %% --- PRD Phase ---
  A[1. 사용자: PRD 초안 작성<br/>01_basic_project_plan]
  A --> B[2. 다른 AI: PRD 리뷰 및 개선 의견]
  B --> C{개선 필요?}
  C -- YES --> A
  C -- NO --> D[3. 사용자: PRD 최종 승인]

  %% --- Planning Phase ---
  D --> E[4. 작업계획서 작성<br/>01_todolist_performance_template.md]
  E --> F[5. 다른 AI: 작업계획서 리뷰]
  F --> G{개선 필요?}
  G -- YES --> E
  G -- NO --> H[6. 사용자: 작업계획서 승인]

  %% --- Task Cycle ---
  H --> K{다음 작업 Step 선택}

  subgraph R2D2["R2-D2 작업 순환 (TDD Cycle)"]
    direction TB
    K --> P[7. 🔴 사전작업 Red<br/>- 이전 결과서 검토<br/>- 컨텍스트 수집<br/>- 실패 테스트 작성]
    P --> Q[8. 🟢 본작업 Green<br/>- 최소 구현<br/>- 테스트 통과]
    Q --> R[9. 🔵 사후작업 Refactor<br/>- 구조 개선<br/>- 성능 최적화<br/>- 작업결과서 작성]
    R --> S[작업결과서 저장<br/>03_work_result_report_template.md]
    S --> T[10. 다른 AI: 작업결과서 기반 리뷰<br/>Codex, Claude, Gemini]
    T --> U{문제 발견?}
    U -- YES 수정가능 --> V[수정 피드백]
    V --> Q
    U -- NO --> W[사용자: Step 완료 승인]
    W --> COMMIT[✅ 커밋]
  end

  %% --- Rollback Branch ---
  U -- YES 방향 잘못 --> RESET{롤백 결정}
  RESET --> GIT[git reset --hard]
  GIT --> RESTORE[작업 직전 상태 복원]
  RESTORE -->|재시작| P

  %% --- Iteration / Finish ---
  COMMIT --> X{남은 Step?}
  X -- YES --> K
  X -- NO --> Y[릴리즈 및 회고<br/>결과서 정리]

  %% --- RAG Connection ---
  S -.->|다음 사전작업에서 참조| P
```
