using System.Diagnostics;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;

namespace WacliDesktop.Services;

public sealed class HiAgentBridgeService : IDisposable
{
    private static readonly Regex TunnelUrlRegex = new(
        @"https://[a-z0-9\-]+\.trycloudflare\.com",
        RegexOptions.IgnoreCase | RegexOptions.Compiled);

    private HiAgentBridgeConfig _config = HiAgentBridgeConfig.Load();
    private HiAgentLocalApiServer? _api;
    private Process? _tunnel;
    private readonly StringBuilder _tunnelLog = new();
    private readonly object _gate = new();

    public HiAgentBridgeConfig Config => _config;
    public bool ApiRunning => _api?.IsRunning == true;
    public bool TunnelRunning => _tunnel is { HasExited: false };
    public string? PublicBaseUrl => _config.PublicBaseUrl;
    public string LocalBaseUrl => $"http://127.0.0.1:{_config.Port}";

    public event Action<string>? LogLine;
    public event Action? StateChanged;

    public void ReloadConfig()
    {
        _config = HiAgentBridgeConfig.Load();
        if (string.IsNullOrEmpty(_config.ApiKey))
        {
            _config.ApiKey = HiAgentBridgeConfig.GenerateApiKey();
            _config.Save();
        }
        RaiseChanged();
    }

    public void SetApiKey(string key)
    {
        _config.ApiKey = key.Trim();
        _config.Save();
        RaiseChanged();
    }

    public void RegenerateApiKey()
    {
        _config.ApiKey = HiAgentBridgeConfig.GenerateApiKey();
        _config.Save();
        RaiseChanged();
    }

    public async Task StartAllAsync(IProgress<string> log, CancellationToken ct = default)
    {
        await StartApiAsync(log, ct);
        await Task.Delay(500, ct);
        await StartTunnelAsync(log, ct);
        _config.LastStartedAt = DateTimeOffset.Now.ToString("O");
        _config.Save();
    }

    public Task StartApiAsync(IProgress<string> log, CancellationToken ct = default)
    {
        ct.ThrowIfCancellationRequested();
        if (ApiRunning)
        {
            log.Report("✓ 本机 API 已在运行");
            return Task.CompletedTask;
        }

        log.Report($"→ 启动本机 API（127.0.0.1:{_config.Port}）…");
        _api = new HiAgentLocalApiServer(_config.Port, () => _config.ApiKey);
        try
        {
            _api.Start();
            log.Report($"✓ 本机 API：{_api.LocalBaseUrl}");
        }
        catch (Exception ex)
        {
            log.Report($"✗ 启动失败：{ex.Message}");
            throw;
        }
        RaiseChanged();
        return Task.CompletedTask;
    }

    public async Task StartTunnelAsync(IProgress<string> log, CancellationToken ct = default)
    {
        ct.ThrowIfCancellationRequested();
        if (!ApiRunning)
            await StartApiAsync(log, ct);

        if (TunnelRunning)
        {
            log.Report($"✓ 隧道已在运行：{_config.PublicBaseUrl}");
            return;
        }

        var cf = FindCloudflared();
        if (cf is null)
        {
            log.Report("→ 未找到 cloudflared，尝试 winget 安装…");
            await RunWingetCloudflaredAsync(log, ct);
            cf = FindCloudflared();
        }

        if (cf is null)
            throw new InvalidOperationException("未安装 cloudflared。请运行：winget install Cloudflare.cloudflared");

        log.Report("→ 启动 Cloudflare 隧道（内网穿透）…");
        lock (_gate)
        {
            _tunnelLog.Clear();
            var psi = new ProcessStartInfo
            {
                FileName = cf,
                Arguments = $"tunnel --url http://127.0.0.1:{_config.Port}",
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true,
                StandardOutputEncoding = Encoding.UTF8,
                StandardErrorEncoding = Encoding.UTF8,
            };
            _tunnel = Process.Start(psi) ?? throw new InvalidOperationException("无法启动 cloudflared");
            _tunnel.OutputDataReceived += (_, e) => OnTunnelLine(e.Data);
            _tunnel.ErrorDataReceived += (_, e) => OnTunnelLine(e.Data);
            _tunnel.BeginOutputReadLine();
            _tunnel.BeginErrorReadLine();
        }

        var url = await WaitForTunnelUrlAsync(TimeSpan.FromSeconds(45), ct);
        if (url is null)
            throw new InvalidOperationException("未获取到公网地址，请查看日志或检查网络");

        _config.PublicBaseUrl = url.TrimEnd('/');
        _config.Save();
        log.Report($"✓ 公网地址：{_config.PublicBaseUrl}");
        RaiseChanged();
    }

