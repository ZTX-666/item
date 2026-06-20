using System.Diagnostics;
using System.IO;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace WacliDesktop.Services;

public sealed class WacliService
{
    private static readonly Regex PairCodePlain = new(
        @"^[A-Z0-9]{4}-[A-Z0-9]{4}$",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant | RegexOptions.Compiled);

    private Process? _authProcess;
    private Process? _syncProcess;
    private DatabaseStoreMutex? _storeMutex;
    private bool _phoneAuthMode;
    private bool _authReaderVoluntaryStop;
    private readonly object _gate = new();

    public event Action<string>? LogLine;
    public event Action<string>? QrPayloadReceived;
    public event Action<string>? PairingCodeReceived;
    public event Action<string>? AuthStateChanged;

    public string? LastPairingCode { get; private set; }
    public string? LastAuthError { get; private set; }

    public bool AuthRunning
    {
        get
        {
            lock (_gate)
                return _authProcess is { HasExited: false };
        }
    }

    public WacliResult Run(IEnumerable<string> args, int timeoutMs = 120_000)
    {
        lock (_gate)
        {
            if (_authProcess is { HasExited: false })
                throw new InvalidOperationException("Cannot run wacli while auth is in progress");
        }

        var list = args.ToList();
        var psi = CreateWacliStartInfo();
        psi.RedirectStandardOutput = true;
        psi.RedirectStandardError = true;
        psi.StandardOutputEncoding = Encoding.UTF8;
        psi.StandardErrorEncoding = Encoding.UTF8;
        foreach (var a in list)
            psi.ArgumentList.Add(a);

        using var proc = Process.Start(psi)
            ?? throw new InvalidOperationException("Failed to start wacli");
        var stdout = proc.StandardOutput.ReadToEnd();
        var stderr = proc.StandardError.ReadToEnd();
        if (!proc.WaitForExit(timeoutMs))
        {
            try { proc.Kill(true); } catch { /* ignore */ }
            return new WacliResult(false, -1, stdout, stderr + "\nTimeout");
        }
        return new WacliResult(proc.ExitCode == 0, proc.ExitCode, stdout, stderr);
    }

    public void StartQrAuth()
    {
        StartAuth(phoneMode: false, extraArgs: []);
    }

    public void StartPhoneAuth(string phone)
    {
        if (string.IsNullOrWhiteSpace(phone))
            throw new ArgumentException("Phone number is required");
        var normalized = phone.Trim();
        if (!normalized.StartsWith('+'))
            normalized = "+" + normalized.TrimStart('+');
        StartAuth(phoneMode: true, extraArgs: ["--phone", normalized]);
    }

    private void StartAuth(bool phoneMode, string[] extraArgs)
    {
        lock (_gate)
        {
            StopAuthInternal();
            StopSyncInternal();
            KillWacliProcesses();

            _phoneAuthMode = phoneMode;
            _authReaderVoluntaryStop = false;
            LastPairingCode = null;
            LastAuthError = null;

            var psi = CreateWacliStartInfo();
            psi.RedirectStandardOutput = true;
            psi.RedirectStandardError = true;
            psi.StandardOutputEncoding = Encoding.UTF8;
            psi.StandardErrorEncoding = Encoding.UTF8;

            // --events 为全局参数，须在 auth 前；配对码 NDJSON 输出在 stderr
            psi.ArgumentList.Add("--events");
            psi.ArgumentList.Add("auth");
            psi.ArgumentList.Add("--qr-format");
            psi.ArgumentList.Add("text");
            psi.ArgumentList.Add("--follow");
            foreach (var a in extraArgs)
                psi.ArgumentList.Add(a);

            _authProcess = Process.Start(psi)
                ?? throw new InvalidOperationException("Failed to start wacli auth");
            AuthStateChanged?.Invoke("starting");
            _ = Task.Run(() => ReadAuthOutput(_authProcess));
        }
    }

    private async Task ReadAuthOutput(Process proc)
    {
        var exitCode = -1;
        try
        {
            await Task.WhenAll(
                PumpLinesAsync(proc.StandardOutput),
                PumpLinesAsync(proc.StandardError));
            await proc.WaitForExitAsync();
            exitCode = proc.ExitCode;

            lock (_gate)
            {
                if (exitCode != 0 && string.IsNullOrEmpty(LastPairingCode) && string.IsNullOrEmpty(LastAuthError))
                    LastAuthError = $"auth exited with code {exitCode}";
            }

            AuthStateChanged?.Invoke(
                exitCode == 0 || !string.IsNullOrEmpty(LastPairingCode) ? "ended" : "failed");
        }
        catch (Exception ex) when (IsBenignAuthReaderError(ex) || _authReaderVoluntaryStop)
        {
            /* auth process was stopped externally (StopAuth / StartSync) */
        }
        catch (Exception ex)
        {
            LastAuthError = ex.Message;
            EmitLog($"Auth reader error: {ex.Message}");
            AuthStateChanged?.Invoke("failed");
        }
        finally
        {
            lock (_gate)
            {
                if (_authProcess == proc)
                {
                    _authProcess = null;
                    _phoneAuthMode = false;
                }
            }

            try { proc.Dispose(); } catch { /* ignore */ }
            _authReaderVoluntaryStop = false;
        }
    }

