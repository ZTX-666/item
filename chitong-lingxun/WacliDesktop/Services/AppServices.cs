using System.Windows;
using System.Windows.Threading;
using WacliDesktop.Services;
using System.Text.RegularExpressions;

namespace WacliDesktop;

public sealed class AppServices : IDisposable
{
    private static readonly Regex PhoneRegex = new(@"\+?\d{6,20}", RegexOptions.Compiled);
    public static AppServices Instance { get; } = new();

    public WacliService Wacli { get; } = new();
    public FileIconService FileIcons { get; } = new();
    public ThumbnailService Thumbnails { get; }
    public SqliteQueryService Sqlite { get; } = new();
    public MediaBackfillService MediaBackfill { get; }
    public ModuleWindowManager Modules { get; } = new();

    private readonly DispatcherTimer _statusTimer;
    private bool _started;

    private AppServices()
    {
        Thumbnails = new ThumbnailService(FileIcons);
        MediaBackfill = new MediaBackfillService(Wacli, Thumbnails);

        _statusTimer = new DispatcherTimer { Interval = TimeSpan.FromMinutes(5) };
        _statusTimer.Tick += (_, _) =>
        {
            RefreshStatus();
            RefreshMediaProgress();
        };

        DatabaseProfileStore.Instance.PhoneSwitched += OnPhoneSwitched;
    }

    public event Action? StatusChanged;
    public event Action? MediaProgressChanged;

    public string AuthStatusText { get; private set; } = "检测中…";
    public string MediaProgressText { get; private set; } = "";

    public void StartBackgroundServices()
    {
        if (_started) return;
        _started = true;
        RefreshStatus();
        RefreshMediaProgress();
        MediaBackfill.Start();
        _statusTimer.Start();
        TryAutoStartSync();
    }

    public void RefreshStatus()
    {
        try
        {
            if (Wacli.AuthRunning)
            {
                AuthStatusText = Wacli.LastPairingCode is not null ? "等待手机确认" : "登录中…";
                StatusChanged?.Invoke();
                return;
            }

            var text = Wacli.GetStatusText();
            var authed = text.Contains("Authenticated as", StringComparison.OrdinalIgnoreCase)
                         || text.Contains("AUTHENTICATED     true", StringComparison.OrdinalIgnoreCase);
            var disconnected = authed && IsLinkDisconnected(text);
            AuthStatusText = disconnected ? "链接断开" : (authed ? "已登录" : "未登录");
            if (authed)
                TryBindPhoneFromStatus(text);
        }
        catch (Exception ex)
        {
            AuthStatusText = $"错误: {ex.Message}";
        }
        StatusChanged?.Invoke();
    }

    public void RefreshMediaProgress()
    {
        var (pending, downloaded) = MediaBackfill.GetCounts();
        var total = downloaded + pending;
        MediaProgressText = total > 0 ? $"附件：{downloaded}/{total} 已下载" : $"附件：{downloaded} 已下载";
        MediaProgressChanged?.Invoke();
    }

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

    public void Dispose()
    {
        DatabaseProfileStore.Instance.PhoneSwitched -= OnPhoneSwitched;
        _statusTimer.Stop();
        MediaBackfill.Dispose();
        Wacli.StopAuth();
        Wacli.StopSync();
    }

    private void OnPhoneSwitched(string phone)
    {
        Wacli.StopSync();
        RefreshStatus();
        RefreshMediaProgress();
        TryAutoStartSync();
    }

    private static void TryBindPhoneFromStatus(string statusText)
    {
        var m = PhoneRegex.Match(statusText ?? "");
        if (!m.Success)
            return;

        var phone = m.Value;
        if (AppConfig.SwitchToPhone(phone, out var msg) && !string.IsNullOrEmpty(msg))
            System.Diagnostics.Debug.WriteLine(msg);
    }

    private static bool IsLinkDisconnected(string text)
    {
        if (string.IsNullOrWhiteSpace(text))
            return false;
        return text.Contains("CONNECTED     false", StringComparison.OrdinalIgnoreCase)
               || text.Contains("connected      false", StringComparison.OrdinalIgnoreCase)
               || text.Contains("disconnected", StringComparison.OrdinalIgnoreCase)
               || text.Contains("offline", StringComparison.OrdinalIgnoreCase);
    }
}
