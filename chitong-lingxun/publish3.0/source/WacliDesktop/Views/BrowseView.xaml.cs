using System.Data;
using System.Diagnostics;
using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using Microsoft.Win32;
using WacliDesktop.Models;
using WacliDesktop.Services;

namespace WacliDesktop.Views;

public partial class BrowseView : UserControl
{
    private readonly AppServices _app = AppServices.Instance;
    private List<MessageRowViewModel> _sourceRows = [];
    private readonly Dictionary<string, HashSet<string>?> _columnFilters = new();
    private string? _activeFilterColumn;
    private readonly Dictionary<string, CheckBox> _filterCheckBoxes = new();
    private string _currentPreset = "message_detail";

    public BrowseView()
    {
        InitializeComponent();
        Loaded += OnLoaded;
        Unloaded += OnUnloaded;
    }

    private void OnLoaded(object sender, RoutedEventArgs e)
    {
        _app.MediaBackfill.DownloadsCompleted += OnDownloadsCompleted;
        UpdateDbPathHint();
        LoadPreset("message_detail");
    }

    private void UpdateDbPathHint()
    {
        DbPathHint.Text =
            $"当前库：{AppConfig.ResolveReadableDbPath()}{Environment.NewLine}" +
            $"默认根目录：{AppConfig.DefaultDatabaseRoot}";
    }

    private void OnUnloaded(object sender, RoutedEventArgs e)
    {
        _app.MediaBackfill.DownloadsCompleted -= OnDownloadsCompleted;
    }

    private void OnDownloadsCompleted()
    {
        if (_currentPreset is not ("message_detail" or "messages_with_attachment"))
            return;
        Dispatcher.Invoke(() => ReloadCurrentMessageList());
    }

    private void ShowMessageList(List<MessageRowViewModel> rows)
    {
        _sourceRows = rows;
        MessageListView.Visibility = Visibility.Visible;
        BrowseGrid.Visibility = Visibility.Collapsed;
        ApplyColumnFilters();
    }

    private void ApplyColumnFilters()
    {
        IEnumerable<MessageRowViewModel> visible = _sourceRows;
        foreach (var (column, selected) in _columnFilters)
        {
            if (selected is null)
                continue;
            visible = visible.Where(r => selected.Contains(GetColumnValue(r, column)));
        }

        var list = visible.ToList();
        MessageListView.ItemsSource = list;
        if (list.Count > 0)
        {
            MessageListView.SelectedIndex = 0;
            AttachmentDetailBox.Text = SqliteQueryService.FormatAttachmentDetail(list[0]);
        }
        else
            AttachmentDetailBox.Text = SqliteQueryService.FormatAttachmentDetail(null);
    }

    private void ShowBrowseGrid(DataTable table)
    {
        MessageListView.Visibility = Visibility.Collapsed;
        BrowseGrid.Visibility = Visibility.Visible;
        BrowseGrid.ItemsSource = table.DefaultView;
    }

    private MessageRowViewModel? GetSelectedMessage() =>
        MessageListView.SelectedItem as MessageRowViewModel;

    private void MessageListView_SelectionChanged(object sender, SelectionChangedEventArgs e) =>
        AttachmentDetailBox.Text = SqliteQueryService.FormatAttachmentDetail(GetSelectedMessage());

    private void LoadPreset(string key)
    {
        _currentPreset = key;
        if (!SqliteQueryService.Presets.TryGetValue(key, out var sql)) return;
        try
        {
            if (key is "message_detail" or "messages_with_attachment")
            {
                var table = key == "message_detail"
                    ? _app.Sqlite.QueryMessagesDetail(100)
                    : _app.Sqlite.RunSelect(sql);
                _columnFilters.Clear();
                ShowMessageList(MessageRowMapper.FromDataTable(table, _app.Thumbnails));
            }
            else
            {
                ShowBrowseGrid(_app.Sqlite.RunSelect(sql));
            }
        }
        catch (Exception ex) { MessageBox.Show(ex.Message, "查询失败"); }
    }

