---
name: migration-review
description: Creates and reviews MySQL database migrations for this project. Use when the user asks to "add a table", "add a column", "change the schema", "create a migration", "write DDL", or mentions database changes, ALTER TABLE, or new fields.
---

# Migration Review

## Purpose

Ensure every database migration follows this project's conventions. Catch errors before they hit production.

## When to Activate

- User asks to create, modify, or delete database tables/columns
- User writes DDL or asks for help writing DDL
- User mentions `ALTER TABLE`, `CREATE TABLE`, schema changes

## Migration Conventions

Every migration file must follow these rules. See [references/schema-conventions.md](references/schema-conventions.md) for the full specification.

### Mandatory Rules

1. **Primary key**: Always `id CHAR(36) PRIMARY KEY DEFAULT (UUID())`. Never AUTO_INCREMENT.
2. **Timestamps**: Use `TIMESTAMP DEFAULT CURRENT_TIMESTAMP`. Never DATETIME.
3. **Engine**: `ENGINE=InnoDB` on every CREATE TABLE.
4. **Charset**: `utf8mb4` + `utf8mb4_unicode_ci` at database and table level.
5. **Foreign keys**: Must include `ON DELETE CASCADE` or `ON DELETE SET NULL`. Never omit.
6. **JSON columns**: Use `JSON` type (MySQL 8.0+), not TEXT with JSON content.
7. **Boolean**: Use `BOOLEAN DEFAULT FALSE/TRUE`, not TINYINT(1).
8. **Indexes**: Every table needs at minimum: primary key index + indexes on all foreign key columns + indexes on columns used in WHERE clauses.

### Naming Conventions

- Table names: snake_case plural (`reply_drafts`, `agent_tasks`)
- Column names: snake_case (`platform_user_id`, `created_at`)
- Index names: `idx_<table>_<columns>` (`idx_comments_post_status`)
- Unique keys: `uk_<table>_<columns>` (`uk_platform_comment`)
- Foreign keys: `<referencing>_<referenced>` inferred, not explicitly named

### Migration File Naming

`backend/migrations/{NNN}_{description}.sql` where `NNN` is zero-padded sequential number.

## Before Committing

- [ ] Run against local MySQL: `docker compose exec mysql mysql -u root -p < migration.sql`
- [ ] Verify no existing data loss (new columns have DEFAULT or are nullable)
- [ ] Add corresponding index for any new column used in WHERE/JOIN/ORDER BY
- [ ] Update `references/schema-conventions.md` if adding a new pattern
