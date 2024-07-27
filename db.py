import sqlite3
import contextlib


# SQLite `with` context for managing simple transactions.
#
# Usage:
# with Transaction(con) as tx:  <-- `tx` is a cursor, implicit BEGIN
#       tx.execute(...)
#       tx.execute(...)
#       some_fn(tx)
#
# --> Implicit COMMIT when scope is exited.
#     If the scope exits due to an exception ROLLBACK instead.
#
# When leaving the scope COMMIT/ROLLBACK is always called,
# so you shouldn't use explicit transaction control statements
# inside of the scope; use a raw cursor instead.
class Transaction:
    def __init__(self, con):
        self.cursor = con.cursor()

    def __enter__(self):
        self.cursor.execute("BEGIN")
        return self.cursor

    def __exit__(self, exc_type, exc_value, exc_tb):
        try:
            if exc_type is None:
                self.cursor.execute("COMMIT")
            else:
                self.cursor.execute("ROLLBACK")
        finally:
            self.cursor.close()


_schema_version_latest = 1
_schema_statements = f"""
CREATE TABLE IF NOT EXISTS database_metadata (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL
) STRICT, WITHOUT ROWID;

INSERT OR IGNORE INTO database_metadata (key, value)
VALUES ('version', '{_schema_version_latest}');


CREATE TABLE IF NOT EXISTS file (
    id              INTEGER NOT NULL PRIMARY KEY,
    absolute_path   TEXT    NOT NULL UNIQUE,
    last_indexed    INTEGER NOT NULL,
    word_count      INTEGER NOT NULL DEFAULT 0,
    exist           INTEGER NOT NULL
) STRICT;
CREATE UNIQUE INDEX IF NOT EXISTS unique_file_path ON file(absolute_path);

-- REAL columns can't have default values, so default is NULL.
-- This is fixed in a more recent version of SQLite.
CREATE TABLE IF NOT EXISTS word (
    id      INTEGER NOT NULL PRIMARY KEY,
    text    TEXT    NOT NULL UNIQUE,
    idf     REAL    DEFAULT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS word_in_file (
    file_id INTEGER NOT NULL,
    word_id INTEGER NOT NULL,
    count   INTEGER NOT NULL DEFAULT 0,

    PRIMARY KEY (file_id, word_id),
    FOREIGN KEY (file_id) REFERENCES file(id) ON DELETE CASCADE,
    FOREIGN KEY (word_id) REFERENCES word(id)
) STRICT, WITHOUT ROWID;
"""


# Opens an SQLite connection with "sane default" pragmas:
# - sets the journaling mode to WAL
# - sets the sync mode to NORMAL
# - sets the encoding to UTF-8
# - enables mandatory foreign key checks
# - enables case sensitive like (which enables using an index with LIKE).
# Most of these pragmas are either the default, or they really should be.
# For more information see: # https://www.sqlite.org/pragma.html
def _set_sqlite_pragmas(con, *, is_in_memory):
    with contextlib.closing(con.cursor()) as cur:
        # If a pragma is set to a different value
        # and the database schema already exist,
        # the PRAGMA command will fail, and we will raise an exception.
        cur.execute("PRAGMA encoding='UTF-8'")
        encoding = cur.execute("PRAGMA encoding").fetchone()[0]
        if encoding != "UTF-8":
            raise sqlite3.OperationalError(f"Can't change encoding from '{encoding}' to 'UTF-8'.")

        # Wal can't be set if the database is in-memory,
        # and passing ':memory:' is the only way to create an in memory db.
        if not is_in_memory:
            cur.execute("PRAGMA journal_mode=wal")
            journal_mode = cur.execute("PRAGMA journal_mode").fetchone()[0]
            if journal_mode != "wal":
                raise sqlite3.OperationalError("Can't change journal mode " f"from '{journal_mode}' to 'wal'.")

        cur.execute("PRAGMA synchronous=NORMAL")
        sync_mode = cur.execute("PRAGMA synchronous").fetchone()[0]
        if sync_mode != 1:
            raise sqlite3.OperationalError(f"Can't change sync mode from '{sync_mode}' to '1'.")

        cur.execute("PRAGMA foreign_keys=1")
        fk_on = cur.execute("PRAGMA foreign_keys").fetchone()[0]
        if fk_on != 1:
            raise sqlite3.OperationalError(f"Can't enable foreign keys! foreign_keys={fk_on}")

        # This is necessary for attempted use of full-text indices
        # when using LIKE 'prefix%'
        # This pragma can't be queried, it "just works".
        cur.execute("PRAGMA case_sensitive_like=1")

    return con


def _open_index_sqlite_connection(path_str):
    def get_schema_set(tx):
        tx.execute("""
            SELECT  type, name, sql
            FROM    sqlite_master
            ORDER   BY type, name""")
        return set(tx.fetchall())

    try:
        is_in_memory = path_str.strip() == ":memory:"
        con = sqlite3.connect(path_str)
        _set_sqlite_pragmas(con, is_in_memory=is_in_memory)

        with contextlib.closing(con.cursor()) as cur:
            # Create the tables if they don't exist.
            # Also sets the schema version in database_metadata.
            cur.executescript(_schema_statements)

        # For extra schema verification,
        # alongside checking the `version` key from `database_metadata`,
        # create a temporary in-memory database with the correct schema
        # and check if the schemas match.

        with Transaction(con) as tx:
            rows = tx.execute("SELECT value FROM database_metadata WHERE key = 'version'")
            version = int(rows.fetchone()[0])
            if version != _schema_version_latest:
                raise sqlite3.OperationalError(
                    f"DB version is {version}, " f"but latest version is {_schema_version_latest}"
                )

            schema_actual_db = get_schema_set(tx)

        tmp_con = sqlite3.connect(":memory:")
        _set_sqlite_pragmas(tmp_con, is_in_memory=True)
        with contextlib.closing(tmp_con.cursor()) as cur:
            cur.executescript(_schema_statements)
            schema_temp_db = get_schema_set(cur)

        if schema_temp_db != schema_actual_db:
            raise sqlite3.OperationalError("DB Schemas doesn't match.")
    except Exception as e:
        con.close()
        raise e

    return con
