# 赤瞳灵讯 publish22 · 数据库多账号与默认路径

> 版本：**publish22**  
> 在 publish21 基础上增加：按手机号单库复用、跨进程锁、用户目录默认库根路径。

---

## 1. 数据库默认存储位置

| 项目 | 路径 |
|------|------|
| **默认根目录** | `%UserProfile%\ChitongLingxun`（例如 `C:\Users\你的用户名\ChitongLingxun`） |
| **未绑定手机号时** | `%UserProfile%\ChitongLingxun\_unbound\wacli.db` |
| **已绑定手机号** | `%UserProfile%\ChitongLingxun\<手机号>Data Base\<手机号>Data Base.db` |
| **程序与 wacli** | 仍在发布包目录 `runtime\bin`（不随数据库根目录迁移） |
| **配置文件** | `runtime/database-profile.json`（记录默认根目录、当前手机号、各账号目录） |

可在 **数据浏览** 页点击 **「默认数据库」** 修改默认根目录（仅影响此后新登录账号；已登记手机号仍用原目录）。

---

## 2. 多账号规则

- **同一 WhatsApp 手机号**：始终复用 `database-profile.json` 中登记的目录与库文件。
- **切换为另一手机号**：自动切换到对应库；若不存在则新建 `手机号Data Base` 目录。
- **临时库迁移**：登录前 wacli 写入 `_unbound\wacli.db` 的，在绑定手机号后会复制到该账号正式库（仅当正式库尚不存在时）。
- **旧版路径兼容**：若存在 `runtime\<手机号>Data Base\` 或 `runtime\data\wacli.db`，首次切号时会尝试迁移到新根目录。

---

## 3. 并发

- 使用 Windows 全局 Mutex（按数据目录哈希）防止多开赤瞳同时写同一库。
- sync、云端同步、媒体补下、导入/导出数据库前会尝试获取锁。

---

## 4. 其他（继承 publish21）

- 数据浏览：导出 / 加载 / 刷新 / 默认数据库
- 主页登录状态每 5 分钟刷新
- 耀耀工厂云端同步（见 publish20-memory.md）

---

*SSH / 云端部署仍参考 publish20-memory.md 与 source/cloud-sync-api/*