    private void ReloadCurrentMessageList() => LoadPreset(_currentPreset);

    private void Preset_Click(object sender, RoutedEventArgs e)
    {
        if (sender is Button btn && btn.Tag is string key) LoadPreset(key);
    }

    private void ProjectItem_Click(object sender, RoutedEventArgs e)
    {
        if (sender is not Button { Tag: MessageRowViewModel row } || !row.CanOpenFile)
            return;

        try
        {
            Process.Start(new ProcessStartInfo(row.AttachmentLocalPath) { UseShellExecute = true });
        }
        catch (Exception ex)
        {
            MessageBox.Show(ex.Message, "无法打开文件");
        }
    }

    private void BtnExportDb_Click(object sender, RoutedEventArgs e)
    {
        var defaultName = Path.GetFileName(AppConfig.DbPath);
        var dlg = new SaveFileDialog
        {
            FileName = string.IsNullOrWhiteSpace(defaultName) ? "Data Base.db" : defaultName,
            Filter = "SQLite 数据库|*.db;*.sqlite;*.sqlite3|所有文件|*.*",
        };
        if (dlg.ShowDialog() != true)
            return;

        if (AppConfig.ExportDatabase(dlg.FileName, out var message))
            MessageBox.Show(message, "导出数据库", MessageBoxButton.OK, MessageBoxImage.Information);
        else
            MessageBox.Show(message, "导出数据库失败", MessageBoxButton.OK, MessageBoxImage.Warning);
    }

    private void BtnLoadDb_Click(object sender, RoutedEventArgs e)
    {
        var dlg = new OpenFileDialog
        {
            Filter = "SQLite 数据库|*.db;*.sqlite;*.sqlite3|所有文件|*.*",
        };
        if (dlg.ShowDialog() != true)
            return;

        if (!AppConfig.ImportDatabase(dlg.FileName, out var message))
        {
            MessageBox.Show(message, "加载数据库失败", MessageBoxButton.OK, MessageBoxImage.Warning);
            return;
        }

        MessageBox.Show(message, "加载数据库", MessageBoxButton.OK, MessageBoxImage.Information);
        UpdateDbPathHint();
        ReloadCurrentMessageList();
    }

    private void BtnRefreshDb_Click(object sender, RoutedEventArgs e)
    {
        UpdateDbPathHint();
        ReloadCurrentMessageList();
    }

    private void BtnSetDefaultDb_Click(object sender, RoutedEventArgs e)
    {
        var dlg = new OpenFolderDialog
        {
            Title = "选择默认数据库存放根目录",
            InitialDirectory = AppConfig.DefaultDatabaseRoot,
        };
        if (dlg.ShowDialog() != true)
            return;

        if (!AppConfig.SetDefaultDatabaseRoot(dlg.FolderName, out var message))
        {
            MessageBox.Show(message, "默认数据库", MessageBoxButton.OK, MessageBoxImage.Warning);
            return;
        }

        UpdateDbPathHint();
        MessageBox.Show(
            message + Environment.NewLine + Environment.NewLine +
            "说明：已登记账号会尝试整体迁移到新根目录；迁移失败的账号会保留原位置并继续可用。",
            "默认数据库",
            MessageBoxButton.OK,
            MessageBoxImage.Information);
    }

    private void BtnSaveAs_Click(object sender, RoutedEventArgs e)
    {
        var row = GetSelectedMessage();
        if (row is null)
        {
            MessageBox.Show("请先选中一条消息。", "另存");
            return;
        }
        if (!row.HasLocalFile)
        {
            MessageBox.Show("本地尚无附件文件，请等待后台自动下载完成。", "另存");
            return;
        }

        var dlg = new SaveFileDialog
        {
            FileName = Path.GetFileName(row.AttachmentLocalPath),
            Filter = "所有文件|*.*",
        };
        if (dlg.ShowDialog() != true)
            return;

        try
        {
            File.Copy(row.AttachmentLocalPath, dlg.FileName, overwrite: true);
            MessageBox.Show($"已保存到：{dlg.FileName}", "另存", MessageBoxButton.OK, MessageBoxImage.Information);
        }
        catch (Exception ex)
        {
            MessageBox.Show(ex.Message, "另存失败");
        }
    }

