# Final Version Decisions

This file records which code should be used as the final version for future development.

## Use These Final Copies

| Capability | Use this folder | Reason |
| --- | --- | --- |
| Formal frontend | `FinalAgentSuite\chitung-frontend` | New Electron + Vue 3 + Vite + TypeScript desktop workbench |
| Frontend UI prototype | `FinalAgentSuite\frontend-ui-prototype` | Latest Feishu-light UI mockups and design docs |
| Chitung Center | `FinalAgentSuite\chitung-center` | Natural-language entry, intent router, Skill loader, LLM gateway, orchestration |
| Agent orchestration gateway | `FinalAgentSuite\agent-toolbox` | New unified HTTP + MCP gateway |
| Safety policy templates | `FinalAgentSuite\safety-policy-templates-20241025` | 159 safety form templates and policy index |
| WhatsApp archive backend | `FinalAgentSuite\whatsapp-archive\app-server` | Existing Node/Express API, copied as final integration version |
| WhatsApp archive UI | `FinalAgentSuite\whatsapp-archive\app-web` | Existing Vite UI, copied as final integration version |
| Chitong Lingxun / 赤瞳灵讯 | `FinalAgentSuite\chitong-lingxun` | Latest copied core source from `publish3.0`; includes WPF client, launcher, cloud sync API, and HiAgent test bridge |
| DocMate / 闪闪文档 | `FinalAgentSuite\docmate-shanshan` | Latest copied core source for version `4.1.37`; Electron + Vue + Tiptap document editor |
| VLM/YOLO detection | `FinalAgentSuite\vlm-detection` | ASCII-path variant copied from `VLMDetection`, easier for Python/PyTorch tooling |
| RTMP screenshot | `FinalAgentSuite\rtmp-tools` | Stable standalone screenshot script |
| Report generation | `FinalAgentSuite\report-generators` | Current Word report script used by AgentToolbox |

## Treat These As Source History

| Original folder | Status |
| --- | --- |
| `J:\China Oversea  Final\chitung-center` | Original Chitung Center source, copied into final suite |
| `J:\China Oversea  Final\2026-06-16-20-13-23` | Original UI prototype package, copied into final suite |
| `J:\China Oversea  Final\safety-policy-templates-20241025` | Original template library, copied into final suite |
| `J:\China Oversea  Final\AgentToolbox` | Original generated integration project, kept as source history |
| `J:\China Oversea  Final\ChinaOverseas Final` | Original WhatsApp archive source and handoff artifacts |
| `J:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\source` | Original Chitong Lingxun handoff source; latest runnable package under `publish3.0` |
| `E:\ChinaOverseas Final\publish4` | Original DocMate Shanshan source and release package; latest runnable package under `publish100` |
| `J:\China Oversea  Final\VLM Detection` | Earlier VLM detection copy with space in path |
| `J:\China Oversea  Final\VLMDetection` | Source used for final VLM copy |
| `J:\China Oversea  Final\VLM-Detection` | Larger handoff/bundle/history folder; use only when recovering old assets |
| `J:\China Oversea  Final\3311 AI` | Original RTMP/report/prototype scripts and documents |

## Assets Not Copied

The final code package intentionally does not duplicate:

- `.venv` directories.
- `node_modules`.
- generated screenshots.
- generated output folders.
- large `.zip` handoff files.
- VLM model weight files.
- DocMate `node_modules`, `dist`, `release`, and historical `publish*` folders.
- Chitong Lingxun binary runtime folders and portable executable outputs.

For VLM detection, keep using the original weights or place them under:

```text
FinalAgentSuite\vlm-detection\weights
```

Expected weight paths:

```text
weights\worker\yolo26x_worker.pt
weights\machinery\yolo26l_machinery.pt
```

## Canonical Agent Entry

Future programming should call:

```text
FinalAgentSuite\agent-toolbox
```

instead of directly calling scattered scripts. This keeps all external agent integrations stable.

## Canonical LLM Entry

Future programming should call the LLM only through:

```text
FinalAgentSuite\chitung-center
```

`LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL` belong in `chitung-center\.env`. Frontends, local desktop modules, and AgentToolbox should call Chitung Center rather than holding their own model API keys.
