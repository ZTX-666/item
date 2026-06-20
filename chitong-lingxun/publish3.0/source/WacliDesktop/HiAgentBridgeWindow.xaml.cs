using System.Windows;
using WacliDesktop.Services;

namespace WacliDesktop;

public partial class HiAgentBridgeWindow : Window
{
    private static readonly HiAgentBridgeService SharedBridge = new();
    private readonly HiAgentBridgeService _bridge = SharedBridge;
    private CancellationTokenSource? _cts;
    private Action<string>? _onLog;

    public HiAgentBridgeWindow()
    {
        InitializeComponent();
        _onLog = line => Dispatcher.Invoke(() => AppendLog(line));
        _bridge.StateChanged += RefreshUi;
        _bridge.LogLine += _onLog;
        Loaded += (_, _) =>
        {
            _bridge.ReloadConfig();
            RefreshUi();
        };
        Closed += (_, _) =>
        {
            _cts?.Cancel();
            _bridge.StateChanged -= RefreshUi;
            if (_onLog is not null)
                _bridge.LogLine -= _onLog;
        };
    }

    private void RefreshUi()
    {
        var cfg = _bridge.Config;
        PublicUrlBox.Text = cfg.PublicBaseUrl ?? "（未启动）";
        ApiKeyBox.Text = cfg.ApiKey;
        TestUrlBox.Text = string.IsNullOrEmpty(cfg.PublicBaseUrl)
            ? $"{_bridge.LocalBaseUrl}/health"
            : $"{cfg.PublicBaseUrl}/health";

        var api = _bridge.ApiRunning ? "API 运行中" : "API 未启动";
        var tun = _bridge.TunnelRunning ? "隧道运行中" : "隧道未启动";
        StatusLine.Text = $"{api} · {tun} · 数据：{AppConfig.ResolveReadableDbPath()}";
        BtnStop.IsEnabled = _bridge.ApiRunning || _bridge.TunnelRunning;
    }

    private async void Start_Click(object sender, RoutedEventArgs e)
    {
        _bridge.SetApiKey(ApiKeyBox.Text);
        BtnStart.IsEnabled = false;
        _cts = new CancellationTokenSource();
        var progress = new Progress<string>(AppendLog);
        try
        {
            AppendLog("");
            AppendLog("━━━ 开始 HiAgent 对接 ━━━");
            await _bridge.StartAllAsync(progress, _cts.Token);
            AppendLog("");
            AppendLog(_bridge.BuildHiAgentConfigText());
            RefreshUi();
        }
        catch (Exception ex)
        {
            AppendLog("");
            AppendLog("错误：" + ex.Message);
        }
        finally
        {
            BtnStart.IsEnabled = true;
        }
    }

    private void Stop_Click(object sender, RoutedEventArgs e)
    {
        _bridge.StopAll();
        AppendLog("已停止本机 API 与隧道。");
        RefreshUi();
    }

    private void RegenKey_Click(object sender, RoutedEventArgs e)
    {
        _bridge.RegenerateApiKey();
        ApiKeyBox.Text = _bridge.Config.ApiKey;
    }

    private void CopyPublicUrl_Click(object sender, RoutedEventArgs e) =>
        Copy(PublicUrlBox.Text);

    private void CopyTestUrl_Click(object sender, RoutedEventArgs e) =>
        Copy(TestUrlBox.Text);

    private void CopyAll_Click(object sender, RoutedEventArgs e) =>
        Copy(_bridge.BuildHiAgentConfigText());

    private void Close_Click(object sender, RoutedEventArgs e) => Close();

    private void AppendLog(string line)
    {
        if (string.IsNullOrEmpty(line)) return;
        LogBox.AppendText(line + Environment.NewLine);
        LogBox.ScrollToEnd();
    }

    private static void Copy(string text)
    {
        if (string.IsNullOrWhiteSpace(text)) return;
        Clipboard.SetText(text);
        MessageBox.Show("已复制到剪贴板。", "HiAgent 对接", MessageBoxButton.OK, MessageBoxImage.Information);
    }
}
