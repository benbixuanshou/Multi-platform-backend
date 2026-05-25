# MySQL Schema Conventions

## Database config
```sql
CREATE DATABASE IF NOT EXISTS comment_platform
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

## Table template
```sql
CREATE TABLE table_name (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    field_name TYPE CONSTRAINTS,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ref_id) REFERENCES other_table(id) ON DELETE CASCADE,
    UNIQUE KEY uk_name (field1, field2),
    INDEX idx_name (field1)
) ENGINE=InnoDB;
```

## Type reference
- UUID primary: `CHAR(36) DEFAULT (UUID())`
- Short strings: `VARCHAR(N)` (specify max length)
- Long text: `TEXT`
- JSON: `JSON`
- Boolean: `BOOLEAN DEFAULT FALSE`
- Timestamps: `TIMESTAMP DEFAULT CURRENT_TIMESTAMP` or `TIMESTAMP NULL`
- Decimals: `DECIMAL(10,6)` for cost/precision values

## Foreign key convention
Always specify ON DELETE behavior:
```sql
FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
FOREIGN KEY (agent_task_id) REFERENCES agent_tasks(id) ON DELETE SET NULL,
```

## Current tables (9 tables)
1. `users`
2. `platform_accounts`
3. `posts`
4. `comments`
5. `agent_tasks`
6. `reply_drafts`
7. `agent_logs`
8. `reply_edit_log`
9. `reply_performance`

Plus: `security_audit_log`
