-- ============================================================
-- Multi-platform Comment Management Platform
-- MySQL 8.0 DDL Migration (from golden-seeking-lobster.md)
-- ============================================================

CREATE DATABASE IF NOT EXISTS comment_platform
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE comment_platform;

-- ============================================================
-- 1. Users & Platform Accounts
-- ============================================================

CREATE TABLE users (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(128),
    creator_tone VARCHAR(32) DEFAULT 'casual',
    creator_phrases TEXT,
    creator_bio TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE platform_accounts (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    user_id CHAR(36) NOT NULL,
    platform VARCHAR(32) NOT NULL,
    platform_user_id VARCHAR(128) NOT NULL,
    platform_username VARCHAR(128),
    access_token TEXT,
    refresh_token TEXT,
    token_expires_at TIMESTAMP NULL,
    cookie_data JSON,
    is_active BOOLEAN DEFAULT TRUE,
    last_synced_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY uk_user_platform (user_id, platform)
) ENGINE=InnoDB;

-- ============================================================
-- 2. Posts
-- ============================================================

CREATE TABLE posts (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    user_id CHAR(36) NOT NULL,
    platform VARCHAR(32) NOT NULL,
    platform_post_id VARCHAR(128) NOT NULL,
    title TEXT,
    url TEXT,
    thumbnail_url TEXT,
    content_summary TEXT,
    published_at TIMESTAMP NULL,
    comment_count INT DEFAULT 0,
    last_comment_fetch_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY uk_platform_post (platform, platform_post_id)
) ENGINE=InnoDB;

-- ============================================================
-- 3. Comments (core table)
-- ============================================================

CREATE TABLE comments (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    post_id CHAR(36) NOT NULL,
    platform VARCHAR(32) NOT NULL,
    platform_comment_id VARCHAR(128) NOT NULL,
    parent_comment_id CHAR(36) NULL,
    parent_platform_comment_id VARCHAR(128),
    parent_comment_content TEXT,
    platform_user_id VARCHAR(128) NOT NULL,
    platform_username VARCHAR(256),
    platform_avatar_url TEXT,
    content TEXT NOT NULL,
    image_urls JSON DEFAULT ('[]'),
    like_count INT DEFAULT 0,
    reply_count INT DEFAULT 0,
    is_from_creator BOOLEAN DEFAULT FALSE,
    is_pinned BOOLEAN DEFAULT FALSE,
    status VARCHAR(32) DEFAULT 'pending',
    classification VARCHAR(32),
    intent VARCHAR(64),
    intent_detail VARCHAR(128),
    sentiment VARCHAR(16),
    urgency VARCHAR(16),
    platform_created_at TIMESTAMP NULL,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_comment_id) REFERENCES comments(id) ON DELETE SET NULL,
    UNIQUE KEY uk_platform_comment (platform, platform_comment_id),
    INDEX idx_comments_post_status (post_id, status),
    INDEX idx_comments_platform_user (platform, platform_user_id),
    INDEX idx_comments_fetched (fetched_at),
    INDEX idx_comments_classification (classification, intent),
    INDEX idx_comments_status_urgency (status, urgency)
) ENGINE=InnoDB;

-- ============================================================
-- 4. Agent Tasks (agent communication via DB queue)
-- ============================================================

CREATE TABLE agent_tasks (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    comment_id CHAR(36),
    task_type VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    priority INT NOT NULL DEFAULT 0,
    payload JSON NOT NULL DEFAULT ('{}'),
    result JSON,
    agent_name VARCHAR(64),
    llm_model VARCHAR(64),
    prompt_version VARCHAR(32),
    llm_tokens INT,
    llm_duration_ms INT,
    error_message TEXT,
    retries INT DEFAULT 0,
    max_retries INT DEFAULT 3,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP NULL,
    completed_at TIMESTAMP NULL,
    FOREIGN KEY (comment_id) REFERENCES comments(id) ON DELETE CASCADE,
    INDEX idx_agent_tasks_fetch (task_type, status, priority DESC, created_at),
    INDEX idx_agent_tasks_comment (comment_id, task_type)
) ENGINE=InnoDB;

-- ============================================================
-- 5. Reply Drafts
-- ============================================================

CREATE TABLE reply_drafts (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    comment_id CHAR(36) NOT NULL,
    agent_task_id CHAR(36),
    style VARCHAR(32) NOT NULL,
    content TEXT NOT NULL,
    is_adopted BOOLEAN DEFAULT FALSE,
    is_edited BOOLEAN DEFAULT FALSE,
    edited_content TEXT,
    risk_warning VARCHAR(255),
    recommended BOOLEAN DEFAULT FALSE,
    sent_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (comment_id) REFERENCES comments(id) ON DELETE CASCADE,
    FOREIGN KEY (agent_task_id) REFERENCES agent_tasks(id) ON DELETE SET NULL,
    INDEX idx_drafts_comment (comment_id)
) ENGINE=InnoDB;

-- ============================================================
-- 6. Agent Execution Logs
-- ============================================================

CREATE TABLE agent_logs (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    agent_name VARCHAR(64) NOT NULL,
    task_id CHAR(36),
    model VARCHAR(64) NOT NULL,
    prompt_version VARCHAR(32),
    prompt_tokens INT NOT NULL,
    completion_tokens INT NOT NULL,
    total_tokens INT NOT NULL,
    duration_ms INT NOT NULL,
    confidence DECIMAL(3,2),
    tool_name VARCHAR(64),
    tool_duration_ms INT,
    checkpoint BOOLEAN DEFAULT FALSE,
    cost_estimate_usd DECIMAL(10,6),
    success BOOLEAN NOT NULL,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES agent_tasks(id) ON DELETE SET NULL,
    INDEX idx_agent_logs_agent (agent_name, created_at),
    INDEX idx_agent_logs_tool (tool_name, created_at),
    INDEX idx_agent_logs_success (success, created_at)
) ENGINE=InnoDB;

-- ============================================================
-- 7. Episodic Memory: Reply Edit Log (Harness Module 4 + 9)
-- ============================================================

CREATE TABLE reply_edit_log (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    comment_id CHAR(36),
    original_draft TEXT NOT NULL,
    edited_content TEXT NOT NULL,
    classification VARCHAR(32),
    intent VARCHAR(32),
    diff_summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (comment_id) REFERENCES comments(id) ON DELETE SET NULL,
    INDEX idx_edit_log_intent_time (intent, created_at),
    INDEX idx_edit_log_created (created_at)
) ENGINE=InnoDB;

-- ============================================================
-- 8. Reply Performance Tracking (MVP phase 3, schema reserved)
-- ============================================================

CREATE TABLE reply_performance (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    draft_id CHAR(36) NOT NULL,
    likes_before INT DEFAULT 0,
    likes_after INT DEFAULT 0,
    replies_before INT DEFAULT 0,
    replies_after INT DEFAULT 0,
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (draft_id) REFERENCES reply_drafts(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ============================================================
-- 9. Security Audit Log (Harness Module 8)
-- ============================================================

CREATE TABLE security_audit_log (
    id CHAR(36) PRIMARY KEY DEFAULT (UUID()),
    user_id CHAR(36),
    event_type VARCHAR(64) NOT NULL,
    event_detail JSON,
    client_ip VARCHAR(45),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_security_audit_type (event_type, created_at)
) ENGINE=InnoDB;
