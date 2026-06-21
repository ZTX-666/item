using System.Text.Json;
using WacliDesktop.ApiHost.Helpers;
using WacliDesktop.ApiHost.Services;
using WacliDesktop.Services;

var builder = WebApplication.CreateBuilder(args);

var apiSection = builder.Configuration.GetSection("ApiHost");
var listenUrls = apiSection["Urls"] ?? "http://127.0.0.1:8790";
builder.WebHost.UseUrls(listenUrls);

var allowedOrigins = apiSection.GetSection("AllowedOrigins").Get<string[]>()
    ?? ["http://127.0.0.1:5173", "http://localhost:5173"];

builder.Services.AddSingleton<AuthEventBroadcaster>();
builder.Services.AddSingleton<WacliBackendHost>();
builder.Services.AddCors(options =>
{
    options.AddDefaultPolicy(policy =>
    {
        policy.WithOrigins(allowedOrigins)
            .AllowAnyHeader()
            .AllowAnyMethod();
    });
});

var app = builder.Build();
app.UseCors();

var backend = app.Services.GetRequiredService<WacliBackendHost>();
var events = app.Services.GetRequiredService<AuthEventBroadcaster>();

app.Lifetime.ApplicationStarted.Register(() => backend.EnsureStarted());
app.Lifetime.ApplicationStopping.Register(() => backend.Dispose());

app.MapGet("/", () => Results.Json(new
{
    service = "wacli-desktop-api",
    version = "1.0.0-preview",
    docs = "/api/app/info",
    status = "/api/app/status",
    authEvents = "/api/auth/events",
    note = "Vue 前端请连接此 Local API，不要直接访问 SQLite 或 wacli.exe",
}));

app.MapGet("/api/app/info", () => Results.Json(new
{
    product = "赤瞳灵讯 WacliDesktop Local API",
    baseUrl = listenUrls,
    appRoot = AppConfig.AppRoot,
    runtimeDir = AppConfig.RuntimeDir,
    wacliExe = AppConfig.WacliExe,
    wacliExeExists = File.Exists(AppConfig.WacliExe),
    endpoints = new[]
    {
        "GET /api/app/status",
        "GET /api/app/info",
        "POST /api/auth/qr/start",
        "POST /api/auth/phone/start",
        "POST /api/auth/stop",
        "POST /api/auth/logout",
        "GET /api/auth/events",
        "POST /api/sync/start",
        "POST /api/sync/stop",
        "GET /api/sync/status",
        "GET /api/db/profile",
        "POST /api/db/switch-phone",
        "POST /api/db/default-root",
        "POST /api/db/import",
        "POST /api/db/export",
        "GET /api/db/tables",
        "GET /api/db/schema",
        "POST /api/db/query",
        "GET /api/db/presets",
        "GET /api/db/messages",
        "GET /api/media/progress",
        "GET /api/toolbox/health",
        "POST /api/toolbox/call",
        "GET /api/cloud/config",
        "POST /api/cloud/config",
        "POST /api/cloud/test",
        "POST /api/cloud/run",
    },
}));

app.MapGet("/api/app/status", () => Results.Json(backend.GetStatus()));

app.MapPost("/api/auth/qr/start", () =>
{
    try
    {
        backend.Wacli.StartQrAuth();
        return Results.Json(new { ok = true, message = "QR auth started" });
    }
    catch (Exception ex)
    {
        return Results.Json(new { ok = false, error = ex.Message }, statusCode: 400);
    }
});

app.MapPost("/api/auth/phone/start", (PhoneStartRequest? req) =>
{
    if (req is null || string.IsNullOrWhiteSpace(req.Phone))
        return Results.Json(new { ok = false, error = "phone is required" }, statusCode: 400);

    try
    {
        AppConfig.SwitchToPhone(req.Phone, out var switchMessage);
        backend.Wacli.StartPhoneAuth(req.Phone);
        return Results.Json(new { ok = true, message = switchMessage });
    }
    catch (Exception ex)
    {
        return Results.Json(new { ok = false, error = ex.Message }, statusCode: 400);
    }
});

app.MapPost("/api/auth/stop", () =>
{
    backend.Wacli.StopAuth();
    return Results.Json(new { ok = true });
});

app.MapPost("/api/auth/logout", () =>
{
    var result = backend.Wacli.Logout();
    return Results.Json(new
    {
        ok = result.Ok,
        code = result.Code,
        stdout = result.Stdout,
        stderr = result.Stderr,
    });
});

app.MapGet("/api/auth/events", async (HttpContext ctx, CancellationToken ct) =>
{
    ctx.Response.Headers.CacheControl = "no-cache";
    ctx.Response.Headers.Connection = "keep-alive";
    ctx.Response.ContentType = "text/event-stream";

    var reader = events.Subscribe(out var id);
    try
    {
        await ctx.Response.WriteAsync(": connected\n\n", ct);
        await ctx.Response.Body.FlushAsync(ct);

        await foreach (var evt in reader.ReadAllAsync(ct))
        {
            await ctx.Response.WriteAsync(AuthEventBroadcaster.FormatSse(evt), ct);
            await ctx.Response.Body.FlushAsync(ct);
        }
    }
    finally
    {
        events.Unsubscribe(id);
    }
});

