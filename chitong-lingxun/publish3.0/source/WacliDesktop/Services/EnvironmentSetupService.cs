using System.Diagnostics;
using System.IO;
using System.Text;

namespace WacliDesktop.Services;

public sealed class EnvironmentSetupService
{
    private readonly RuntimeEnvironmentManifest _manifest = new();

    public async Task RunAsync(IProgress<string> log, CancellationToken ct = default)
    {
        EnsureDirectories(log);

        log.Report("");
        log.Report("━━━ 阶段 1/4：扫描本机已安装工具 ━━━");
        var scan = ToolDiscovery.ScanAll();
        LogScanResults(log, scan);

        log.Report("");
        log.Report("━━━ 阶段 2/4：补全编译依赖（Git · Go · gcc）━━━");
        await EnsureToolAsync("git", required: true, log, ct);
        await EnsureToolAsync("go", required: true, log, ct);
        await EnsureToolAsync("gcc", required: true, log, ct);

        log.Report("");
        log.Report("━━━ 阶段 3/4：wacli（复用本机 → 本地编译）━━━");
        await EnsureWacliAsync(log, ct);

        log.Report("");
        log.Report("━━━ 阶段 4/4：可选组件（Python · wacli-web）━━━");
        await EnsurePythonOptionalAsync(log, ct);
        await EnsureWacliWebDepsAsync(log, ct);

        RuntimeEnvironment.Save(_manifest);
        RuntimeEnvironment.Reload();

        log.Report("");
        log.Report("━━━ 配置完成 · 路径摘要 ━━━");
        log.Report($"  数据目录：{AppConfig.StoreDir}");
        log.Report($"  配置文件：{AppConfig.EnvironmentManifestPath}");
        foreach (var (name, record) in _manifest.Tools.OrderBy(x => x.Key))
            log.Report($"  {name,-6} [{record.Source}] {record.Path}");
        log.Report("");
        log.Report("全部步骤完成。请重启本软件后使用。");
    }

    private static void EnsureDirectories(IProgress<string> log)
    {
        Directory.CreateDirectory(AppConfig.LocalBinDir);
        Directory.CreateDirectory(AppConfig.StoreDir);
        Directory.CreateDirectory(AppConfig.ThumbnailDir);
        Directory.CreateDirectory(Path.GetDirectoryName(AppConfig.WacliSrcDir)!);
        log.Report($"✓ 运行目录：{AppConfig.RuntimeDir}");
    }

    private static void LogScanResults(IProgress<string> log, IReadOnlyDictionary<string, string?> scan)
    {
        foreach (var (tool, path) in scan.OrderBy(x => x.Key))
        {
            if (path is not null && ToolDiscovery.IsValidToolPath(tool, path))
                log.Report($"  ✓ {tool} 已发现 → {path}");
            else
                log.Report($"  · {tool} 未发现");
        }
    }

    private async Task EnsureToolAsync(string tool, bool required, IProgress<string> log, CancellationToken ct)
    {
        var path = ToolDiscovery.Find(tool);
        if (path is not null && ToolDiscovery.IsValidToolPath(tool, path))
        {
            Register(tool, path, "system", log);
            return;
        }

        var wingetId = ToolDiscovery.GetWingetPackageId(tool);
        if (wingetId is not null)
        {
            if (ToolDiscovery.IsWingetInstalled(wingetId))
                log.Report($"→ {tool}：winget 已注册，正在重新定位…");
            else
                log.Report($"→ {tool} 未找到，winget 安装 {wingetId} …");

            await RunWingetAsync(wingetId, log, ct);
        }

        path = ToolDiscovery.Find(tool);
        if (path is not null && ToolDiscovery.IsValidToolPath(tool, path))
        {
            Register(tool, path, wingetId is not null ? "winget" : "system", log);
            return;
        }

        if (!required)
        {
            log.Report($"⚠ {tool} 未就绪（可选，已跳过）");
            return;
        }

        throw new InvalidOperationException(
            $"{tool} 未找到。请手动安装后重试，或重启电脑使 PATH 生效。");
    }

