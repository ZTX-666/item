# 赤瞳灵讯 publish20 · 耀耀工厂云端同步（SSH 续作指南）

> 版本：**publish20**  
> 入口：主界面 **「耀耀工厂」**（原 HiAgent 对接）  
> 本文件供你在 **云服务器 SSH + Cursor** 中继续部署接收端与耀耀工厂数据通道。

---

## 1. 本版做了什么

### 客户端（赤瞳 publish20）

| 功能 | 说明 |
|------|------|
| **耀耀工厂窗口** | 云端同步配置 + 立即同步 + 自动同步 |
| **三档可选** | 档位1 仅消息元数据；档位2 +缩略图；档位3 +原文件媒体 |
| **出站 HTTPS** | 本机主动 POST，无需暴露本机 3306 |
| **稳定机制** | 批量上传、失败重试、水位 `last_message_ts`、媒体已传记录 |
| **Token 存储** | `runtime/cloud-sync.json`（SyncToken 使用 Windows DPAPI） |
| **状态文件** | `runtime/cloud-sync-state.json` |
| **本机调试** | 第二 Tab：原 HiAgent 本机 API + cloudflared（可选，非生产） |

### 服务端（需你在云上部署）

路径：`source/cloud-sync-api/`

| 文件 | 说明 |
|------|------|
| `main.py` | FastAPI 接收 API |
| `sql/schema.sql` | MySQL 表结构 |
| `docker-compose.yml` | MySQL + API 一键起 |

---

## 2. 接口约定（赤瞳 → 云）

**鉴权（二选一）：**

```http
Authorization: Bearer <SyncToken>
```

或 `X-Api-Key: <SyncToken>`

### 2.1 健康检查

```http
GET /sync/v1/health
```

响应示例：`{"ok":true,"service":"chitong-cloud-sync","database":true}`

### 2.2 消息同步

```http
POST /sync/v1/messages
Content-Type: application/json

{
  "owner_id": "your.name",
  "tier": 0,
  "items": [
    {
      "msg_id": "...",
      "chat_jid": "...",
      "chat_name": "...",
      "sender_name": "...",
      "sender_jid": "...",
      "ts": 1717234567,
      "text": "...",
      "display_text": "...",
      "media_type": "image",
      "local_path": "...",
      "filename": "...",
      "revoked": 0,
      "deleted_for_me": 0
    }
  ]
}
```

### 2.3 媒体同步（multipart）

```http
POST /sync/v1/media
Content-Type: multipart/form-data

owner_id, msg_id, chat_jid, kind=(thumbnail|full), file=<binary>
```

---

## 3. 云服务器部署步骤（SSH 内执行）

### 3.1 上传代码

将 `publish20/source/cloud-sync-api/` 拷到服务器，例如 `/opt/chitong-sync/`。

```bash
cd /opt/chitong-sync
# 若用 git/scp 从本机上传整个 cloud-sync-api 目录
```

### 3.2 Docker 方式（推荐）

```bash
cd /opt/chitong-sync
# 编辑 docker-compose.yml 修改密码与 SYNC_API_TOKEN
nano docker-compose.yml

docker compose up -d
docker compose logs -f sync-api
```

默认 API 端口：**8090**  
健康检查：`curl http://127.0.0.1:8090/sync/v1/health`

### 3.3 手动方式

```bash
apt install -y python3-pip mysql-server   # 或 yum
mysql -u root -p < sql/schema.sql

pip install -r requirements.txt
export SYNC_API_TOKEN='与赤瞳一致的随机长串'
export MYSQL_HOST=127.0..1
export MYSQL_USER=sync_writer
export MYSQL_PASSWORD='...'
export MYSQL_DATABASE=wacli_sync

uvicorn main:app --host 0.0.0.0 --port 8090
```

### 3.4 HTTPS 与防火墙