app.MapPost("/api/sync/start", (SyncStartRequest? req) =>
{
    backend.Wacli.StartSync(req?.InterruptAuth ?? true);
    return Results.Json(new { ok = true, running = backend.Wacli.SyncRunning });
});

app.MapPost("/api/sync/stop", () =>
{
    backend.Wacli.StopSync();
    return Results.Json(new { ok = true, running = backend.Wacli.SyncRunning });
});

app.MapGet("/api/sync/status", () => Results.Json(new
{
    running = backend.Wacli.SyncRunning,
    storeDir = AppConfig.StoreDir,
    status = backend.GetStatus().StatusDetail,
}));

app.MapGet("/api/db/profile", () => Results.Json(backend.GetDbProfile()));

app.MapPost("/api/db/switch-phone", (SwitchPhoneRequest? req) =>
{
    var ok = AppConfig.SwitchToPhone(req?.Phone, out var message);
    return Results.Json(new { ok, message });
});

app.MapPost("/api/db/default-root", (PathRequest? req) =>
{
    if (req is null || string.IsNullOrWhiteSpace(req.Path))
        return Results.Json(new { ok = false, error = "path is required" }, statusCode: 400);

    var ok = AppConfig.SetDefaultDatabaseRoot(req.Path, out var message);
    return Results.Json(new { ok, message, profile = backend.GetDbProfile() });
});

app.MapPost("/api/db/import", (PathRequest? req) =>
{
    if (req is null || string.IsNullOrWhiteSpace(req.Path))
        return Results.Json(new { ok = false, error = "path is required" }, statusCode: 400);

    var ok = AppConfig.ImportDatabase(req.Path, out var message);
    return Results.Json(new { ok, message, profile = backend.GetDbProfile() });
});

app.MapPost("/api/db/export", (PathRequest? req) =>
{
    if (req is null || string.IsNullOrWhiteSpace(req.Path))
        return Results.Json(new { ok = false, error = "path is required" }, statusCode: 400);

    var ok = AppConfig.ExportDatabase(req.Path, out var message);
    return Results.Json(new { ok, message });
});

app.MapGet("/api/db/tables", () =>
{
    try
    {
        return Results.Json(new { ok = true, tables = backend.Sqlite.ListTables() });
    }
    catch (Exception ex)
    {
        return Results.Json(new { ok = false, error = ex.Message }, statusCode: 400);
    }
});

app.MapGet("/api/db/schema", (string? table) =>
{
    if (string.IsNullOrWhiteSpace(table))
        return Results.Json(new { ok = false, error = "table is required" }, statusCode: 400);

    try
    {
        var schema = backend.Sqlite.GetSchema(table)
            .Select(c => new { name = c.Name, type = c.Type, primaryKey = c.Pk })
            .ToList();
        return Results.Json(new { ok = true, table, schema });
    }
    catch (Exception ex)
    {
        return Results.Json(new { ok = false, error = ex.Message }, statusCode: 400);
    }
});

app.MapPost("/api/db/query", (DbQueryRequest? req) =>
{
    if (req is null || string.IsNullOrWhiteSpace(req.Sql))
        return Results.Json(new { ok = false, error = "sql is required" }, statusCode: 400);

    try
    {
        var table = backend.Sqlite.RunSelect(req.Sql, req.Limit ?? 100);
        return Results.Json(new { ok = true, data = ApiJsonHelper.DataTableToPayload(table) });
    }
    catch (Exception ex)
    {
        return Results.Json(new { ok = false, error = ex.Message }, statusCode: 400);
    }
});

app.MapGet("/api/db/presets", () => Results.Json(new
{
    ok = true,
    presets = SqliteQueryService.Presets.Keys.ToList(),
}));

app.MapGet("/api/db/messages", (string? preset, int? limit) =>
{
    try
    {
        var key = string.IsNullOrWhiteSpace(preset) ? "message_detail" : preset;
        if (!SqliteQueryService.Presets.TryGetValue(key, out var sql))
            return Results.Json(new { ok = false, error = $"unknown preset: {key}" }, statusCode: 400);

        var table = backend.Sqlite.RunSelect(sql, limit ?? 100);
        return Results.Json(new { ok = true, preset = key, data = ApiJsonHelper.DataTableToPayload(table) });
    }
    catch (Exception ex)
    {
        return Results.Json(new { ok = false, error = ex.Message }, statusCode: 400);
    }
});

app.MapGet("/api/media/progress", () =>
{
    var status = backend.GetStatus();
    return Results.Json(new
    {
        ok = true,
        downloaded = status.MediaDownloaded,
        pending = status.MediaPending,
        text = status.MediaProgressText,
    });
});

app.MapGet("/api/toolbox/health", async () =>
{
    var ok = await backend.Toolbox.HealthCheckAsync();
    return Results.Json(new { ok, baseUrl = "http://127.0.0.1:8899" });
});

