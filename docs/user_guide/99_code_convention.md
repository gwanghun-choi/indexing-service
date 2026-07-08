# Code Convention Guide

> **Scope**: indexing-service project

---

## 1. Environment

```bash
# macOS
/opt/anaconda3/condabin/conda run -n Indexing python your_script.py
/opt/anaconda3/condabin/conda run -n Indexing pytest tests/

# WSL
/root/anaconda3/bin/conda run -n Indexing python your_script.py
/root/anaconda3/bin/conda run -n Indexing pytest tests/

# Install libraries (latest version only, no version pinning)
pip install {library_name}
pip freeze > requirements.txt
```

**Server Environment:**

| Service | Local Port (211.188.60.43) |
|---------|---------------------------|
| Milvus | 19530 |
| Redis | 16379 |
| OpenSearch | 19200 |
| PostgreSQL | 5432 |

---

## 2. Core Principles

| Principle | Do | Don't |
|-----------|-----|-------|
| Dict Access | `data["key"]` (Fail Fast) | `data.get("key", default)` |
| Env Vars | `os.getenv("VAR")` | `os.getenv("VAR", "default")` |
| Import | Top of file | Lazy import in functions |
| Output | `logger.info(f"...")` | `print()` |
| String | f-string | `.format()`, `%` |
| Global | Pass as parameters | `global variable` |
| Class | When state needed | Static methods only |

---

## 3. Import Order

```python
# 1. Standard Library
import logging
from typing import Any, Dict, List

# 2. Third-Party
from fastapi import APIRouter
from pymilvus import Collection

# 3. Custom (Local)
from app.config.settings import get_settings
```

One blank line between sections, alphabetical order within each.

---

## 4. Naming

| Target | Rule | Example |
|--------|------|---------|
| Function | `verb_object` | `get_user()`, `create_model()` |
| Variable | snake_case | `user_count`, `is_enabled` |
| Constant | UPPER_SNAKE | `MAX_RETRY_COUNT` |
| Boolean | `is_`, `has_` prefix | `is_admin`, `has_role` |
| List | Plural | `users`, `documents` |

**Common Verbs:**

| Verb | Usage | Verb | Usage |
|------|-------|------|-------|
| `get` | Single retrieval | `select` | DB query |
| `create` | Creation | `update` | Modification |
| `delete` | DB deletion | `remove` | File/cache removal |
| `load` | Load to memory | `unload` | Unload from memory |
| `parse` | Parsing | `validate` | Validation |

**Verbs by Layer:**

| Layer | Verbs |
|-------|-------|
| CRUD | `create`, `select`, `update`, `delete` |
| Service | `download`, `remove`, `load`, `unload`, `enable` |

**Don't:**
```python
usr_id = 123      # Bad: abbreviation → user_id
mdl_nm = "..."    # Bad: abbreviation → model_name
x = get_user()    # Bad: meaningless → user
temp = calc()     # Bad: meaningless → score
```

---

## 5. Type Hints & Docstring

```python
def search_documents(
    client: Elasticsearch,
    query: str,
    top_k: int = 10,
) -> List[Dict[str, Any]]:
    """
    Perform document search.

    Args:
        client: Elasticsearch client
        query: Search query
        top_k: Maximum number of documents to return

    Returns:
        List of search result documents
    """
    pass
```

---

## 6. Utils Separation

| Move to utils | Keep in place |
|---------------|---------------|
| Data transformation | Business logic → service/ |
| General utilities | DB operations → crud/ |
| Parsers, validators | API handlers → api/ |

**Criteria:** Reused in 2+ places OR simple transformation → move to utils

---

## 7. Context Manager Usage

- Use `@contextmanager` when a resource must be reliably released.
- Keep the scope minimal and include type hints + docstring.

```python
from contextlib import contextmanager
from typing import Iterator

@contextmanager
def acquire_lock(lock) -> Iterator[None]:
    """
    Acquire and release a lock safely.
    """
    lock.acquire()
    try:
        yield
    finally:
        lock.release()
```

---

## 8. Clean Code

### 7.1 Metrics

| Metric | Recommended | Max |
|--------|-------------|-----|
| Function lines | ≤ 20 | 50 |
| Cyclomatic complexity | ≤ 5 | 10 |
| Parameters | ≤ 4 | 6 |
| Nesting depth | ≤ 2 | 3 |

### 7.2 Patterns

```python
# Early Return - flatten nested conditions
def process(data):
    if not data:
        return None
    if not data.is_valid:
        return None
    return do_something(data)

# Single Responsibility - one function, one job
def validate_user(data): ...
def save_user(data): ...
def notify_user(user): ...

# No Magic Numbers
BULK_THRESHOLD = 100
DISCOUNT_RATE = 0.85
```

---

## 9. Error Handling

```python
# Specific exceptions
try:
    result = process(data)
except KeyError as e:
    logger.error(f"Missing key: {e}")
    raise

# Exception hierarchy
class AppError(Exception): pass
class ValidationError(AppError): pass
class NotFoundError(AppError): pass
```

| Style | When |
|-------|------|
| EAFP (try/except) | Exception is rare |
| LBYL (if check) | Check is cheap, exception common |

---

## 10. Testing

```python
# Naming: test_<method>_<scenario>_<expected>
def test_create_user_with_valid_email_returns_user(): ...

# AAA Pattern
def test_calculate_discount():
    # Arrange
    order = Order(quantity=150)
    # Act
    result = calc.total(order)
    # Assert
    assert result == 1275.0
```

---

## 11. Quick Reference

### Clean Code Checklist

| Rule |
|------|
| Single responsibility |
| ≤ 20 lines per function |
| ≤ 4 parameters |
| ≤ 2 nesting levels |
| Early return |
| No magic numbers |
| No abbreviations |
| `verb_object` naming |
| Specific exceptions |
| Import order: std → 3rd → local |
