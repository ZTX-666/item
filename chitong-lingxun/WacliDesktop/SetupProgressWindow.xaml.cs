using System.Text;
using System.Windows;
using WacliDesktop.Services;

namespace WacliDesktop;

public partial class SetupProgressWindow : Window
{
    private readonly StringBuilder _log = new();
    private CancellationTokenSource? _cts;

    public SetupProgressWindow()
    {
        InitializeComponent();
    }

    protected override async void OnContentRendered(EventArgs e)
    {
        base.OnContentRendered(e);
        _cts = new CancellationTokenSource();
        var progress = new Progress<string>(AppendLog);
        try
        {
            await new EnvironmentSetupService().RunAsync(progress, _cts.Token);
            AppendLog("");
            AppendLog("环境配置已完成。");
        }
        catch (Exception ex)
        {
            AppendLog("");
            AppendLog("错误：" + ex.Message);
        }
        finally
        {
            BtnClose.IsEnabled = true;
        }
    }

    private void AppendLog(string line)
    {
        Dispatcher.Invoke(() =>
        {
            _log.AppendLine(line);
            LogBox.Text = _log.ToString();
            LogBox.ScrollToEnd();
        });
    }

    private void Close_Click(object sender, RoutedEventArgs e)
    {
        _cts?.Cancel();
        Close();
    }

    protected override void OnClosed(EventArgs e)
    {
        _cts?.Cancel();
        _cts?.Dispose();
        base.OnClosed(e);
    }
}