    private async Task EnsureWacliAsync(IProgress<string> log, CancellationToken ct)
    {
        var local = AppConfig.LocalWacliExe;

        if (File.Exists(local) && ToolDiscovery.VerifyWacli(local))
        {
            Register("wacli", local, "local-built", log);
            return;
        }

        var existing = ToolDiscovery.FindWacli();
        if (existing is not null
            && !existing.Equals(local, StringComparison.OrdinalIgnoreCase)
            && ToolDiscovery.VerifyWacli(existing))
        {
            log.Report($"→ wacli 本机已安装，复制到运行目录…");
            log.Report($"  来源：{existing}");
            Directory.CreateDirectory(AppConfig.LocalBinDir);
            File.Copy(existing, local, overwrite: true);
            Register("wacli", local, "local-copied", log);
            return;
        }

        var git = RequireTool("git");
        var go = RequireTool("go");

        var srcDir = AppConfig.WacliSrcDir;
        if (!Directory.Exists(Path.Combine(srcDir, ".git")))
        {
            log.Report("→ git clone wacli …");
            log.Report($"  {AppConfig.WacliGitUrl}");
            Directory.CreateDirectory(Path.GetDirectoryName(srcDir)!);
            var cloned = await RunProcessAsync(
                git,
                $"clone --depth 1 \"{AppConfig.WacliGitUrl}\" \"{srcDir}\"",
                log,
                ct);
            if (!cloned)
                throw new InvalidOperationException("git clone wacli 失败");
        }
        else
        {
            log.Report("→ git pull wacli 源码…");
            await RunProcessAsync(git, $"-C \"{srcDir}\" pull --ff-only", log, ct);
        }

        log.Report("→ 编译 wacli（go build -tags sqlite_fts5）…");
        var built = await RunGoBuildAsync(local, srcDir, go, log, ct);
        if (!built || !File.Exists(local))
            throw new InvalidOperationException("wacli 编译失败，请查看上方日志");

        Register("wacli", local, "local-built", log);
    }

    private async Task EnsurePythonOptionalAsync(IProgress<string> log, CancellationToken ct)
    {
        var python = ToolDiscovery.FindPython();
        if (python is not null && ToolDiscovery.VerifyPython(python))
        {
            Register("python", python, "system", log);
            return;
        }

        log.Report("→ Python 未找到，winget 安装（可选）…");
        await RunWingetAsync("Python.Python.3.12", log, ct);
        python = ToolDiscovery.FindPython();
        if (python is not null && ToolDiscovery.VerifyPython(python))
        {
            Register("python", python, "winget", log);
            return;
        }

        log.Report("⚠ Python 未就绪，wacli-web 依赖可稍后手动安装");
    }

    private async Task EnsureWacliWebDepsAsync(IProgress<string> log, CancellationToken ct)
    {
        var webDir = AppConfig.WacliWebDir;
        var reqFile = Path.Combine(webDir, "requirements.txt");
        if (!File.Exists(reqFile))
        {
            log.Report($"⚠ 未找到 {reqFile}，跳过 pip（HiAgent 可选）");
            return;
        }

        var python = _manifest.Tools.TryGetValue("python", out var p) ? p.Path : ToolDiscovery.FindPython();
        if (python is null)
        {
            log.Report("⚠ 无 Python，跳过 wacli-web pip");
            return;
        }

        log.Report("→ pip install wacli-web 依赖…");
        var ok = await RunProcessAsync(python, $"-m pip install -r \"{reqFile}\"", log, ct);
        log.Report(ok ? "✓ wacli-web Python 依赖安装完成" : "⚠ pip 安装失败，请手动进入 wacli-web 目录执行 pip install");
    }

    private void Register(string tool, string path, string source, IProgress<string> log)
    {
        var version = ToolDiscovery.GetVersion(tool, path);
        _manifest.Tools[tool] = new ToolRecord
        {
            Path = path,
            Source = source,
            Version = version,
        };
        var ver = string.IsNullOrWhiteSpace(version) ? "" : $" ({version})";
        log.Report($"✓ {tool} [{source}] → {path}{ver}");
    }

    private string RequireTool(string tool)
    {
        if (_manifest.Tools.TryGetValue(tool, out var rec) && File.Exists(rec.Path))
            return rec.Path;
        var found = ToolDiscovery.Find(tool);
        if (found is null)
            throw new InvalidOperationException($"{tool} 未就绪");
        return found;
    }

