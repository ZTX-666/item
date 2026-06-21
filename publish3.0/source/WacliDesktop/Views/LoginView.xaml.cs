using System.Text;
using System.Windows;
using System.Windows.Controls;
using WacliDesktop.Helpers;
using WacliDesktop.Services;

namespace WacliDesktop.Views;

public partial class LoginView : UserControl
{
    private readonly AppServices _app = AppServices.Instance;
    private readonly StringBuilder _authLog = new();

    private Action<string>? _onLog;
    private Action<string>? _onQr;
    private Action<string>? _onPairing;
    private Action<string>? _onAuthState;

    public LoginView()
    {
        InitializeComponent();
        _onLog = OnLog;
        _onQr = p => Dispatcher.Invoke(() => QrImage.Source = QrHelper.CreateImage(p));
        _onPairing = c => Dispatcher.Invoke(() =>
        {
            PairingCodeText.Text = c;
            PairingHintText.Text = "请在手机上输入配对码";
        });
        _onAuthState = s =>
        {
            if (s is "authenticated" or "syncing")
                Dispatcher.Invoke(() =>
                {
                    if (!_app.Wacli.SyncRunning)
                        _app.Wacli.StartSync(interruptAuth: true);
                    RefreshStatus();
                    _app.RefreshStatus();
                });
            else if (s is "waiting_phone_confirm")
                Dispatcher.Invoke(() =>
                {
                    PairingHintText.Text = "请在手机上输入上方配对码完成关联";
                    RefreshStatus();
                });
            else if (s is "failed")
                Dispatcher.Invoke(() =>
                {
                    if (PairingCodeText.Text is "等待…" or "—")
                        PairingCodeText.Text = "失败";
                    PairingHintText.Text = FormatAuthError(_app.Wacli.LastAuthError);
                    RefreshStatus();
                });
            else if (s is "ended")
                Dispatcher.Invoke(RefreshStatus);
        };

        Loaded += OnLoaded;
        Unloaded += OnUnloaded;
    }

    private void OnLoaded(object sender, RoutedEventArgs e)
    {
        _app.Wacli.LogLine += _onLog;
        _app.Wacli.QrPayloadReceived += _onQr!;
        _app.Wacli.PairingCodeReceived += _onPairing!;
        _app.Wacli.AuthStateChanged += _onAuthState!;
        if (!string.IsNullOrEmpty(_app.Wacli.LastPairingCode))
            PairingCodeText.Text = _app.Wacli.LastPairingCode;
        RefreshStatus();
    }

    private void OnUnloaded(object sender, RoutedEventArgs e)
    {
        _app.Wacli.LogLine -= _onLog;
        _app.Wacli.QrPayloadReceived -= _onQr!;
        _app.Wacli.PairingCodeReceived -= _onPairing!;
        _app.Wacli.AuthStateChanged -= _onAuthState!;
    }

    private void OnLog(string line)
    {
        Dispatcher.Invoke(() =>
        {
            if (_authLog.Length > 8000) _authLog.Remove(0, 4000);
            _authLog.AppendLine(line);
            AuthLogBox.Text = _authLog.ToString();
            AuthLogBox.ScrollToEnd();
        });
    }

    private void RefreshStatus() => StatusBox.Text = _app.Wacli.GetStatusText();

    private void BtnQrStart_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            QrImage.Source = null;
            PairingCodeText.Text = "—";
            PairingHintText.Text = "";
            _authLog.Clear();
            AuthLogBox.Clear();
            _app.Wacli.StartQrAuth();
        }
        catch (Exception ex) { MessageBox.Show(ex.Message, "二维码登录"); }
    }

    private void BtnPhoneStart_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            AppConfig.SwitchToPhone(PhoneInput.Text, out _);
            PairingCodeText.Text = "等待…";
            PairingHintText.Text = "正在连接 wacli，请稍候…";
            _authLog.Clear();
            AuthLogBox.Clear();
            _app.Wacli.StartPhoneAuth(PhoneInput.Text);
        }
        catch (Exception ex)
        {
            PairingCodeText.Text = "—";
            PairingHintText.Text = "";
            MessageBox.Show(ex.Message, "手机号登录");
        }
    }

    private void BtnAuthStop_Click(object sender, RoutedEventArgs e)
    {
        _app.Wacli.StopAuth();
        RefreshStatus();
        _app.RefreshStatus();
    }

    private void BtnSyncStart_Click(object sender, RoutedEventArgs e)
    {
        _app.Wacli.StartSync(interruptAuth: true);
        RefreshStatus();
    }

    private void BtnSyncStop_Click(object sender, RoutedEventArgs e)
    {
        _app.Wacli.StopSync();
        RefreshStatus();
    }

    private void BtnLogout_Click(object sender, RoutedEventArgs e)
    {
        if (MessageBox.Show("确定退出 WhatsApp 登录？", "确认", MessageBoxButton.YesNo, MessageBoxImage.Warning) != MessageBoxResult.Yes)
            return;
        _app.Wacli.Logout();
        QrImage.Source = null;
        PairingCodeText.Text = "—";
        RefreshStatus();
        _app.RefreshStatus();
    }

    private void BtnRefreshStatus_Click(object sender, RoutedEventArgs e)
    {
        RefreshStatus();
        _app.RefreshStatus();
    }

    private static string FormatAuthError(string? raw)
    {
        if (string.IsNullOrWhiteSpace(raw))
            return "认证进程异常结束，请重试";

        if (raw.Contains("429", StringComparison.Ordinal) ||
            raw.Contains("rate-overlimit", StringComparison.OrdinalIgnoreCase) ||
            raw.Contains("rate limit", StringComparison.OrdinalIgnoreCase))
        {
            return "WhatsApp 请求过于频繁（429 限流），手机号配对码暂时无法生成。"
                   + "请等待 30–60 分钟后再试，或改用左侧二维码登录。";
        }

        return raw;
    }
}
