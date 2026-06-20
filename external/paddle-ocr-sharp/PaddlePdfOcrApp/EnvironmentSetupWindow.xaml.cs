using System;
using System.IO;
using System.Windows;
using PaddlePdfOcrApp.Services;

namespace PaddlePdfOcrApp;

public partial class EnvironmentSetupWindow : Window
{
    private readonly string _baseDirectory;
    private CancellationTokenSource? _cts;

    public string? InstalledPythonPath { get; private set; }

    public EnvironmentSetupWindow(string baseDirectory)
    {
        _baseDirectory = baseDirectory;
        InitializeComponent();
    }

    private void AppendLog(string line)
    {
        LogTextBox.AppendText(line + Environment.NewLine);
        LogTextBox.ScrollToEnd();
    }

    private async void StartButton_OnClick(object sender, RoutedEventArgs e)
    {
        StartButton.IsEnabled = false;
        _cts?.Cancel();
        _cts = new CancellationTokenSource();
        var log = new Progress<string>(AppendLog);

        try
        {
            AppendLog("—— 開始 ——");
            using var setup = new EnvironmentSetupService(_baseDirectory);
            await setup.RunFullSetupAsync(log, _cts.Token).ConfigureAwait(true);

            InstalledPythonPath = Path.Combine(_baseDirectory, "python_portable", "python.exe");
            if (!File.Exists(InstalledPythonPath))
            {
                InstalledPythonPath = null;
                throw new InvalidOperationException("未找到 python_portable\\python.exe。");
            }

            AppendLog("—— 全部完成 ——");
            MessageBox.Show(
                "環境配置完成。\n已寫入可攜式 Python 至程式目錄，請確認 appsettings.local.json 的 PythonExePath（程式會自動偵測）。\n若剛安裝了 .NET Runtime，建議關閉並重新開啟本程式。",
                "完成",
                MessageBoxButton.OK,
                MessageBoxImage.Information);
            DialogResult = true;
        }
        catch (OperationCanceledException)
        {
            AppendLog("已取消。");
        }
        catch (Exception ex)
        {
            AppendLog("錯誤：" + ex.Message);
            MessageBox.Show(ex.Message, "配置失敗", MessageBoxButton.OK, MessageBoxImage.Error);
        }
        finally
        {
            StartButton.IsEnabled = true;
        }
    }

    private void CloseButton_OnClick(object sender, RoutedEventArgs e)
    {
        _cts?.Cancel();
        DialogResult = false;
        Close();
    }
}