    private void BtnSearch_Click(object sender, RoutedEventArgs e)
    {
        var q = SearchInput.Text.Trim();
        if (string.IsNullOrEmpty(q)) return;
        _app.Wacli.Run(["--read-only", "--json", "messages", "search", q, "--limit", "30"]);
        ShowBrowseGrid(new DataTable());
        BrowseGrid.Visibility = Visibility.Visible;
        MessageListView.Visibility = Visibility.Collapsed;
    }

    private void FilterHeader_Click(object sender, RoutedEventArgs e)
    {
        if (sender is not Button { Tag: string column })
            return;

        _activeFilterColumn = column;
        FilterTitleText.Text = $"筛选 · {ColumnTitle(column)}";
        FilterOptionsPanel.Children.Clear();
        _filterCheckBoxes.Clear();

        var values = _sourceRows
            .Select(r => GetColumnValue(r, column))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .OrderBy(v => v, StringComparer.OrdinalIgnoreCase)
            .ToList();

        var active = _columnFilters.GetValueOrDefault(column);
        foreach (var value in values)
        {
            var cb = new CheckBox
            {
                Content = string.IsNullOrEmpty(value) ? "(空白)" : value,
                Tag = value,
                IsChecked = active is null || active.Contains(value),
                Margin = new Thickness(0, 2, 0, 2),
                FontSize = 12,
            };
            _filterCheckBoxes[value] = cb;
            FilterOptionsPanel.Children.Add(cb);
        }

        ColumnFilterPopup.PlacementTarget = sender as UIElement;
        ColumnFilterPopup.IsOpen = true;
    }

    private void FilterSelectAll_Click(object sender, RoutedEventArgs e)
    {
        foreach (var cb in _filterCheckBoxes.Values)
            cb.IsChecked = true;
    }

    private void FilterClear_Click(object sender, RoutedEventArgs e)
    {
        if (_activeFilterColumn is null)
            return;
        _columnFilters.Remove(_activeFilterColumn);
        ColumnFilterPopup.IsOpen = false;
        ApplyColumnFilters();
    }

    private void FilterApply_Click(object sender, RoutedEventArgs e)
    {
        if (_activeFilterColumn is null)
            return;

        var selected = _filterCheckBoxes
            .Where(p => p.Value.IsChecked == true)
            .Select(p => p.Key)
            .ToHashSet(StringComparer.OrdinalIgnoreCase);

        if (selected.Count == _filterCheckBoxes.Count)
            _columnFilters.Remove(_activeFilterColumn);
        else
            _columnFilters[_activeFilterColumn] = selected;

        ColumnFilterPopup.IsOpen = false;
        ApplyColumnFilters();
    }

    private static string GetColumnValue(MessageRowViewModel row, string column) => column switch
    {
        "GroupDisplay" => row.GroupDisplay,
        "MessageDate" => row.MessageDate,
        "WhatsappId" => row.WhatsappId,
        "SenderName" => row.SenderName,
        "AttachmentType" => row.AttachmentType,
        "AttachmentStatus" => row.AttachmentStatus,
        "MessageText" => row.MessageText,
        _ => "",
    };

    private static string ColumnTitle(string column) => column switch
    {
        "GroupDisplay" => "群组",
        "MessageDate" => "日期",
        "WhatsappId" => "ID",
        "SenderName" => "发送人",
        "AttachmentType" => "附件",
        "AttachmentStatus" => "状态",
        "MessageText" => "消息",
        _ => column,
    };
}
