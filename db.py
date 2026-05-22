"""Postgres-backed key/value store for user data (Neon-compatible).

Falls back to local JSON file when NEON_DATABASE_URL is not set, so dev/offline
still works. All access is via load_users() / save_users() to match the legacy
file-based API one-for-one.
"""
import os, json, threading, time

NEON_URL = os.environ.get('NEON_DATABASE_URL', '').strip()
USERS_FILE = 'users.json'
_USERS_KEY = 'users'

_pg_lock = threading.RLock()
_conn = None


def _connect():
    global _conn
    import psycopg2
    if _conn is not None:
        try:
            with _conn.cursor() as cur:
                cur.execute('SELECT 1')
            return _conn
        except Exception:
            try: _conn.close()
            except Exception: pass
            _conn = None
    _conn = psycopg2.connect(NEON_URL, connect_timeout=10)
    _conn.autocommit = True
    with _conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS app_data (
                key   TEXT PRIMARY KEY,
                value JSONB NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
    return _conn


def _pg_get(key):
    with _pg_lock:
        for attempt in range(3):
            try:
                conn = _connect()
                with conn.cursor() as cur:
                    cur.execute("SELECT value FROM app_data WHERE key=%s", (key,))
                    row = cur.fetchone()
                    return row[0] if row else None
            except Exception:
                global _conn
                try:
                    if _conn: _conn.close()
                except Exception: pass
                _conn = None
                if attempt == 2: raise
                time.sleep(0.3 * (attempt + 1))


def _pg_set(key, value):
    payload = json.dumps(value)
    with _pg_lock:
        for attempt in range(3):
            try:
                conn = _connect()
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO app_data (key, value, updated_at)
                        VALUES (%s, %s::jsonb, now())
                        ON CONFLICT (key) DO UPDATE
                          SET value = EXCLUDED.value, updated_at = now()
                    """, (key, payload))
                return
            except Exception:
                global _conn
                try:
                    if _conn: _conn.close()
                except Exception: pass
                _conn = None
                if attempt == 2: raise
                time.sleep(0.3 * (attempt + 1))


def _file_load():
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}


def _file_save(users):
    tmp = USERS_FILE + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(users, f, indent=2)
    os.replace(tmp, USERS_FILE)


def using_postgres():
    return bool(NEON_URL)


def seed_if_empty():
    """If Postgres is configured and empty, copy users.json into the DB once."""
    if not using_postgres():
        return
    try:
        existing = _pg_get(_USERS_KEY)
    except Exception as e:
        print(f"[db] seed check failed: {e}")
        return
    if existing is None:
        local = _file_load()
        try:
            _pg_set(_USERS_KEY, local)
            print(f"[db] seeded Postgres with {len(local)} users from {USERS_FILE}")
        except Exception as e:
            print(f"[db] seed write failed: {e}")


def load_users():
    if using_postgres():
        # No silent fallback — local file on a stateless host would diverge from DB.
        data = _pg_get(_USERS_KEY)
        return data if isinstance(data, dict) else {}
    return _file_load()


def save_users(users):
    if using_postgres():
        # Raise loudly on DB failure rather than writing to ephemeral local FS.
        _pg_set(_USERS_KEY, users)
        return
    _file_save(users)