    public void StopAll()
    {
        StopTunnel();
        StopApi();
        RaiseChanged();
    }

    public void StopApi()
    {
        _api?.Dispose();
        _api = null;
    }

    public void StopTunnel()
    {
        lock (_gate)
        {
            if (_tunnel is null) return;
            try
            {
                if (!_tunnel.HasExited)
                    _tunnel.Kill(true);
            }
            catch { /* ignore */ }
            _tunnel.Dispose();
            _tunnel = null;
        }
    }

    public string BuildHiAgentConfigText()
    {
        var baseUrl = _config.PublicBaseUrl ?? "(请先点击「一键启动对接」获取公网地址)";
        var key = string.IsNullOrEmpty(_config.ApiKey) ? "(未设置)" : _config.ApiKey;
        var sb = new StringBuilder();
        sb.AppendLine("【赤瞳灵讯 · HiAgent 对接配置】");
        sb.AppendLine();
        sb.AppendLine("■ 公网基础地址（填到 HiAgent HTTP 工具）");
        sb.AppendLine(baseUrl);
        sb.AppendLine();
        sb.AppendLine("■ 推荐测试 URL");
        sb.AppendLine($"{baseUrl}/health");
        sb.AppendLine($"{baseUrl}/api/ping");
        sb.AppendLine($"{baseUrl}/api/messages/search?limit=5");
        sb.AppendLine();
        sb.AppendLine("■ 请求头（若已启用 API Key）");
        sb.AppendLine("accept: application/json");
        sb.AppendLine($"X-Api-Key: {key}");
        sb.AppendLine();
        sb.AppendLine("■ 本机信息");
        sb.AppendLine($"数据目录: {AppConfig.StoreDir}");
        sb.AppendLine($"数据库: {AppConfig.ResolveReadableDbPath()}");
        sb.AppendLine($"本机 API: {LocalBaseUrl}");
        sb.AppendLine();
        sb.AppendLine("■ 注意");
        sb.AppendLine("- 关闭本窗口不会自动停止服务；点「停止对接」结束");
        sb.AppendLine("- 重启隧道后公网地址会变，需同步更新 HiAgent");
        return sb.ToString();
    }

    private void OnTunnelLine(string? line)
    {
        if (string.IsNullOrWhiteSpace(line)) return;
        lock (_gate)
            _tunnelLog.AppendLine(line);
        LogLine?.Invoke(line);
        var m = TunnelUrlRegex.Match(line);
        if (m.Success)
        {
            _config.PublicBaseUrl = m.Value;
            _config.Save();
            RaiseChanged();
        }
    }

    private async Task<string?> WaitForTunnelUrlAsync(TimeSpan timeout, CancellationToken ct)
    {
        var deadline = DateTime.UtcNow + timeout;
        while (DateTime.UtcNow < deadline)
        {
            ct.ThrowIfCancellationRequested();
            if (!string.IsNullOrEmpty(_config.PublicBaseUrl))
                return _config.PublicBaseUrl;
            lock (_gate)
            {
                var m = TunnelUrlRegex.Match(_tunnelLog.ToString());
                if (m.Success)
                {
                    _config.PublicBaseUrl = m.Value;
                    _config.Save();
                    return _config.PublicBaseUrl;
                }
            }
            await Task.Delay(400, ct);
        }
        return null;
    }

    private static string? FindCloudflared()
    {
        var paths = new[]
        {
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86), "cloudflared", "cloudflared.exe"),
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "cloudflared", "cloudflared.exe"),
        };
        foreach (var p in paths)
        {
            if (File.Exists(p)) return p;
        }
        return ToolDiscovery.Find("cloudflared");
    }

    private static async Task RunWingetCloudflaredAsync(IProgress<string> log, CancellationToken ct)
    {
        log.Report("$ winget install Cloudflare.cloudflared");
        using var proc = Process.Start(new ProcessStartInfo
        {
            FileName = "winget",
            Arguments = "install --id Cloudflare.cloudflared -e --accept-package-agreements --accept-source-agreements",
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
        });
        if (proc is null) return;
        await proc.WaitForExitAsync(ct);
    }

    private void RaiseChanged() => StateChanged?.Invoke();

    public void Dispose() => StopAll();
}
