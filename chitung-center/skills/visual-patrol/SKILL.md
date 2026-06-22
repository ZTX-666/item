# Visual Patrol

从 CCTV、RTMP 或本地图片抽帧，执行 YOLO/VLM 安全巡检，并把证据写入本地 SQLite。

## Rules

- 优先使用真实摄像头或用户选择的视频源抽帧，不得静默回退到本地兜底图片。
- 抽帧失败时必须返回明确错误、摄像头编号、失败原因和可重试建议。
- YOLO 标注图、原始抽帧图、检测 JSON、VLM 分析结果和用户检测要求都要保留路径或结构化字段。
- 视频巡检结果应展示标注图片、目标数量、风险等级、建议动作和 SQLite 存储位置。

## Tools

- `workbench_video_detection`
- `rtmp_snapshot`
- `vlm_detect`
- `ingest_vlm_hazards`

## Frontend

- 展示视频巡检结果卡片 `video_detection_report`。
- 如果存在 `snapshot_url` 或 `annotated_url`，优先展示图片证据。
- 如果工具返回失败，直接显示失败原因，不要显示静态占位图冒充检测结果。