    private static async Task<bool> RunGoBuildAsync(
        string outputExe,
        string srcDir,
        string goExe,
        IProgress<string> log,
        CancellationToken ct)
    {
        log.Report($"$ \"{goExe}\" build -tags sqlite_fts5 -o \"{outputExe}\" ./cmd/wacli");
        var psi = new ProcessStartInfo
        {
            FileName = goExe,
            Arguments = $"build -tags sqlite_fts5 -o \"{outputExe}\" ./cmd/wacli",
            WorkingDirectory = srcDir,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8,
        };
        ToolDiscovery.ApplyDiscoveredPath(psi);
        psi.Environment["CGO_ENABLED"] = "1";
        psi.Environment["CGO_CFLAGS"] = "-Wno-error=missing-braces";

        using var proc = Process.Start(psi)
            ?? throw new InvalidOperationException("无法启动 go build");

        var stdout = proc.StandardOutput.ReadToEndAsync(ct);
        var stderr = proc.StandardError.ReadToEndAsync(ct);
        await proc.WaitForExitAsync(ct);

        foreach (var line in (await stdout).Split('\n', StringSplitOptions.RemoveEmptyEntries))
            log.Report("  " + line.Trim());
        foreach (var line in (await stderr).Split('\n', StringSplitOptions.RemoveEmptyEntries))
            log.Report("  " + line.Trim());

        if (proc.ExitCode != 0)
            log.Report($"  [exit {proc.ExitCode}]");
        return proc.ExitCode == 0;
    }

    private static Task RunWingetAsync(string packageId, IProgress<string> log, CancellationToken ct) =>
        RunProcessAsync(
            "winget",
            $"install --id {packageId} -e --accept-package-agreements --accept-source-agreements",
            log,
            ct,
            treatAlreadyInstalledAsOk: true);

    private static bool IsWingetAlreadyInstalled(string output, int exitCode) =>
        exitCode is -1978335189 or -2145844847
        || output.Contains("已安装", StringComparison.OrdinalIgnoreCase)
        || output.Contains("已安裝", StringComparison.OrdinalIgnoreCase)
        || output.Contains("already installed", StringComparison.OrdinalIgnoreCase)
        || output.Contains("No available upgrade", StringComparison.OrdinalIgnoreCase)
        || output.Contains("沒有較新的套件版本", StringComparison.OrdinalIgnoreCase)
        || output.Contains("没有较新的包版本", StringComparison.OrdinalIgnoreCase)
        || output.Contains("Found an existing package", StringComparison.OrdinalIgnoreCase)
        || output.Contains("發現已安裝", StringComparison.OrdinalIgnoreCase);

    private static async Task<bool> RunProcessAsync(
        string file,
        string args,
        IProgress<string> log,
        CancellationToken ct,
        bool treatAlreadyInstalledAsOk = false)
    {
        log.Report($"$ {file} {args}");
        var psi = new ProcessStartInfo
        {
            FileName = file,
            Arguments = args,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8,
        };
        psi.Environment["PATH"] = ToolDiscovery.GetExpandedPath();

        using var proc = Process.Start(psi);
        if (proc is null) return false;

        var stdout = proc.StandardOutput.ReadToEndAsync(ct);
        var stderr = proc.StandardError.ReadToEndAsync(ct);
        await proc.WaitForExitAsync(ct);

        var outText = await stdout;
        var errText = await stderr;
        foreach (var line in outText.Split('\n', StringSplitOptions.RemoveEmptyEntries))
            log.Report("  " + line.Trim());
        foreach (var line in errText.Split('\n', StringSplitOptions.RemoveEmptyEntries))
            log.Report("  " + line.Trim());

        var combined = outText + errText;
        if (proc.ExitCode != 0)
        {
            if (treatAlreadyInstalledAsOk && IsWingetAlreadyInstalled(combined, proc.ExitCode))
                log.Report("  （winget：已安装，跳过）");
            else
                log.Report($"  [exit {proc.ExitCode}]");
        }

        if (proc.ExitCode == 0)
            return true;
        if (treatAlreadyInstalledAsOk && IsWingetAlreadyInstalled(combined, proc.ExitCode))
            return true;
        return false;
    }
}
