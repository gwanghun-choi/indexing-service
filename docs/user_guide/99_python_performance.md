# Python Performance Guide

> **Scope**: indexing-service project

---

## 1. Memory Usage

| Object | Memory | Object | Memory |
|--------|--------|--------|--------|
| int | 28B | float | 24B |
| empty str | 41B (+1B/char) | empty list | 56B |
| empty dict | 64B | empty set | 216B |

**Class Instance (5 attributes):**

| Type | Single | 1,000 instances |
|------|--------|-----------------|
| Regular class | 694B | 165.2KB |
| `__slots__` | 212B | 79.1KB (**52%↓**) |

---

## 2. Data Structures

| Operation | Fast | Slow | Diff |
|-----------|------|------|------|
| Membership | `set`/`dict` O(1) | `list` O(n) | **200x** |
| Queue ops | `deque` O(1) | `list.insert(0)` O(n) | **O(n)** |
| Sorted search | `bisect` O(log n) | `list.index` O(n) | **O(n)** |
| Immutable | `tuple` | `list` | **5-10%** |

---

## 3. Operation Speed

| Operation | Speed | Operation | Speed |
|-----------|-------|-----------|-------|
| int add/mul | 19ns | float add | 18.4ns |
| str concat | 39.1ns | len() | 17.6ns |
| dict lookup | 21.9ns | set lookup | 19ns |
| list search (1K) | 3.85μs | attr read | 14-16ns |
| isinstance() | 18.3ns | hasattr() | 23.8ns |

**String Formatting:**

| Method | Speed |
|--------|-------|
| f-string | 65ns ✅ |
| `%` format | 90ns |
| `.format()` | 103ns |

**Loop (1,000 items):**

| Method | Speed |
|--------|-------|
| Comprehension | 9.45μs ✅ |
| for loop | 11.9μs (26% slower) |

---

## 4. Function & Exception

| Operation | Speed |
|-----------|-------|
| Empty function | 22.4ns |
| Method call | 23.3ns |
| try/except (normal) | 21.5ns |
| **Exception raised** | **139ns (7x slower)** |

---

## 5. Async Overhead

| Operation | Speed |
|-----------|-------|
| Sync function | 20ns |
| Coroutine creation | 47ns |
| asyncio.sleep(0) | 39.4μs |
| gather (10 tasks) | 55μs |
| **Sync vs Async** | **~1,400x** |

→ Use async only for actual I/O parallelism

---

## 6. JSON & Serialization

| Library | Serialize | Deserialize |
|---------|-----------|-------------|
| **orjson** | **310ns** | **839ns** ✅ |
| msgspec | 445ns | - |
| ujson | 1.64μs | - |
| stdlib json | 2.65μs | - |

---

## 7. File I/O

| Operation | Speed | Operation | Speed |
|-----------|-------|-----------|-------|
| File open/close | 9.05μs | | |
| 1KB read | 10μs | 1KB write | 35.1μs |
| 1MB read | 33.6μs | 1MB write | 207μs |

---

## 8. Web Framework (JSON Response)

| Framework | Speed |
|-----------|-------|
| Starlette | 8.01μs ✅ |
| Litestar | 8.19μs |
| FastAPI | 8.63μs |
| Flask | 16.5μs |
| Django | 18.1μs (2x slower) |

---

## 9. Database

| DB | Operation | Speed |
|----|-----------|-------|
| SQLite | insert | 192μs |
| SQLite | select | 3.57μs |
| SQLite | update | 5.22μs |
| MongoDB | insert | 119μs |
| MongoDB | find_one | 121μs |
| diskcache | set | 23.9μs |
| diskcache | get | 4.25μs |

---

## 10. Optimization Patterns

```python
# String: f-string and join
url = f"{protocol}://{host}:{port}"     # Good
result = "".join(strings)                # Good: O(n)
result += s  # in loop                   # Bad: O(n²)

# Dict: literal and defaultdict
d = {"a": 1, "b": 2}                     # Good
counts = defaultdict(int)                # Good
d = dict(a=1, b=2)                       # Bad: slower

# Branchless - avoid branch prediction misses
x = max(min_val, min(max_val, x))        # Good
result = np.maximum(data, 0)             # Good: SIMD
if x < min_val: return min_val           # Bad: branches

# LRU Cache - avoid recomputation
@lru_cache(maxsize=128)
def expensive_calc(n): ...

# Local Caching - avoid repeated lookups
append = self.results.append             # Cache method
_len = len                               # Cache builtin
for item in items:
    append(_len(item))

# Short-circuit - cheap checks first
if user.is_active and expensive_db_check(user): ...

# Walrus - compute once
if (data := get_data(x)) is not None:
    process(data)

# Comprehension > for loop (26% faster)
result = [x * 2 for x in items]

# Generator for large data (O(1) memory)
squares = (x ** 2 for x in range(1_000_000))
def get_lines(path):
    with open(path) as f:
        yield from f

# NumPy Vectorized (100-500x faster)
result = (data - data.mean()) / data.std()
result = np.where(cond, a, b)            # Branchless
```

---

## 11. Parallelism

| Task Type | Use |
|-----------|-----|
| CPU-bound | `ProcessPoolExecutor` (bypass GIL) |
| I/O-bound (few) | `ThreadPoolExecutor` |
| I/O-bound (many) | `asyncio` |

---

## 12. Profiling

```bash
# CPU profiling
python -m cProfile -s cumtime script.py

# Line-by-line profiling
pip install line_profiler
kernprof -l -v script.py

# Memory profiling
pip install memory_profiler
python -m memory_profiler script.py
```

```python
# Inline timing
from contextlib import contextmanager
import time

@contextmanager
def timer(name: str):
    start = time.perf_counter()
    yield
    print(f"{name}: {time.perf_counter() - start:.4f}s")

with timer("process"):
    result = process(data)
```

---

## 13. Quick Reference

### Performance Checklist

| Do | Impact |
|----|--------|
| `set`/`dict` for membership | 200x |
| `deque` for queue | O(1) vs O(n) |
| `tuple` over `list` (immutable) | 5-10% |
| List comprehension | 26% |
| Generator for large data | O(1) memory |
| f-string | 65ns (fastest) |
| `"".join()` | O(n) vs O(n²) |
| `@lru_cache` | No recompute |
| Local var caching | No repeated lookups |
| Short-circuit order | Cheap checks first |
| `min()`/`max()` branchless | No misprediction |
| NumPy vectorization | 100-500x |
| `orjson` | 8x vs stdlib |
| `__slots__` | 52% memory |
| ProcessPool for CPU | Bypass GIL |
| Async for I/O only | 1,400x overhead |