- 用 **Nginx** 反向代理 `https://sync.your-domain.com` → `127.0.0.1:8090`
- 防火墙：开放 **443** 给赤瞳客户端；**3306** 仅对耀耀工厂平台出口 IP（见下）
- 赤瞳里填的 API 地址：`https://sync.your-domain.com`（不要带末尾斜杠）

### 3.5 与赤瞳配对

1. 云上设 `SYNC_API_TOKEN=某长随机串`
2. 赤瞳 → **耀耀工厂** → API 地址、Sync Token（与上一致）、OwnerId（如工号）
3. 选档位 → **测试连接** → **立即同步**
4. 查看日志是否 `消息同步完成`

---

## 4. 耀耀工厂「创建数据通道」

同步有数据后，在平台配置 **MySQL**（不是 SQLite）：

| 字段 | 填什么 |
|------|--------|
| host | 云服务器 **公网 IP/域名**（平台要求公网可达时） |
| 端口 | 3306 |
| 库名 | `wacli_sync` |
| 用户 | `hiagent_read`（建议只读，需 DBA 创建） |
| 密码 | IT 分配 |

**注意：** 赤瞳 Sync API 写库用户 `sync_writer` 与平台只读用户应分离。

创建只读用户示例：

```sql
CREATE USER 'hiagent_read'@'%' IDENTIFIED BY '强密码';
GRANT SELECT ON wacli_sync.* TO 'hiagent_read'@'%';
FLUSH PRIVILEGES;
```

平台 **连接测试** 通过后，用 `sync_messages` 表做数据集。

---

## 5. 三档说明（客户端下拉）

| 档位 | SyncTier | 上传内容 |
|------|----------|----------|
| 档位1 | 0 | 仅 `POST /messages`（含 media_type、local_path 等元数据，不传文件） |
| 档位2 | 1 | 消息 + `runtime/data/thumbnails/` 缩略图 |
| 档位3 | 2 | 消息 + 缩略图 + `local_path` 原文件（受大小限制，默认 50MB/文件） |

配置项：`runtime/cloud-sync.json` 中 `MaxMediaFileBytes`、`MaxThumbnailBytes`。

---

## 6. 故障排查

| 现象 | 处理 |
|------|------|
| 测试连接失败 | 检查 Token、URL、防火墙、Nginx |
| 消息 0 条 | 本机先 wacli sync；确认 `runtime/data/wacli.db` 有数据 |
| 媒体跳过 | 文件超大或未下载 `local_path`；档位3 需先完成附件下载 |
| 水位不前进 | 看 `cloud-sync-state.json`；失败看 `cloud-sync.json` 的 `LastError` |
| 平台连不上 MySQL | 3306 白名单、公网地址、只读账号 |

本机检测脚本（Windows）：

```powershell
cd source\hiagent-local-test
.\test-db-reachability.ps1
```

---

## 7. 文件路径速查

| 路径 | 说明 |
|------|------|
| `runtime/cloud-sync.json` | 云端同步配置 |
| `runtime/cloud-sync-state.json` | 同步水位与已传媒体 |
| `runtime/data/wacli.db` | 本地 SQLite |
| `runtime/data/thumbnails/` | 缩略图（档位2） |
| `source/cloud-sync-api/` | 服务端代码 |
| `source/WacliDesktop/Services/CloudSyncService.cs` | 客户端同步逻辑 |

---

## 8. 后续可做（可选）

- [ ] 云上部署 **Streamable HTTP MCP**，工具 `search_messages` 读 `sync_messages`
- [ ] Nginx 限流、审计日志
- [ ] 按 `chat_jid` 白名单过滤同步
- [ ] systemd 守护 `uvicorn`

---

## 9. 合规提醒

- 同步前确认 WhatsApp 数据是否允许上云。
- 生产环境勿用「本机调试」Tab 的 cloudflared 暴露办公机。
- 试验结束：关闭自动同步、轮换 Token、按需清理 `media_storage/`。

---

*在服务器上打开本文件：`publish20/memory.md` 或 `/opt/chitong-sync/../memory.md`*
