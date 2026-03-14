# supabase-lite

> In-memory Supabase client for testing. Zero infrastructure, drop-in replacement for `supabase-py`.

Like Qdrant's `client(":memory:")`, but for Supabase.

```python
from supabase_lite import create_client

client = create_client(":memory:")

client.from_("users").insert({"id": 1, "name": "Alice"}).execute()

result = client.from_("users").select("*").eq("name", "Alice").single().execute()
print(result.data)  # {"id": 1, "name": "Alice"}
```

## Why?

- **No Docker** — no `supabase start`, no containers, no waiting
- **No network** — everything runs in-process with SQLite
- **No config** — one line to get a working client
- **Same API** — mirrors `supabase-py`'s query builder interface
- **Auto-creates tables** — just insert data, tables and columns appear automatically

## Install

```bash
pip install git+https://github.com/acelikyurek/supabase-py-lite
```

## Usage

```python
from supabase_lite import create_client

# In-memory (for testing)
client = create_client(":memory:")

# File-based (for persistence)
client = create_client("./my_app.db")
```

### Insert

```python
client.from_("users").insert({"id": 1, "name": "Alice", "age": 30}).execute()

# Batch insert
client.from_("users").insert([
    {"id": 2, "name": "Bob", "age": 25},
    {"id": 3, "name": "Charlie", "age": 35},
]).execute()
```

### Select

```python
# All rows
res = client.from_("users").select("*").execute()

# Specific columns
res = client.from_("users").select("id, name").execute()

# With count
res = client.from_("users").select("*", count="exact").execute()
print(res.count)  # 3

# Single row
res = client.from_("users").select("*").eq("id", 1).single().execute()
print(res.data)  # {"id": 1, "name": "Alice", "age": 30}

# Maybe single (returns None instead of raising)
res = client.from_("users").select("*").eq("id", 999).maybe_single().execute()
print(res.data)  # None
```

### Filters

```python
.eq("col", value)        # col = value
.neq("col", value)       # col != value
.gt("col", value)        # col > value
.gte("col", value)       # col >= value
.lt("col", value)        # col < value
.lte("col", value)       # col <= value
.in_("col", [a, b])      # col IN (a, b)
.like("col", "A%")       # col LIKE 'A%'
.ilike("col", "a%")      # case-insensitive LIKE
.is_("col", None)        # col IS NULL
.contains("col", val)    # JSON array contains val

# Chain them
res = (
    client.from_("users")
    .select("*")
    .gte("age", 25)
    .lte("age", 35)
    .order("age", ascending=False)
    .limit(10)
    .execute()
)
```

### Update

```python
client.from_("users").update({"name": "Alicia"}).eq("id", 1).execute()
```

### Delete

```python
client.from_("users").delete().eq("id", 1).execute()
```

### Upsert

```python
client.from_("users").upsert({"id": 1, "name": "Alice v2"}).execute()

# Custom conflict column
client.from_("users").upsert(
    {"email": "a@b.com", "name": "A"}, on_conflict="email"
).execute()
```

### JSON columns

```python
client.from_("posts").insert({
    "id": 1,
    "meta": {"tags": ["python", "supabase"], "draft": False}
}).execute()

res = client.from_("posts").select("*").eq("id", 1).execute()
print(res.data[0]["meta"]["tags"])  # ["python", "supabase"]
```

## Use in tests

```python
import pytest
from supabase_lite import create_client

@pytest.fixture
def db():
    client = create_client(":memory:")
    yield client
    client.close()

def test_create_user(db):
    db.from_("users").insert({"id": 1, "name": "Alice"}).execute()
    res = db.from_("users").select("*").eq("id", 1).single().execute()
    assert res.data["name"] == "Alice"
```

## Supported API

| Method | Status |
|--------|--------|
| `.from_() / .table()` | ✅ |
| `.select()` | ✅ |
| `.insert()` | ✅ |
| `.update()` | ✅ |
| `.delete()` | ✅ |
| `.upsert()` | ✅ |
| `.eq/.neq/.gt/.gte/.lt/.lte` | ✅ |
| `.in_/.like/.ilike/.is_` | ✅ |
| `.contains` | ✅ |
| `.order/.limit/.offset/.range` | ✅ |
| `.single/.maybe_single` | ✅ |
| `count="exact"` | ✅ |
| JSON columns | ✅ |
| Auto-create tables | ✅ |
| Foreign key joins | 🚧 Planned |
| `.or_() / .not_()` | 🚧 Planned |

## Development

```bash
git clone https://github.com/acelikyurek/supabase-lite
cd supabase-lite
uv sync --group dev
uv run pytest -v
```

## License

MIT
