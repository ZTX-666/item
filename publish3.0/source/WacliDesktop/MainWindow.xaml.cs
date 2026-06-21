using System.Data;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Threading;
using WacliDesktop.Helpers;
using WacliDesktop.Models;
using WacliDesktop.Services;

namespace WacliDesktop;

public partial class MainWindow : Window
{
    private readonly WacliService _wacli = new();
    private readonly FileIconService _fileIcons = new();
    private readonly ThumbnailService _thumbnails;
    private readonly SqliteQueryService _sqlite = new();
    private readonly MediaBackfillService _mediaBackfill;
    private readonly StringBuilder _authLog = new();
    private readonly DispatcherTimer _statusTimer;

    public MainWindow()
    {
        InitializeComponent();
        _thumbnails = new ThumbnailService(_fileIcons);
        _mediaBackfill = new MediaBackfillService(_wacli, _thumbnails);

        _wacli.LogLine += line => Dispatcher.Invoke(() => AppendAuthLog(line));
        _wacli.QrPayloadReceived += payload => Dispatcher.Invoke(() =>
        {
            QrImage.Source = QrHelper.CreateImage(payload);
        });
        _wacli.PairingCodeReceived += code => Dispatcher.Invoke(() =>
        {
            PairingCodeText.Text = code;
        });
        _wacli.AuthStateChanged += state => Dispatcher.Invoke(() =>
        {
            if (state is "authenticated" or "syncing")
            {
                RefreshStatus();
                TryAutoStartSyncAndDownload();
            }
        });

        _mediaBackfill.ProgressUpdated += (done, total, _) =>
            Dispatcher.Invoke(() => UpdateMediaProgress(done, total));
        _mediaBackfill.DownloadsCompleted += () =>
            Dispatcher.Invoke(() =>
            {
                UpdateMediaProgressFromDb();
                LoadPreset("message_detail");
            });

        _statusTimer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(5) };
        _statusTimer.Tick += (_, _) =>
        {
            RefreshStatus();
            UpdateMediaProgressFromDb();
        };
        _statusTimer.Start();

