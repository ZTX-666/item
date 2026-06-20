# 赤瞳守护者视觉模块对接记录（2026-06-20）

## 对接目标

将 `scripts/nightly_patrol.py`（RTMP→YOLO→VLM→标注图）接入三层栈，使前端「视觉巡检」页可：

- 单路摄像头巡检（赤瞳守护者完整流水线）
- 11 路全量巡检
- 查看 `patrol-output` 历史报告与标注图
- 人工确认后入库

## 新增/修改

### 中台 `chitung-center`

| 文件 | 说明 |
|------|------|
| `visual_patrol_batch_service.py` | 调用 `nightly_patrol.run_patrol`，同步 app_config 摄像头，读写 patrol-output |
| `visual_patrol_service.py` | 支持 `camera_id` 解析 |
| `app.py` | 新增视觉 API（见下） |
| `models.py` | `VisualPatrolBatchRequest`、`use_guardian_pipeline` |

**API**

```http
POST /api/visual/patrol-draft        # use_guardian_pipeline=true 时走 nightly_patrol
POST /api/visual/patrol-batch        # 全量/单路批量巡检
GET  /api/visual/patrol-runs         # 历史列表
GET  /api/visual/patrol-runs/{id}    # 报告详情
GET  /api/visual/patrol-files/{id}/{filename}  # 标注图/截图
POST /api/visual/confirm-candidate   # 确认入库（原有）
```

### 前端 `chitung-frontend`

| 文件 | 说明 |
|------|------|
| `VisualPatrolPage.vue` | 全量巡检、历史侧栏、标注图展示、检测详情 |
| `chitungApi.ts` | `runVisualPatrolBatch`、`listVisualPatrolRuns`、`getVisualPatrolRun` |
| `domain.ts` | `PatrolRunReport` 等类型 |

## 调用链

```text
VisualPatrolPage
  → POST /api/visual/patrol-draft (use_guardian_pipeline=true)
  → visual_patrol_batch_service.run_guardian_patrol()
  → scripts/nightly_patrol.py (RTMP/YOLO/VLM/标注)
  → patrol-output/{timestamp}/
  → GET /api/visual/patrol-files/... 展示标注图
  → POST /api/visual/confirm-candidate 入库
```

## 环境依赖（见迁移交接文档）

- YOLO 权重：`VLM Detection/weights/`
- ffmpeg 二进制
- `agent-toolbox/.env` 中 `SECUREEYE_MODEL=glm-4v`
- RTMP token 过期时使用本地测试图回退

## 验证步骤

```powershell
# 1. 启动 toolbox + center
# 2. 前端 → 视觉巡检 → 点单路「巡检此摄像头」
# 3. 或点「全量巡检 11 路」
# 4. 右侧应出现 patrol-output 历史；标注图应通过中台 URL 显示
```
