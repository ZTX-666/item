using System.Windows;
using System.Windows.Controls;
using WacliDesktop.Services;

namespace WacliDesktop;

public partial class YaoyaoFactoryWindow : Window
{
    private static readonly HiAgentBridgeService SharedBridge = new();
    private readonly HiAgentBridgeService _bridge = SharedBridge;
    private readonly CloudSyncService _cloud = CloudSyncService.Instance;
    private CancellationTokenSource? _syncCts;
    private Action<string>? _cloudLogHandler;
    private Action<string>? _localLogHandler;

    public YaoyaoFactoryWindow()
    {
        InitializeComponent();
        _cloudLogHandler = line => Dispatcher.Invoke(() => AppendCloudLog(line));
        _localLogHandler = line => Dispatcher.Invoke(() => AppendLocalLog(line));

        _cloud.LogLine += _cloudLogHandler;
        _cloud.StateChanged += RefreshCloudUi;
        _bridge.StateChanged += RefreshLocalUi;
        _bridge.LogLine += _localLogHandler;

        Loaded += (_, _) =>
        {
            _cloud.Reload();
            _bridge.ReloadConfig();
            LoadCloudFields();
            RefreshCloudUi();
            RefreshLocalUi();
        };

        Closed += (_, _) =>
        {
            _syncCts?.Cancel();
            _cloud.LogLine -= _cloudLogHandler;
            _cloud.StateChanged -= RefreshCloudUi;
            _bridge.StateChanged -= RefreshLocalUi;
            if (_localLogHandler is not null)
                _bridge.LogLine -= _localLogHandler;
        };
    }

    private void LoadCloudFields()
    {
        var cfg = _cloud.Config;
        ApiBaseUrlBox.Text = cfg.ApiBaseUrl;
        if (!string.IsNullOrEmpty(cfg.SyncToken))
            SyncTokenBox.Password = cfg.SyncToken;
        OwnerIdBox.Text = cfg.OwnerId;
        SyncTierCombo.SelectedIndex = Math.Clamp(cfg.SyncTier, 0, 2);
        AutoSyncCheck.IsChecked = cfg.AutoSyncEnabled;
        IntervalBox.Text = cfg.AutoSyncIntervalMinutes.ToString();
        ApiHelpBox.Text = _cloud.BuildConfigSummary();
    }

    private CloudSyncConfig ReadCloudConfigFromUi()
    {
        var cfg = _cloud.Config;
        cfg.ApiBaseUrl = ApiBaseUrlBox.Text.Trim().TrimEnd('/');
        cfg.SyncToken = SyncTokenBox.Password;
        cfg.OwnerId = OwnerIdBox.Text.Trim();
        cfg.SyncTier = SyncTierCombo.SelectedIndex;
        cfg.AutoSyncEnabled = AutoSyncCheck.IsChecked == true;
        if (int.TryParse(IntervalBox.Text, out var mins))
            cfg.AutoSyncIntervalMinutes = mins;
        return cfg;
    }

    private void RefreshCloudUi()
    {
        var cfg = _cloud.Config;
        var state = CloudSyncState.Load();
        var run = _cloud.IsRunning ? "同步中…" : "空闲";
        CloudStatusLine.Text =
            $"{run} · {CloudSyncConfig.TierLabel(cfg.SyncTier)} · 水位 ts={state.LastMessageTs}" +
            (string.IsNullOrEmpty(cfg.LastSuccessAt) ? "" : $" · 上次成功 {cfg.LastSuccessAt}") +
            (string.IsNullOrEmpty(cfg.LastError) ? "" : $" · 最近错误 {cfg.LastError}");
        BtnSyncNow.IsEnabled = !_cloud.IsRunning;
        ApiHelpBox.Text = _cloud.BuildConfigSummary();
    }

