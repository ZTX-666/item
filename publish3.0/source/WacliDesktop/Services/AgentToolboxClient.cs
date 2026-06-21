using System.Net.Http;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace WacliDesktop.Services;

/// <summary>调用本地 AgentToolbox HTTP 服务（端口 8899）的客户端。</summary>
public sealed class AgentToolboxClient
{
    private readonly HttpClient _http;
    private readonly string _baseUrl;

    public AgentToolboxClient(string baseUrl = "http://127.0.0.1:8899")
    {
        _baseUrl = baseUrl.TrimEnd('/');
        _http = new HttpClient { Timeout = TimeSpan.FromSeconds(30) };
    }

    public async Task<bool> HealthCheckAsync()
    {
        try
        {
            using var resp = await _http.GetAsync($"{_baseUrl}/health");
            return resp.IsSuccessStatusCode;
        }
        catch
        {
            return false;
        }
    }

    public Task<ToolResult> WhatsAppSearchAsync(string q, string? chat = null, int limit = 20)
    {
        var args = new Dictionary<string, object?> { ["q"] = q, ["limit"] = limit };
        if (!string.IsNullOrWhiteSpace(chat)) args["chat"] = chat;
        return CallToolAsync("whatsapp_search", args);
    }

    public Task<ToolResult> QuerySafetyCasesAsync(string? status = null, string? scene = null, string? riskLevel = null, int limit = 50)
    {
        var args = new Dictionary<string, object?> { ["limit"] = limit };
        if (!string.IsNullOrWhiteSpace(status)) args["status"] = status;
        if (!string.IsNullOrWhiteSpace(scene)) args["scene"] = scene;
        if (!string.IsNullOrWhiteSpace(riskLevel)) args["risk_level"] = riskLevel;
        return CallToolAsync("query_safety_cases", args);
    }

    public Task<ToolResult> SearchFormTemplatesAsync(string? query = null, string? scene = null, int limit = 20)
    {
        var args = new Dictionary<string, object?> { ["limit"] = limit };
        if (!string.IsNullOrWhiteSpace(query)) args["query"] = query;
        if (!string.IsNullOrWhiteSpace(scene)) args["scene"] = scene;
        return CallToolAsync("search_form_templates", args);
    }

    public async Task<ToolResult> CallToolAsync(string toolName, Dictionary<string, object?> arguments)
    {
        var url = $"{_baseUrl}/tools/{toolName}";
        var json = JsonSerializer.Serialize(arguments);
        using var content = new StringContent(json, Encoding.UTF8, "application/json");
        using var resp = await _http.PostAsync(url, content);
        var body = await resp.Content.ReadAsStringAsync();
        if (!resp.IsSuccessStatusCode)
        {
            return new ToolResult
            {
                Ok = false,
                Tool = toolName,
                Summary = $"AgentToolbox 返回 HTTP {(int)resp.StatusCode}",
                Error = body,
            };
        }

        try
        {
            return JsonSerializer.Deserialize<ToolResult>(body) ?? new ToolResult
            {
                Ok = false,
                Tool = toolName,
                Summary = "返回为空",
                Error = "Empty response",
            };
        }
        catch (Exception ex)
        {
            return new ToolResult
            {
                Ok = false,
                Tool = toolName,
                Summary = "解析 AgentToolbox 响应失败",
                Error = ex.Message,
            };
        }
    }
}

public sealed class ToolResult
{
    [JsonPropertyName("ok")]
    public bool Ok { get; set; }

    [JsonPropertyName("tool")]
    public string Tool { get; set; } = "";

    [JsonPropertyName("summary")]
    public string Summary { get; set; } = "";

    [JsonPropertyName("task_id")]
    public string? TaskId { get; set; }

    [JsonPropertyName("data")]
    public JsonElement Data { get; set; }

    [JsonPropertyName("error")]
    public string? Error { get; set; }
}
