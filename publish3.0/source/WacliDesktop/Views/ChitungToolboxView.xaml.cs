using System.Data;
using System.Net.Http;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Shapes;
using System.Windows.Threading;
using WacliDesktop.Services;

namespace WacliDesktop.Views;

public partial class ChitungToolboxView : UserControl
{
    private readonly AppServices _app = AppServices.Instance;
    private readonly AgentToolboxClient _client = new();
    private readonly HiAgentBridgeService _bridge = new();
    private readonly DispatcherTimer _statusTimer;

    public ChitungToolboxView()
    {
        InitializeComponent();
        Loaded += OnLoaded;
        Unloaded += OnUnloaded;

        _statusTimer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(3) };
        _statusTimer.Tick += (_, _) => RefreshStatus();
    }

    private void OnLoaded(object sender, RoutedEventArgs e)
    {
        _bridge.ReloadConfig();
        _statusTimer.Start();
        RefreshStatus();
    }

    private void OnUnloaded(object sender, RoutedEventArgs e)
    {
        _statusTimer.Stop();
    }

    private async void RefreshStatus()
    {
        var agentOk = await _client.HealthCheckAsync();
        SetStatus(AgentToolboxDot, AgentToolboxStatus, agentOk, "8899 已连接", "8899 未启动");

        var localApiOk = false;
        try
        {
            using var http = new HttpClient { Timeout = TimeSpan.FromSeconds(2) };
            var resp = await http.GetAsync($"http://127.0.0.1:{_bridge.Config.Port}/health");
            localApiOk = resp.IsSuccessStatusCode;
        }
        catch { }
        SetStatus(LocalApiDot, LocalApiStatus, localApiOk, $"{_bridge.Config.Port} 已启动", $"{_bridge.Config.Port} 未启动");
    }

    private static void SetStatus(Ellipse dot, TextBlock text, bool ok, string okText, string failText)
    {
        dot.Fill = ok ? new SolidColorBrush(Color.FromRgb(0x52, 0xc4, 0x1a)) : new SolidColorBrush(Color.FromRgb(0xe2, 0x4b, 0x4a));
        text.Text = ok ? okText : failText;
    }

    private async void BtnStartLocalApi_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var progress = new Progress<string>(msg =>
            {
                Dispatcher.Invoke(() => LocalApiStatus.Text = msg);
            });
            await _bridge.StartApiAsync(progress);
            RefreshStatus();
        }
        catch (Exception ex)
        {
            MessageBox.Show(ex.Message, "启动本地 API 失败", MessageBoxButton.OK, MessageBoxImage.Warning);
        }
    }

    private void BtnRefreshStatus_Click(object sender, RoutedEventArgs e) => RefreshStatus();

    private async void BtnWaSearch_Click(object sender, RoutedEventArgs e)
    {
        var q = WaSearchInput.Text.Trim();
        if (string.IsNullOrEmpty(q))
        {
            MessageBox.Show("请输入关键词。", "WhatsApp 搜索");
            return;
        }
        if (!int.TryParse(WaLimitInput.Text, out var limit))
            limit = 20;
        var chat = WaChatInput.Text.Trim();
        if (string.IsNullOrEmpty(chat)) chat = null;

        WaSummary.Text = "搜索中…";
        WaResultGrid.ItemsSource = null;
        var result = await _client.WhatsAppSearchAsync(q, chat, limit);
        RenderResult(result, WaSummary, WaResultGrid, "rows");
    }

    private async void BtnCaseQuery_Click(object sender, RoutedEventArgs e)
    {
        if (!int.TryParse(CaseLimitInput.Text, out var limit))
            limit = 50;
        var status = CaseStatusInput.Text.Trim();
        var scene = CaseSceneInput.Text.Trim();
        var risk = CaseRiskInput.Text.Trim();

        CaseSummary.Text = "查询中…";
        CaseResultGrid.ItemsSource = null;
        var result = await _client.QuerySafetyCasesAsync(
            string.IsNullOrEmpty(status) ? null : status,
            string.IsNullOrEmpty(scene) ? null : scene,
            string.IsNullOrEmpty(risk) ? null : risk,
            limit);
        RenderResult(result, CaseSummary, CaseResultGrid, "items");
    }

    private async void BtnFormSearch_Click(object sender, RoutedEventArgs e)
    {
        if (!int.TryParse(FormLimitInput.Text, out var limit))
            limit = 20;
        var query = FormQueryInput.Text.Trim();
        var scene = FormSceneInput.Text.Trim();

        FormSummary.Text = "搜索中…";
        FormResultGrid.ItemsSource = null;
        var result = await _client.SearchFormTemplatesAsync(
            string.IsNullOrEmpty(query) ? null : query,
            string.IsNullOrEmpty(scene) ? null : scene,
            limit);
        RenderResult(result, FormSummary, FormResultGrid, "items");
    }

    private static void RenderResult(ToolResult result, TextBlock summary, DataGrid grid, string arrayKey)
    {
        if (!result.Ok)
        {
            summary.Text = $"失败：{result.Summary} {result.Error}";
            grid.ItemsSource = null;
            return;
        }

        summary.Text = result.Summary;
        var table = JsonToDataTable(result.Data, arrayKey);
        grid.ItemsSource = table.DefaultView;
    }

    private static DataTable JsonToDataTable(JsonElement data, string arrayKey)
    {
        var table = new DataTable();
        if (data.ValueKind == JsonValueKind.Object && data.TryGetProperty(arrayKey, out var array) && array.ValueKind == JsonValueKind.Array)
        {
            foreach (var item in array.EnumerateArray())
            {
                if (item.ValueKind != JsonValueKind.Object) continue;
                var row = table.NewRow();
                foreach (var prop in item.EnumerateObject())
                {
                    if (!table.Columns.Contains(prop.Name))
                        table.Columns.Add(prop.Name, typeof(string));
                    row[prop.Name] = JsonValueToString(prop.Value);
                }
                table.Rows.Add(row);
            }
        }
        return table;
    }

    private static string JsonValueToString(JsonElement value)
    {
        return value.ValueKind switch
        {
            JsonValueKind.Null or JsonValueKind.Undefined => "",
            JsonValueKind.String => value.GetString() ?? "",
            JsonValueKind.True => "true",
            JsonValueKind.False => "false",
            JsonValueKind.Number => value.GetRawText(),
            _ => value.GetRawText(),
        };
    }
}
