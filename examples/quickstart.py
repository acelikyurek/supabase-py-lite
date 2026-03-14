"""Quickstart example for supabase-lite."""

from supabase_py_lite import create_client

# Create an in-memory client — no Docker, no server, no config
client = create_client(":memory:")

# Insert data — tables are auto-created
client.from_("users").insert([
    {"id": 1, "name": "Alice", "email": "alice@example.com", "age": 30},
    {"id": 2, "name": "Bob", "email": "bob@example.com", "age": 25},
    {"id": 3, "name": "Charlie", "email": "charlie@example.com", "age": 35},
]).execute()

# Select all
res = client.from_("users").select("*").execute()
print(f"All users ({len(res.data)}):")
for user in res.data:
    print(f"  {user}")

# Select with filters
res = client.from_("users").select("name, age").gt("age", 28).order("age").execute()
print(f"\nUsers older than 28: {res.data}")

# Select single row
res = client.from_("users").select("*").eq("id", 1).single().execute()
print(f"\nUser #1: {res.data}")

# Count
res = client.from_("users").select("*", count="exact").execute()
print(f"\nTotal count: {res.count}")

# Update
client.from_("users").update({"name": "Alicia"}).eq("id", 1).execute()
res = client.from_("users").select("name").eq("id", 1).single().execute()
print(f"\nAfter update: {res.data}")

# Upsert
client.from_("users").upsert({"id": 1, "name": "Alice", "age": 31}).execute()
res = client.from_("users").select("*").eq("id", 1).single().execute()
print(f"\nAfter upsert: {res.data}")

# Delete
deleted = client.from_("users").delete().eq("id", 3).execute()
print(f"\nDeleted: {deleted.data}")
res = client.from_("users").select("*").execute()
print(f"Remaining users: {len(res.data)}")

# JSON columns work too
client.from_("posts").insert({
    "id": 1,
    "title": "Hello World",
    "meta": {"tags": ["python", "supabase"], "draft": False},
}).execute()
res = client.from_("posts").select("*").eq("id", 1).single().execute()
print(f"\nPost with JSON meta: {res.data}")

client.close()
print("\n✓ Done!")
