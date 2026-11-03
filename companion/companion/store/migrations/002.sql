CREATE TABLE cognitive_jobs (
 job_id TEXT PRIMARY KEY, user_key TEXT NOT NULL REFERENCES users(user_key),
 session_id TEXT NOT NULL REFERENCES sessions(session_id), kind TEXT NOT NULL,
 status TEXT NOT NULL, priority INTEGER NOT NULL, queued_at TEXT NOT NULL,
 started_at TEXT, finished_at TEXT, source_turn_id INTEGER NOT NULL,
 data TEXT NOT NULL, result TEXT, error TEXT
);
CREATE INDEX jobs_queue ON cognitive_jobs(status,priority,queued_at);
CREATE TABLE agent_runs (
 run_id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES cognitive_jobs(job_id) ON DELETE CASCADE,
 role TEXT NOT NULL, attempt INTEGER NOT NULL, model TEXT NOT NULL, prompt_version TEXT NOT NULL,
 candidate_version INTEGER, started_at TEXT NOT NULL, duration_ms REAL,
 status TEXT NOT NULL, usage TEXT NOT NULL, result TEXT, error TEXT
);
CREATE TABLE support_plans (
 plan_id TEXT NOT NULL, version INTEGER NOT NULL, user_key TEXT NOT NULL REFERENCES users(user_key),
 session_id TEXT NOT NULL REFERENCES sessions(session_id), status TEXT NOT NULL,
 valid_until TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY(plan_id,version), UNIQUE(session_id,version)
);
CREATE INDEX plans_session ON support_plans(session_id,status,version);
CREATE TABLE interaction_events (
 event_id TEXT PRIMARY KEY, idempotency_key TEXT NOT NULL UNIQUE,
 user_key TEXT NOT NULL REFERENCES users(user_key), session_id TEXT NOT NULL REFERENCES sessions(session_id),
 turn_id INTEGER REFERENCES turns(id), event_type TEXT NOT NULL, origin TEXT NOT NULL,
 recorded_at TEXT NOT NULL, data TEXT NOT NULL
);
CREATE INDEX interactions_user ON interaction_events(user_key,session_id,turn_id);
CREATE TABLE memory_items (
 memory_id TEXT PRIMARY KEY, user_key TEXT NOT NULL REFERENCES users(user_key), kind TEXT NOT NULL,
 key TEXT NOT NULL, scope TEXT NOT NULL, scope_ref TEXT, expires_at TEXT,
 status TEXT NOT NULL, version INTEGER NOT NULL, supersedes_id TEXT REFERENCES memory_items(memory_id),
 source_cursor INTEGER NOT NULL, data TEXT NOT NULL, legacy_key TEXT UNIQUE
);
CREATE INDEX memory_user ON memory_items(user_key,status,kind,key);
CREATE INDEX memory_scope ON memory_items(user_key,scope,expires_at);
CREATE TABLE memory_sources (
 memory_id TEXT NOT NULL REFERENCES memory_items(memory_id) ON DELETE CASCADE,
 source_type TEXT NOT NULL, source_id TEXT NOT NULL,
 PRIMARY KEY(memory_id,source_type,source_id)
);
CREATE TABLE user_revisions (
 user_key TEXT PRIMARY KEY REFERENCES users(user_key), memory_revision INTEGER NOT NULL DEFAULT 0,
 boundary_revision INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE turn_policies (
 turn_id INTEGER PRIMARY KEY REFERENCES turns(id) ON DELETE CASCADE,
 session_id TEXT NOT NULL REFERENCES sessions(session_id), data TEXT NOT NULL
);
INSERT INTO user_revisions(user_key) SELECT user_key FROM users;
CREATE TABLE memory_corrections (
 user_key TEXT NOT NULL REFERENCES users(user_key), kind TEXT NOT NULL, key TEXT NOT NULL,
 source_turn_id INTEGER NOT NULL REFERENCES turns(id), PRIMARY KEY(user_key,kind,key)
);
