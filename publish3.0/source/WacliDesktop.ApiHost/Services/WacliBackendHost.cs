using System.Text.RegularExpressions;
using Microsoft.Data.Sqlite;
using WacliDesktop.Services;

namespace WacliDesktop.ApiHost.Services;

public sealed class WacliBackendHost : IDisposable
{
    private static readonly Regex PhoneRegex = new(@"\+?\d{6,20}", RegexOptions.Compiled);

    private readonly AuthEventBroadcaster _events;
    private readonly Timer _statusTimer;
    private bool _started;

    public WacliService Wacli { get; } = new();
    public SqliteQueryService Sqlite { get; } = new();
    public AgentToolboxClient Toolbox { get; } = new();

    public WacliBackendHost(AuthEventBroadcaster events)
    {
        _events = events;

        Wacli.LogLine += line => _events.Publish("log", new { line });
        Wacli.QrPayloadReceived += payload => _events.Publish("qr", new { payload });
        Wacli.PairingCodeReceived += code => _events.Publish("pairing_code", new { code });
        Wacli.AuthStateChanged += state => _events.Publish("auth_state", new { state });

        _statusTimer = new Timer(_ => RefreshStatusSafe(), null, Timeout.Infinite, Timeout.Infinite);
        DatabaseProfileStore.Instance.PhoneSwitched += OnPhoneSwitched;
    }

    public void EnsureStarted()
    {
        if (_started) return;
        _started = true;
        _statusTimer.Change(TimeSpan.FromMinutes(1), TimeSpan.FromMinutes(1));
        _ = Task.Run(() =>
        {
            RefreshStatusSafe();
            TryAutoStartSync();
        });
    }

    public AppStatusSnapshot GetStatus()
    {
        var wacliExists = File.Exists(AppConfig.WacliExe);
        var authText = wacliExists || Wacli.AuthRunning || Wacli.SyncRunning
            ? SafeGetStatusText()
            : $"wacli 未安装：{AppConfig.WacliExe}";
        var authed = wacliExists && IsAuthenticated(authText);
        var disconnected = authed && IsLinkDisconnected(authText);
        var media = GetMediaCounts();

        return new AppStatusSnapshot
        {
            AuthStatusText = disconnected ? "链接断开" : authed ? "已登录" :
                Wacli.AuthRunning ? (Wacli.LastPairingCode is not null ? "等待手机确认" : "登录中…") : "未登录",
            Authenticated = authed,
            Disconnected = disconnected,
            AuthRunning = Wacli.AuthRunning,
            SyncRunning = Wacli.SyncRunning,
            PairingCode = Wacli.LastPairingCode,
            LastAuthError = Wacli.LastAuthError,
            CurrentPhone = AppConfig.CurrentPhone,
            AppRoot = AppConfig.AppRoot,
            RuntimeDir = AppConfig.RuntimeDir,
            StoreDir = AppConfig.StoreDir,
            DbPath = AppConfig.ResolveReadableDbPath(),
            DefaultDatabaseRoot = AppConfig.DefaultDatabaseRoot,
            ThumbnailDir = AppConfig.ThumbnailDir,
            WacliExe = AppConfig.WacliExe,
            WacliExeExists = File.Exists(AppConfig.WacliExe),
            MediaDownloaded = media.Downloaded,
            MediaPending = media.Pending,
            MediaProgressText = media.Total > 0
                ? $"附件：{media.Downloaded}/{media.Total} 已下载"
                : $"附件：{media.Downloaded} 已下载",
            StatusDetail = authText,
        };
    }

    public DbProfileSnapshot GetDbProfile() => new()
    {
        CurrentPhone = AppConfig.CurrentPhone,
        DefaultDatabaseRoot = AppConfig.DefaultDatabaseRoot,
        StoreDir = AppConfig.StoreDir,
        DbPath = AppConfig.ResolveReadableDbPath(),
        ThumbnailDir = AppConfig.ThumbnailDir,
    };

    public void TryAutoStartSync()
    {
        try
        {
            if (Wacli.AuthRunning)
                return;

            var auth = Wacli.Run(["auth", "status"]);
            if (!auth.Stdout.Contains("Authenticated as", StringComparison.OrdinalIgnoreCase))
                return;
            if (!Wacli.SyncRunning)
                Wacli.StartSync();
        }
        catch
        {
            /* ignore */
        }
    }

