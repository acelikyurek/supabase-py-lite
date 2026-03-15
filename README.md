# supabase-py-lite

> In-memory Supabase client for testing. Zero infrastructure, drop-in replacement for `supabase-py`.

Like Qdrant's `client(":memory:")`, but for Supabase.

```python
from supabase_py_lite import create_client

supabase_client = create_client(":memory:")

supabase_client.table("users").insert({"id": 1, "name": "Alice"}).execute()

result = supabase_client.table("users").select("*").eq("name", "Alice").single().execute()
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
from supabase_py_lite import create_client

# In-memory (for testing)
supabase_client = create_client(":memory:")

# File-based (for persistence)
supabase_client = create_client("./my_app.db")
```

### Insert

```python
supabase_client.table("users").insert({"id": 1, "name": "Alice", "age": 30}).execute()

# Batch insert
supabase_client.table("users").insert([
    {"id": 2, "name": "Bob", "age": 25},
    {"id": 3, "name": "Charlie", "age": 35},
]).execute()
```

### Select

```python
# All rows
res = supabase_client.table("users").select("*").execute()

# Specific columns
res = supabase_client.table("users").select("id, name").execute()

# With count
res = supabase_client.table("users").select("*", count="exact").execute()
print(res.count)  # 3

# Single row
res = supabase_client.table("users").select("*").eq("id", 1).single().execute()
print(res.data)  # {"id": 1, "name": "Alice", "age": 30}

# Maybe single (returns None instead of raising)
res = supabase_client.table("users").select("*").eq("id", 999).maybe_single().execute()
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
    supabase_client.table("users")
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
supabase_client.table("users").update({"name": "Alicia"}).eq("id", 1).execute()
```

### Delete

```python
supabase_client.table("users").delete().eq("id", 1).execute()
```

### Upsert

```python
supabase_client.table("users").upsert({"id": 1, "name": "Alice v2"}).execute()

# Custom conflict column
supabase_client.table("users").upsert(
    {"email": "a@b.com", "name": "A"}, on_conflict="email"
).execute()
```

### JSON columns

```python
supabase_client.table("posts").insert({
    "id": 1,
    "meta": {"tags": ["python", "supabase"], "draft": False}
}).execute()

res = supabase_client.table("posts").select("*").eq("id", 1).execute()
print(res.data[0]["meta"]["tags"])  # ["python", "supabase"]
```

### Foreign Keys

Register FK relationships with `define_foreign_key`, then use embedded resource syntax in `.select()` to join related data — exactly like Supabase.

```python
# posts.user_id -> users.id
supabase_client.define_foreign_key("posts", "user_id", "users")

# comments.post_id -> posts.id
supabase_client.define_foreign_key("comments", "post_id", "posts")
```

**Many-to-one** (FK on current table → embeds as a single object):

```python
res = supabase_client.table("posts").select("id, title, users(name, email)").execute()
# [{"id": 1, "title": "Hello", "users": {"name": "Alice", "email": "alice@example.com"}}, ...]
```

**One-to-many** (FK on related table → embeds as a list):

```python
res = supabase_client.table("posts").select("id, title, comments(body)").execute()
# [{"id": 1, "title": "Hello", "comments": [{"body": "Great post!"}, ...]}, ...]
```

**Wildcard on main table:**

```python
res = supabase_client.table("posts").select("*, users(name)").execute()
```

**Alias** — rename the embedded key in the result:

```python
res = supabase_client.table("posts").select("id, author:users(name)").execute()
# [{"id": 1, "author": {"name": "Alice"}}, ...]
```

**Hint** — explicitly specify which FK column to use (useful when multiple FKs point to the same table):

```python
res = supabase_client.table("posts").select("id, users!user_id(name)").execute()
```

**Multiple embeds in one query:**

```python
res = supabase_client.table("posts").select("id, users(name), comments(body)").execute()
```

> The FK join column is added to the query automatically if needed and stripped from the result unless you selected it explicitly.

## Use in tests

```python
import pytest
from supabase_py_lite import create_client

@pytest.fixture
def db():
    supabase_client = create_client(":memory:")
    yield supabase_client
    supabase_client.close()

def test_create_user(db):
    db.table("users").insert({"id": 1, "name": "Alice"}).execute()
    res = db.table("users").select("*").eq("id", 1).single().execute()
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
| Foreign key joins | ✅ |
| `.or_()` | ✅ |
| `.not_()` | ✅ |

## Development

```bash
git clone https://github.com/acelikyurek/supabase-py-lite
cd supabase-py-lite
uv sync --group dev
uv run pytest -v
```

## License

MIT
