# PowerShell Runner

在 Windows 沙箱中运行 PowerShell，用于系统诊断、服务与注册表只读查询。

## Rules

- 默认只允许 workspace 内 cwd；系统级查询（Get-Service、Get-Process）可用于运维诊断。
- 修改系统配置、停止服务、写注册表前必须经用户确认。
- 输出应简洁，避免 dump 大量对象。

## Preferred Tools

- `run_powershell_command`

## Boundaries

- 禁止 `Remove-Item -Recurse -Force` 作用于 workspace 之外
- 禁止 Invoke-Expression 执行远程代码
