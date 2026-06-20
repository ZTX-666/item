# Core Code Migration 2026-06-17

This file records the latest core-code migration into `FinalAgentSuite`.

## Target Folder

```text
J:\China Oversea  Final\FinalAgentSuite
```

## Migrated Modules

| Module | Source | Target | Baseline |
| --- | --- | --- | --- |
| DocMate / 闪闪文档 | `E:\ChinaOverseas Final\publish4` | `docmate-shanshan` | `v4.1.37`, `publish100` handoff |
| Chitong Lingxun / 赤瞳灵讯 | `J:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\source\publish3.0\source` | `chitong-lingxun` | `publish3.0` |

## DocMate Shanshan

Copied:

- `src`
- `electron`
- `scripts`
- `public`
- `openspec`
- `.cursor`
- `package.json`
- `package-lock.json`
- TypeScript/Vite configs
- product and handoff documents

Not copied:

- `node_modules`
- `dist`
- `release`
- historical `publish*` folders

Original runnable entry:

```text
E:\ChinaOverseas Final\publish4\publish100\DocMate.vbs
```

Original portable exe:

```text
E:\ChinaOverseas Final\publish4\release\DocMate闪闪文档 4.1.37.exe
```

## Chitong Lingxun

Copied:

- `WacliDesktop`
- `WacliDesktopLauncher`
- `cloud-sync-api`
- `hiagent-local-test`
- latest memory documents
- latest build scripts
- runtime config samples

Not copied:

- `publish7.zip`
- binary `runtime/bin`
- portable runtime DLL payloads
- generated executable outputs

Original runnable package:

```text
J:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\source\publish3.0
```

Important runnable files in original package:

```text
publish3.0\start.bat
publish3.0\wacli-desktop.exe
publish3.0\portable\WacliDesktop.exe
```

## Integration Note

Future integration should treat `FinalAgentSuite` as the curated code workspace. The original folders remain the source history and runnable-release archive.