    private static bool IsBenignAuthReaderError(Exception ex)
    {
        for (var cur = ex; cur is not null; cur = cur.InnerException)
        {
            if (cur is InvalidOperationException or ObjectDisposedException)
                return true;
            if (cur.Message.Contains("No process is associated", StringComparison.OrdinalIgnoreCase))
                return true;
        }

        return ex is AggregateException agg && agg.Flatten().InnerExceptions.Any(IsBenignAuthReaderError);
    }

    private async Task PumpLinesAsync(StreamReader reader)
    {
        while (true)
        {
            string? line;
            try
            {
                line = await reader.ReadLineAsync();
            }
            catch (Exception ex) when (IsBenignAuthReaderError(ex))
            {
                break;
            }

            if (line is null)
                break;
            HandleAuthLine(line);
        }
    }

    private void HandleAuthLine(string line)
    {
        EmitLog(line);
        var trimmed = line.Trim();
        if (trimmed.Length == 0)
            return;

        if (trimmed.StartsWith("2@", StringComparison.Ordinal))
        {
            QrPayloadReceived?.Invoke(trimmed);
            AuthStateChanged?.Invoke("waiting_scan");
            return;
        }

        if (trimmed.StartsWith('{'))
        {
            TryParseAuthEvent(trimmed);
            return;
        }

        if (trimmed.Contains("Authenticated as", StringComparison.OrdinalIgnoreCase))
            AuthStateChanged?.Invoke("authenticated");
        if (trimmed.Contains("Connected.", StringComparison.OrdinalIgnoreCase))
            AuthStateChanged?.Invoke("syncing");

        TryExtractPairingCodeFromPlainLine(trimmed);
    }

    private void TryParseAuthEvent(string json)
    {
        try
        {
            using var doc = JsonDocument.Parse(json);
            var root = doc.RootElement;
            var eventName = GetEventName(root);
            var data = root.TryGetProperty("data", out var dataEl) && dataEl.ValueKind == JsonValueKind.Object
                ? dataEl
                : root;

            if (eventName.Contains("pair", StringComparison.OrdinalIgnoreCase))
            {
                if (root.TryGetProperty("code", out var rootCode) && rootCode.ValueKind == JsonValueKind.String)
                    TryEmitPairingCode(rootCode.GetString());
            }

            if (data.ValueKind == JsonValueKind.Object)
            {
                if (data.TryGetProperty("code", out var pairCode) && pairCode.ValueKind == JsonValueKind.String)
                    TryEmitPairingCode(pairCode.GetString());

                foreach (var key in new[] { "pairing_code", "phone_code" })
                {
                    if (data.TryGetProperty(key, out var codeEl) && codeEl.ValueKind == JsonValueKind.String)
                        TryEmitPairingCode(codeEl.GetString());
                }

                if (data.TryGetProperty("qr", out var qr) && qr.ValueKind == JsonValueKind.String)
                {
                    var payload = qr.GetString();
                    if (!string.IsNullOrEmpty(payload) && payload.StartsWith("2@", StringComparison.Ordinal))
                    {
                        QrPayloadReceived?.Invoke(payload);
                        AuthStateChanged?.Invoke("waiting_scan");
                    }
                }

                if (data.TryGetProperty("message", out var msg) && msg.ValueKind == JsonValueKind.String)
                {
                    var text = msg.GetString();
                    if (!string.IsNullOrWhiteSpace(text) &&
                        eventName.Contains("error", StringComparison.OrdinalIgnoreCase))
                    {
                        LastAuthError = text;
                        AuthStateChanged?.Invoke("failed");
                    }
                }
            }

            if (eventName.Contains("authenticated", StringComparison.OrdinalIgnoreCase))
                AuthStateChanged?.Invoke("authenticated");
        }
        catch
        {
            /* ignore malformed json */
        }
    }

    private static string GetEventName(JsonElement root)
    {
        if (root.TryGetProperty("event", out var ev))
            return ev.GetString() ?? "";
        if (root.TryGetProperty("type", out var ty))
            return ty.GetString() ?? "";
        return "";
    }

    private void TryEmitPairingCode(string? code)
    {
        if (string.IsNullOrWhiteSpace(code))
            return;
        code = code.Trim();
        if (code.StartsWith("2@", StringComparison.Ordinal))
            return;
        if (PairCodePlain.IsMatch(code) || (_phoneAuthMode && code.Contains('-', StringComparison.Ordinal)))
            EmitPairingCode(code);
    }