        Loaded += (_, _) =>
        {
            LoadTables();
            RefreshStatus();
            UpdateMediaProgressFromDb();
            _mediaBackfill.Start();
            TryAutoStartSyncAndDownload();
            LoadPreset("message_detail");
        };
        Closed += (_, _) =>
        {
            _statusTimer.Stop();
            _mediaBackfill.Dispose();
            _wacli.StopAuth();
            _wacli.StopSync();
        };
    }

    private void TryAutoStartSyncAndDownload()
    {
        try
        {
            var auth = _wacli.Run(["auth", "status"]);
            if (!auth.Stdout.Contains("Authenticated as", StringComparison.OrdinalIgnoreCase))
                return;
            if (!_wacli.SyncRunning)
                _wacli.StartSync();
        }
        catch
        {
            /* ignore */
        }
    }

    private void UpdateMediaProgress(int done, int total)
    {
        MediaDownloadText.Text = total > 0
            ? $"附件：{done}/{total} 已下载"
            : $"附件：{done} 已下载";
    }

    private void UpdateMediaProgressFromDb()
    {
        var (pending, downloaded) = _mediaBackfill.GetCounts();
        UpdateMediaProgress(downloaded, downloaded + pending);
    }

    private void AppendAuthLog(string line)
    {
        if (_authLog.Length > 8000)
            _authLog.Remove(0, 4000);
        _authLog.AppendLine(line);
        AuthLogBox.Text = _authLog.ToString();
        AuthLogBox.ScrollToEnd();
    }

    private void RefreshStatus()
    {
        try
        {
            StatusBox.Text = _wacli.GetStatusText();
            var authed = StatusBox.Text.Contains("Authenticated as", StringComparison.OrdinalIgnoreCase)
                         || StatusBox.Text.Contains("AUTHENTICATED     true", StringComparison.OrdinalIgnoreCase);
            StatusText.Text = authed ? "已登录" : "未登录";
            StatusText.Foreground = Brushes.White;
        }
        catch (Exception ex)
        {
            StatusText.Text = "错误";
            StatusBox.Text = ex.Message;
        }
    }

    private void BtnQrStart_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            QrImage.Source = null;
            _authLog.Clear();
            AuthLogBox.Clear();
            _wacli.StartQrAuth();
        }
        catch (Exception ex)
        {
            MessageBox.Show(ex.Message, "二维码登录", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private void BtnPhoneStart_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            PairingCodeText.Text = "…";
            _authLog.Clear();
            AuthLogBox.Clear();
            _wacli.StartPhoneAuth(PhoneInput.Text);
        }
        catch (Exception ex)
        {
            PairingCodeText.Text = "—";
            MessageBox.Show(ex.Message, "手机号登录", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private void BtnAuthStop_Click(object sender, RoutedEventArgs e)
    {
        _wacli.StopAuth();
        RefreshStatus();
    }

    private void BtnSyncStart_Click(object sender, RoutedEventArgs e)
    {
        _wacli.StartSync();
        RefreshStatus();
    }

    private void BtnSyncStop_Click(object sender, RoutedEventArgs e)
    {
        _wacli.StopSync();
        RefreshStatus();
    }

    private void BtnLogout_Click(object sender, RoutedEventArgs e)
    {
        if (MessageBox.Show("确定退出 WhatsApp 登录？", "确认", MessageBoxButton.YesNo, MessageBoxImage.Warning)
            != MessageBoxResult.Yes)
            return;
        var result = _wacli.Logout();
        CmdOutput.Text = result.Stdout + result.Stderr;
        QrImage.Source = null;
        PairingCodeText.Text = "—";
        RefreshStatus();
    }

    private void BtnRefreshStatus_Click(object sender, RoutedEventArgs e) => RefreshStatus();

    private void LoadTables()
    {
        try
        {
            TableList.ItemsSource = _sqlite.ListTables();
        }
        catch (Exception ex)
        {
            SchemaBox.Text = ex.Message;
        }
    }

    private void TableList_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (TableList.SelectedItem is not string table) return;
        try
        {
            var schema = _sqlite.GetSchema(table);
            SchemaBox.Text = string.Join(Environment.NewLine,
                schema.Select(c => $"{c.Name} {c.Type}{(c.Pk ? " PK" : "")}"));
            SqlInput.Text = table.Equals("messages", StringComparison.OrdinalIgnoreCase)
                ? SqliteQueryService.MessagesDetailSql + " LIMIT 50"
                : $"SELECT * FROM {table} LIMIT 20";
        }
        catch (Exception ex)
        {
            SchemaBox.Text = ex.Message;
        }
    }

    private void ShowMessageList(List<MessageRowViewModel> rows)
    {
        MessageListView.Visibility = Visibility.Visible;
        BrowseGrid.Visibility = Visibility.Collapsed;
        MessageListView.ItemsSource = rows;
        if (rows.Count > 0)
            MessageListView.SelectedIndex = 0;
        else
            AttachmentDetailBox.Text = SqliteQueryService.FormatAttachmentDetail(null);
    }

    private void ShowBrowseGrid(DataTable table)
    {
        MessageListView.Visibility = Visibility.Collapsed;
        BrowseGrid.Visibility = Visibility.Visible;
        BrowseGrid.ItemsSource = table.DefaultView;
        BrowseGrid.Visibility = Visibility.Visible;
    }

    private MessageRowViewModel? GetSelectedMessage() =>
        MessageListView.SelectedItem as MessageRowViewModel;

    private void MessageListView_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        var row = GetSelectedMessage();
        AttachmentDetailBox.Text = SqliteQueryService.FormatAttachmentDetail(row);
    }

    private void LoadPreset(string key)
    {
        if (!SqliteQueryService.Presets.TryGetValue(key, out var sql))
            return;
        try
        {
            if (key is "message_detail" or "messages_with_attachment")
            {
                var table = key == "message_detail"
                    ? _sqlite.QueryMessagesDetail(100)
                    : _sqlite.RunSelect(sql);
                ShowMessageList(MessageRowMapper.FromDataTable(table, _thumbnails));
            }
            else
            {
                ShowBrowseGrid(_sqlite.RunSelect(sql));
            }
        }
        catch (Exception ex)
        {
            MessageBox.Show(ex.Message, "查询失败", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private void Preset_Click(object sender, RoutedEventArgs e)
    {
        if (sender is not Button btn || btn.Tag is not string key) return;
        LoadPreset(key);
    }

    private void LoadDefaultMessagesView() => LoadPreset("message_detail");

    private void BtnDownloadAttachment_Click(object sender, RoutedEventArgs e)
    {
        var row = GetSelectedMessage();
        if (row is null)
        {
            MessageBox.Show("请先在列表中选中一条消息。", "下载附件", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        if (string.IsNullOrEmpty(row.MsgId) || string.IsNullOrEmpty(row.ChatJid))
        {
            MessageBox.Show("选中行缺少 msg_id 或 chat_jid。", "下载附件", MessageBoxButton.OK, MessageBoxImage.Warning);
            return;
        }

        if (row.AttachmentStatus == "无附件")
        {
            MessageBox.Show("该消息在本地库中标记为无附件。", "下载附件", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        var result = _wacli.Run(["media", "download", "--chat", row.ChatJid, "--id", row.MsgId]);
        CmdOutput.Text = result.Stdout + result.Stderr;
        if (!result.Ok)
        {
            MessageBox.Show(
                (result.Stderr + result.Stdout).Trim(),
                "下载失败",
                MessageBoxButton.OK,
                MessageBoxImage.Warning);
            return;
        }

        _thumbnails.Invalidate(row.MsgId);
        LoadPreset("message_detail");
    }

    private void BtnOpenAttachment_Click(object sender, RoutedEventArgs e)
    {
        var row = GetSelectedMessage();
        if (row is null)
        {
            MessageBox.Show("请先选中一条消息。", "打开附件", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        if (!row.HasLocalFile)
        {
            MessageBox.Show("本地尚无附件文件，请等待自动下载完成。", "打开附件", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        Process.Start(new ProcessStartInfo(row.AttachmentLocalPath) { UseShellExecute = true });
    }

    private void BtnSearch_Click(object sender, RoutedEventArgs e)
    {
        var q = SearchInput.Text.Trim();
        if (string.IsNullOrEmpty(q)) return;
        var result = _wacli.Run([
            "--read-only", "--json", "messages", "search", q, "--limit", "30"
        ]);
        CmdOutput.Text = result.Stdout + result.Stderr;
        ShowBrowseGrid(new DataTable());
        BrowseGrid.Visibility = Visibility.Visible;
        MessageListView.Visibility = Visibility.Collapsed;
    }

    private static bool IsMessageResult(DataTable table) =>
        table.Columns.Contains("msg_id") ||
        table.Columns.Contains("sender_jid") ||
        table.Columns.Contains("whatsapp_id");

    private void BindSqlResults(DataTable table)
    {
        if (IsMessageResult(table))
        {
            SqlGrid.Visibility = Visibility.Collapsed;
            SqlMessageListView.Visibility = Visibility.Visible;
            var rows = MessageRowMapper.FromDataTable(table, _thumbnails);
            SqlMessageListView.ItemsSource = rows;
            if (rows.Count > 0)
            {
                SqlMessageListView.SelectedIndex = 0;
                SqlPreviewImage.Source = rows[0].Thumbnail;
            }
            else
                SqlPreviewImage.Source = null;
        }
        else
        {
            SqlMessageListView.Visibility = Visibility.Collapsed;
            SqlGrid.Visibility = Visibility.Visible;
            SqlGrid.ItemsSource = table.DefaultView;
            SqlPreviewImage.Source = null;
        }
    }

    private void SqlMessageListView_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (SqlMessageListView.SelectedItem is MessageRowViewModel row)
            SqlPreviewImage.Source = row.Thumbnail;
    }

    private void SqlGrid_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (SqlGrid.SelectedItem is not DataRowView drv) return;
        var row = MessageRowMapper.FromDataRow(drv.Row, _thumbnails);
        SqlPreviewImage.Source = row.Thumbnail;
    }

    private void BtnSqlRun_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            if (!int.TryParse(SqlLimitInput.Text, out var limit))
                limit = 100;
            BindSqlResults(_sqlite.RunSelect(SqlInput.Text, limit));
        }
        catch (Exception ex)
        {
            MessageBox.Show(ex.Message, "SQL 错误", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private void QuickCmd_Click(object sender, RoutedEventArgs e)
    {
        if (sender is not Button btn || btn.Tag is not string tag) return;
        RunWacliArgs(tag.Split(' ', StringSplitOptions.RemoveEmptyEntries));
    }

    private void BtnCmdRun_Click(object sender, RoutedEventArgs e)
    {
        var text = CmdArgsInput.Text.Trim();
        if (string.IsNullOrEmpty(text)) return;
        RunWacliArgs(text.Split(' ', StringSplitOptions.RemoveEmptyEntries));
    }

    private void RunWacliArgs(string[] args)
    {
        try
        {
            var result = _wacli.Run(args);
            CmdOutput.Text = string.Join(Environment.NewLine + "---" + Environment.NewLine,
                new[] { result.Stdout, result.Stderr }.Where(s => !string.IsNullOrWhiteSpace(s)));
        }
        catch (Exception ex)
        {
            CmdOutput.Text = ex.Message;
        }
    }
}