app.MapPost("/api/toolbox/call", async (ToolboxCallRequest? req) =>
{
    if (req is null || string.IsNullOrWhiteSpace(req.Tool))
        return Results.Json(new { ok = false, error = "tool is required" }, statusCode: 400);

    var args = req.Arguments ?? new Dictionary<string, object?>();
    var result = await backend.Toolbox.CallToolAsync(req.Tool, args);
    return Results.Json(result);
});

app.MapGet("/api/cloud/config", () =>
{
    var cfg = CloudSyncConfig.Load();
    return Results.Json(new
    {
        ok = true,
        syncTier = cfg.SyncTier,
        tierLabel = CloudSyncConfig.TierLabel(cfg.SyncTier),
        apiBaseUrl = cfg.ApiBaseUrl,
        ownerId = cfg.OwnerId,
        hasSyncToken = !string.IsNullOrWhiteSpace(cfg.SyncToken),
        autoSyncEnabled = cfg.AutoSyncEnabled,
        autoSyncIntervalMinutes = cfg.AutoSyncIntervalMinutes,
        messageBatchSize = cfg.MessageBatchSize,
        maxRetryCount = cfg.MaxRetryCount,
        maxMediaFileBytes = cfg.MaxMediaFileBytes,
        maxThumbnailBytes = cfg.MaxThumbnailBytes,
        lastSuccessAt = cfg.LastSuccessAt,
        lastError = cfg.LastError,
    });
});

app.MapPost("/api/cloud/config", (CloudConfigUpdateRequest? req) =>
{
    if (req is null)
        return Results.Json(new { ok = false, error = "body is required" }, statusCode: 400);

    var cfg = CloudSyncConfig.Load();
    if (req.SyncTier is not null) cfg.SyncTier = req.SyncTier.Value;
    if (req.ApiBaseUrl is not null) cfg.ApiBaseUrl = req.ApiBaseUrl;
    if (req.OwnerId is not null) cfg.OwnerId = req.OwnerId;
    if (req.SyncToken is not null) cfg.SyncToken = req.SyncToken;
    if (req.AutoSyncEnabled is not null) cfg.AutoSyncEnabled = req.AutoSyncEnabled.Value;
    if (req.AutoSyncIntervalMinutes is not null) cfg.AutoSyncIntervalMinutes = req.AutoSyncIntervalMinutes.Value;
    if (req.MessageBatchSize is not null) cfg.MessageBatchSize = req.MessageBatchSize.Value;
    cfg.Save();
    CloudSyncService.Instance.Reload();
    return Results.Json(new { ok = true });
});

app.MapPost("/api/cloud/test", async () =>
{
    var logs = new List<string>();
    var ok = await CloudSyncService.Instance.TestConnectionAsync(new Progress<string>(logs.Add));
    return Results.Json(new { ok, logs });
});

app.MapPost("/api/cloud/run", async (HttpContext ctx) =>
{
    var logs = new List<string>();
    try
    {
        await CloudSyncService.Instance.RunSyncAsync(new Progress<string>(logs.Add), ctx.RequestAborted);
        return Results.Json(new { ok = true, logs });
    }
    catch (Exception ex)
    {
        return Results.Json(new { ok = false, error = ex.Message, logs }, statusCode: 400);
    }
});

app.MapPost("/api/auth/qr/png", (QrPayloadRequest? req) =>
{
    if (req is null || string.IsNullOrWhiteSpace(req.Payload))
        return Results.Json(new { ok = false, error = "payload is required" }, statusCode: 400);

    try
    {
        var pngBase64 = QrCodeHelper.ToBase64Png(req.Payload);
        return Results.Json(new { ok = true, payload = req.Payload, pngBase64 });
    }
    catch (Exception ex)
    {
        return Results.Json(new { ok = false, error = ex.Message }, statusCode: 400);
    }
});

Console.WriteLine($"[WacliDesktop.ApiHost] Listening on {listenUrls}");
Console.WriteLine($"[WacliDesktop.ApiHost] AppRoot = {AppConfig.AppRoot}");
Console.WriteLine($"[WacliDesktop.ApiHost] WacliExe = {AppConfig.WacliExe} (exists={File.Exists(AppConfig.WacliExe)})");

app.Run();

internal sealed record PhoneStartRequest(string Phone);
internal sealed record SyncStartRequest(bool? InterruptAuth);
internal sealed record SwitchPhoneRequest(string? Phone);
internal sealed record PathRequest(string Path);
internal sealed record DbQueryRequest(string Sql, int? Limit);
internal sealed record ToolboxCallRequest(string Tool, Dictionary<string, object?>? Arguments);
internal sealed record QrPayloadRequest(string Payload);
internal sealed record CloudConfigUpdateRequest(
    int? SyncTier,
    string? ApiBaseUrl,
    string? OwnerId,
    string? SyncToken,
    bool? AutoSyncEnabled,
    int? AutoSyncIntervalMinutes,
    int? MessageBatchSize);
