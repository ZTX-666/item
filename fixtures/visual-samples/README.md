# 视觉巡检测试样例图

RTMP 不可用时，`scripts/nightly_patrol.py` 会使用本地 JPG 回退。

## 本地来源（不上传 GitHub）

从项目负责人机器复制：

```text
J:\China Oversea  Final\3311 AI\
```

建议至少保留 15 张 `.jpg`，文件名含 `snapshot_` 或 `20260518-095211.jpg`（RGBA 兼容测试图）。

## 用法

无需放入本目录；脚本会自动扫描上级 `FinalAgentSuite` 外的 `3311 AI` 路径（见 `nightly_patrol.py` 配置）。

若同事机器路径不同，在 `agent-toolbox/.env` 或脚本配置区修改测试图目录。