    private void RefreshStatusSafe()
    {
        try
        {
            if (Wacli.AuthRunning)
                return;

            var text = SafeGetStatusText();
            if (IsAuthenticated(text))
                TryBindPhoneFromStatus(text);
        }
        catch
        {
            /* ignore */
        }
    }

    private void OnPhoneSwitched(string phone)
    {
        Wacli.StopSync();
        RefreshStatusSafe();
        TryAutoStartSync();
        _events.Publish("phone_switched", new { phone });
    }

    private string SafeGetStatusText()
    {
        try
        {
            return Wacli.GetStatusText();
        }
        catch (Exception ex)
        {
            return ex.Message;
        }
    }

    private static bool IsAuthenticated(string text) =>
        text.Contains("Authenticated as", StringComparison.OrdinalIgnoreCase)
        || text.Contains("AUTHENTICATED     true", StringComparison.OrdinalIgnoreCase);

    private static bool IsLinkDisconnected(string text)
    {
        if (string.IsNullOrWhiteSpace(text))
            return false;
        return text.Contains("CONNECTED     false", StringComparison.OrdinalIgnoreCase)
               || text.Contains("connected      false", StringComparison.OrdinalIgnoreCase)
               || text.Contains("disconnected", StringComparison.OrdinalIgnoreCase)
               || text.Contains("offline", StringComparison.OrdinalIgnoreCase);
    }

    private static void TryBindPhoneFromStatus(string statusText)
    {
        var m = PhoneRegex.Match(statusText ?? "");
        if (!m.Success)
            return;
        AppConfig.SwitchToPhone(m.Value, out _);
    }

    private static (int Pending, int Downloaded, int Total) GetMediaCounts()
    {
        var db = AppConfig.ResolveReadableDbPath();
        if (!File.Exists(db))
            return (0, 0, 0);

        using var conn = new SqliteConnection($"Data Source={db};Mode=ReadOnly");
        conn.Open();
        var pending = Scalar(conn, """
            SELECT COUNT(*) FROM messages
            WHERE media_type IS NOT NULL AND TRIM(media_type) != ''
              AND (local_path IS NULL OR TRIM(local_path) = '')
              AND revoked = 0 AND deleted_for_me = 0
            """);
        var downloaded = Scalar(conn, """
            SELECT COUNT(*) FROM messages
            WHERE local_path IS NOT NULL AND TRIM(local_path) != ''
              AND revoked = 0 AND deleted_for_me = 0
            """);
        return (pending, downloaded, pending + downloaded);
    }

    private static int Scalar(SqliteConnection conn, string sql)
    {
        using var cmd = conn.CreateCommand();
        cmd.CommandText = sql;
        return Convert.ToInt32(cmd.ExecuteScalar() ?? 0);
    }

    public void Dispose()
    {
        DatabaseProfileStore.Instance.PhoneSwitched -= OnPhoneSwitched;
        _statusTimer.Dispose();
        Wacli.StopAuth();
        Wacli.StopSync();
    }
}

public sealed class AppStatusSnapshot
{
    public string AuthStatusText { get; init; } = "";
    public bool Authenticated { get; init; }
    public bool Disconnected { get; init; }
    public bool AuthRunning { get; init; }
    public bool SyncRunning { get; init; }
    public string? PairingCode { get; init; }
    public string? LastAuthError { get; init; }
    public string CurrentPhone { get; init; } = "";
    public string AppRoot { get; init; } = "";
    public string RuntimeDir { get; init; } = "";
    public string StoreDir { get; init; } = "";
    public string DbPath { get; init; } = "";
    public string DefaultDatabaseRoot { get; init; } = "";
    public string ThumbnailDir { get; init; } = "";
    public string WacliExe { get; init; } = "";
    public bool WacliExeExists { get; init; }
    public int MediaDownloaded { get; init; }
    public int MediaPending { get; init; }
    public string MediaProgressText { get; init; } = "";
    public string StatusDetail { get; init; } = "";
}

public sealed class DbProfileSnapshot
{
    public string CurrentPhone { get; init; } = "";
    public string DefaultDatabaseRoot { get; init; } = "";
    public string StoreDir { get; init; } = "";
    public string DbPath { get; init; } = "";
    public string ThumbnailDir { get; init; } = "";
}
