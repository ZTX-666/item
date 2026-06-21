@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在启动文稿修改助手 v4.0.0 ...
if exist "release\win-unpacked\文稿修改助手.exe" (
  start "" "release\win-unpacked\文稿修改助手.exe"
) else (
  echo 未找到打包版本，正在重新构建...
  call npm run pack
  if exist "release\win-unpacked\文稿修改助手.exe" (
    start "" "release\win-unpacked\文稿修改助手.exe"
  ) else (
    echo 构建失败，尝试开发模式...
    call npm run electron:dev
  )
)