    private void RefreshLocalUi()
    {
        PublicUrlBox.Text = _bridge.Config.PublicBaseUrl ?? "（未启动）";
        LocalApiKeyBox.Text = _bridge.Config.ApiKey;
        var api = _bridge.ApiRunning ? "API运行" : "API未启";
        var tun = _bridge.TunnelRunning ? "隧道运行" : "隧道未启";
        LocalBridgeStatus.Text = $"{api} · {tun} · {_bridge.LocalBaseUrl}";
        BtnStopLocal.IsEnabled = _bridge.ApiRunning || _bridge.TunnelRunning;
    }

    private void SaveCloud_Click(object sender, RoutedEventArgs e)
    {
        var cfg = ReadCloudConfigFromUi();
        _cloud.UpdateConfig(cfg);
        AppendCloudLog("已保存云端同步配置。");
        RefreshCloudUi();
    }

    private async void TestCloud_Click(object sender, RoutedEventArgs e)
    {
        SaveCloud_Click(sender, e);
        BtnTestCloud.IsEnabled = false;
        try
        {
            await _cloud.TestConnectionAsync(new Progress<string>(AppendCloudLog));
        }
        finally
        {
            BtnTestCloud.IsEnabled = true;
            RefreshCloudUi();
        }
    }

    private async void SyncNow_Click(object sender, RoutedEventArgs e)
    {
        SaveCloud_Click(sender, e);
        BtnSyncNow.IsEnabled = false;
        _syncCts = new CancellationTokenSource();
        try
        {
            await _cloud.RunSyncAsync(new Progress<string>(AppendCloudLog), _syncCts.Token);
        }
        catch
        {
            /* logged */
        }
        finally
        {
            BtnSyncNow.IsEnabled = true;
            RefreshCloudUi();
        }
    }

    private void CopyApiHelp_Click(object sender, RoutedEventArgs e) =>
        CopyText(ApiHelpBox.Text, "耀耀工厂");

    private async void StartLocal_Click(object sender, RoutedEventArgs e)
    {
        _bridge.SetApiKey(LocalApiKeyBox.Text);
        BtnStartLocal.IsEnabled = false;
        try
        {
            AppendLocalLog("━━━ 本机调试 API ━━━");
            await _bridge.StartAllAsync(new Progress<string>(AppendLocalLog));
            AppendLocalLog(_bridge.BuildHiAgentConfigText());
            RefreshLocalUi();
        }
        catch (Exception ex)
        {
            AppendLocalLog("错误：" + ex.Message);
        }
        finally
        {
            BtnStartLocal.IsEnabled = true;
        }
    }

    private void StopLocal_Click(object sender, RoutedEventArgs e)
    {
        _bridge.StopAll();
        AppendLocalLog("已停止本机 API 与隧道。");
        RefreshLocalUi();
    }

    private void RegenLocalKey_Click(object sender, RoutedEventArgs e)
    {
        _bridge.RegenerateApiKey();
        LocalApiKeyBox.Text = _bridge.Config.ApiKey;
    }

    private void CopyPublicUrl_Click(object sender, RoutedEventArgs e) =>
        CopyText(PublicUrlBox.Text, "本机调试");

    private void Close_Click(object sender, RoutedEventArgs e) => Close();

    private void AppendCloudLog(string line)
    {
        if (string.IsNullOrEmpty(line)) return;
        CloudLogBox.AppendText(line + Environment.NewLine);
        CloudLogBox.ScrollToEnd();
    }

    private void AppendLocalLog(string line)
    {
        if (string.IsNullOrEmpty(line)) return;
        LocalLogBox.AppendText(line + Environment.NewLine);
        LocalLogBox.ScrollToEnd();
    }

    private static void CopyText(string text, string title)
    {
        if (string.IsNullOrWhiteSpace(text)) return;
        Clipboard.SetText(text);
        MessageBox.Show("已复制到剪贴板。", title, MessageBoxButton.OK, MessageBoxImage.Information);
    }
}
