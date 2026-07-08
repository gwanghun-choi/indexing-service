---
paths:
  - "src/**/*.py"
  - "app/**/*.py"
  - "tests/**/*.py"
---

# TDD 원칙 (Kent Beck + Tidy First)

## 사이클
1. **Red**: 실패하는 테스트 먼저 작성, 실패 확인 후 구현 시작
2. **Green**: 테스트 통과하는 최소 코드만 구현 (최적화 X)
3. **Refactor**: 테스트 통과 상태에서만 리팩터링

## Tidy First
- **구조 변경** (Structural): 동작 변경 없이 코드 정리 (네이밍, 추출, 이동)
- **동작 변경** (Behavioral): 실제 기능 추가/수정
- 구조와 동작 변경을 같은 커밋에 섞지 않음
- 구조 변경 먼저, 동작 변경 나중에

## 커밋 규율
- 모든 테스트 통과
- 린터 경고 0개
- 사용자 최종 승인
- 단일 논리 단위

## 테스트 명명
```python
def test_<method>_<scenario>_<expected>():
    """설명"""
    # Arrange
    # Act
    # Assert
```

## 롤백 규율
- 지속적 실패 또는 잘못된 방향 → `git reset --hard HEAD`
- 설계 방향 자체가 잘못됨 → PRD/작업계획서 재검토

상세: @docs/working_template/99_TDD_plan.md
