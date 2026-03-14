class SupabaseLiteError(Exception):
    """Base exception for supabase-lite."""


class TableNotFoundError(SupabaseLiteError):
    """Raised when querying a table that doesn't exist and auto-create is off."""


class QueryError(SupabaseLiteError):
    """Raised when a query fails."""


class SingleRowError(SupabaseLiteError):
    """Raised when .single() returns zero or multiple rows."""
