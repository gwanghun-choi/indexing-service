---
paths:
  - "src/**/*.py"
  - "app/**/*.py"
---

# Python 성능 가이드 (Refactor 단계 참조)

> 수치는 상대적 비교용. 본인 환경에서 측정 후 적용

## 데이터 구조 선택
| 상황 | 권장 |
|------|------|
| 반복 멤버십 검사 | `set`/`dict` O(1) |
| 순서 있는 고유값 | `dict` (Python 3.7+) |
| 대량 인스턴스 | `__slots__` (메모리 50%↓) |

```python
# 반복 검사 시 set 변환
large_set = set(large_list)  # 변환 비용 O(n)
if item in large_set:  # 이후 O(1)
```

## 문자열
- f-string 우선 사용
- 루프 내 `+=` 연결 금지 → `"".join()` 사용

## JSON
| 라이브러리 | 속도 | 주의 |
|------------|------|------|
| orjson | ~8배↑ | bytes 반환, 테스트 필수 |
| json (표준) | 기준 | 호환성 최고 |

## 비동기
- I/O 바운드에만 async 사용
- CPU 바운드는 동기 또는 멀티프로세싱

## 예외 처리
| 상황 | 권장 |
|------|------|
| 키가 거의 항상 존재 | `d[key]` (try/except) |
| 키가 자주 없음 | `d.get(key, default)` |

## 보안
- pickle은 신뢰된 내부 데이터만 (외부 입력 금지)

상세: @docs/working_template/100_Python_Performance_Guide.md