    private void TryExtractPairingCodeFromPlainLine(string line)
    {
        if (!_phoneAuthMode)
            return;

        if (PairCodePlain.IsMatch(line))
        {
            EmitPairingCode(line.ToUpperInvariant());
            return;
        }

        var compact = line.Replace("-", "", StringComparison.Ordinal).Replace(" ", "", StringComparison.Ordinal);
        if (compact.Length is 6 or 8 && compact.All(char.IsDigit))
            EmitPairingCode(compact);
    }

    private void EmitPairingCode(string code)
    {
        code = code.Trim().ToUpperInvariant();
        if (code.StartsWith("2@", StringComparison.Ordinal))
            return;

        LastPairingCode = code;
        PairingCodeReceived?.Invoke(code);
        AuthStateChanged?.Invoke("waiting_phone_confirm");
    }

    public void StopAuth()
    {
        lock (_gate) StopAuthInternal();
    }

    private void StopAuthInternal()
    {
        if (_authProcess is null) return;
        _authReaderVoluntaryStop = true;
        var proc = _authProcess;
        _authProcess = null;
        try
        {
            if (!proc.HasExited)
                proc.Kill(true);
        }
        catch { /* ignore */ }
    }

    public bool SyncRunning
    {
        get
        {
            lock (_gate)
                return _syncProcess is { HasExited: false };
        }
    }

    public void StartSync(bool interruptAuth = false)
    {
        lock (_gate)
        {
            if (_syncProcess is { HasExited: false }) return;
            if (_authProcess is { HasExited: false } && !interruptAuth)
                return;
            StopAuthInternal();
            KillWacliProcesses();
            ReleaseStoreMutex();

            _storeMutex = DatabaseStoreMutex.TryAcquire(AppConfig.StoreDir, 5_000);
            if (_storeMutex is null)
            {
                EmitLog("无法启动 sync：数据库目录正被其他赤瞳实例占用。");
                return;
            }

            var psi = CreateWacliStartInfo();
            psi.RedirectStandardOutput = true;
            psi.RedirectStandardError = true;
            psi.ArgumentList.Add("sync");
            psi.ArgumentList.Add("--follow");
            psi.ArgumentList.Add("--download-media");

            _syncProcess = Process.Start(psi);
            EmitLog("Sync started with --download-media.");
        }
    }

    public void StopSync()
    {
        lock (_gate) StopSyncInternal();
    }

    private void StopSyncInternal()
    {
        if (_syncProcess is null) return;
        try
        {
            if (!_syncProcess.HasExited)
                _syncProcess.Kill(true);
        }
        catch { /* ignore */ }
        finally
        {
            _syncProcess.Dispose();
            _syncProcess = null;
            ReleaseStoreMutex();
            EmitLog("Sync stopped.");
        }
    }

    private void ReleaseStoreMutex()
    {
        _storeMutex?.Dispose();
        _storeMutex = null;
    }

    public WacliResult Logout()
    {
        lock (_gate)
        {
            StopAuthInternal();
            StopSyncInternal();
            KillWacliProcesses();
        }
        return Run(["auth", "logout"]);
    }

    public string GetStatusText()
    {
        lock (_gate)
        {
            if (_authProcess is { HasExited: false })
            {
                var pairHint = LastPairingCode ?? (_phoneAuthMode ? "等待 wacli 返回配对码…" : "—");
                var err = string.IsNullOrEmpty(LastAuthError) ? "" : $"\nerror: {LastAuthError}";
                return $"auth: running (phone={_phoneAuthMode})\npairing code: {pairHint}{err}\nstore: {AppConfig.StoreDir}";
            }
        }

        var auth = Run(["auth", "status"]);
        var doctor = Run(["doctor"]);
        var sync = SyncRunning;
        return string.Join(
            Environment.NewLine + Environment.NewLine,
            auth.Stdout.Trim(),
            doctor.Stdout.Trim(),
            $"sync: {(sync ? "running" : "stopped")}",
            $"store: {AppConfig.StoreDir}");
    }

    public static void KillWacliProcesses()
    {
        foreach (var p in Process.GetProcessesByName("wacli"))
        {
            try
            {
                if (!p.HasExited)
                    p.Kill(true);
            }
            catch { /* ignore */ }
            finally
            {
                p.Dispose();
            }
        }
        Thread.Sleep(300);
    }

    private static ProcessStartInfo CreateWacliStartInfo()
    {
        if (!File.Exists(AppConfig.WacliExe))
        {
            throw new InvalidOperationException(
                $"未找到 wacli：{AppConfig.WacliExe}{Environment.NewLine}" +
                "请点击主页右下角「配置环境」，通过 Git 下载并编译 wacli。");
        }

        var psi = new ProcessStartInfo
        {
            FileName = AppConfig.WacliExe,
            WorkingDirectory = AppConfig.StoreDir,
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        AppConfig.ApplyWacliEnvironment(psi.Environment);
        return psi;
    }

    private void EmitLog(string line) => LogLine?.Invoke(line);
}

public readonly record struct WacliResult(bool Ok, int Code, string Stdout, string Stderr);
