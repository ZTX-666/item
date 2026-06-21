CREATE DATABASE IF NOT EXISTS wacli_sync DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE wacli_sync;

CREATE TABLE IF NOT EXISTS sync_messages (
  owner_id VARCHAR(128) NOT NULL,
  msg_id VARCHAR(128) NOT NULL,
  chat_jid VARCHAR(256) NOT NULL,
  chat_name VARCHAR(512) DEFAULT '',
  sender_name VARCHAR(512) DEFAULT '',
  sender_jid VARCHAR(256) DEFAULT '',
  ts BIGINT NOT NULL,
  text MEDIUMTEXT,
  display_text MEDIUMTEXT,
  media_type VARCHAR(64) DEFAULT '',
  local_path VARCHAR(1024) DEFAULT '',
  filename VARCHAR(512) DEFAULT '',
  revoked TINYINT DEFAULT 0,
  deleted_for_me TINYINT DEFAULT 0,
  synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (owner_id, msg_id),
  KEY idx_owner_ts (owner_id, ts),
  KEY idx_owner_chat (owner_id, chat_jid)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS sync_media (
  owner_id VARCHAR(128) NOT NULL,
  msg_id VARCHAR(128) NOT NULL,
  chat_jid VARCHAR(256) DEFAULT '',
  kind VARCHAR(32) NOT NULL,
  object_key VARCHAR(512) NOT NULL,
  size_bytes BIGINT DEFAULT 0,
  mime_type VARCHAR(128) DEFAULT '',
  uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (owner_id, msg_id, kind),
  KEY idx_owner_uploaded (owner_id, uploaded_at)
) ENGINE=InnoDB;
