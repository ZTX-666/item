using System.IO;
using System.Net;
using System.Text;
using System.Text.Json;
using Microsoft.Data.Sqlite;

namespace WacliDesktop.Services;

/// <summary>本机 HTTP API（供 cloudflared 转发给 HiAgent）。</summary>
public sealed class HiAgentLocalApiServer : IDisposable
{
    private readonly int _port;
    private readonly Func<string?> _getApiKey;
    private HttpListener? _listener;
    private CancellationTokenSource? _cts;
    private Task? _loop;

    public HiAgentLocalApiServer(int port, Func<string?> getApiKey)
    {
        _port = port;
        _getApiKey = getApiKey;
    }

    public bool IsRunning => _listener is not null;

    public string LocalBaseUrl => $"http://127.0.0.1:{_port}";

    public void Start()
    {
        if (IsRunning) return;
        _listener = new HttpListener();
        _listener.Prefixes.Add($"http://127.0.0.1:{_port}/");
        _listener.Start();
        _cts = new CancellationTokenSource();
        _loop = Task.Run(() => LoopAsync(_cts.Token));
    }

    public void Stop()
    {
        _cts?.Cancel();
        try { _listener?.Stop(); } catch { /* ignore */ }
        _listener?.Close();
        _listener = null;
    }

    private async Task LoopAsync(CancellationToken ct)
    {
        while (!ct.IsCancellationRequested && _listener is { IsListening: true })
        {
            HttpListenerContext ctx;
            try
            {
                ctx = await _listener.GetContextAsync().WaitAsync(ct);
            }
            catch when (ct.IsCancellationRequested)
            {
                break;
            }
            catch
            {
                break;
            }

            _ = Task.Run(() => HandleAsync(ctx), ct);
        }
    }

    private async Task HandleAsync(HttpListenerContext ctx)
    {
        try
        {
            if (!CheckAuth(ctx.Request))
            {
                await WriteJson(ctx, 401, new { error = "Invalid or missing X-Api-Key" });
                return;
            }

            var path = ctx.Request.Url?.AbsolutePath.TrimEnd('/') ?? "";
            switch (path)
            {
                case "" or "/":
                    await WriteJson(ctx, 200, new
                    {
                        service = "chitong-hiagent-api",
                        health = "/health",
                        ping = "/api/ping",
                        search = "/api/messages/search?q=&limit=10",
                    });
                    break;
                case "/health":
                    await HandleHealth(ctx);
                    break;
                case "/api/ping":
                    await WriteJson(ctx, 200, new
                    {
                        message = "hello from ChitongLingxun HiAgent bridge",
                        time = DateTimeOffset.Now,
                        store = AppConfig.StoreDir,
                    });
                    break;
                case "/api/messages/search":
                    await HandleSearch(ctx);
                    break;
                case "/api/upload" when ctx.Request.HttpMethod == "POST":
                    await HandleUpload(ctx);
                    break;
                default:
                    await WriteJson(ctx, 404, new { error = "not found", path });
                    break;
            }
        }
        catch (Exception ex)
        {
            await WriteJson(ctx, 500, new { error = ex.Message });
        }
    }

    private bool CheckAuth(HttpListenerRequest req)
    {
        var expected = _getApiKey();
        if (string.IsNullOrEmpty(expected))
            return true;
        var key = req.Headers["X-Api-Key"];
        return string.Equals(key, expected, StringComparison.Ordinal);
    }

    private static async Task HandleHealth(HttpListenerContext ctx)
    {
        var db = AppConfig.ResolveReadableDbPath();
        var exists = File.Exists(db);
        object counts = new { messages = 0, chats = 0 };
        if (exists)
        {
            using var conn = new SqliteConnection($"file:{db}?mode=ro");
            conn.Open();
            var msg = conn.ExecuteScalar<long>(
                "SELECT COUNT(*) FROM messages WHERE revoked = 0 AND deleted_for_me = 0");
            var chats = conn.ExecuteScalar<long>("SELECT COUNT(*) FROM chats");
            counts = new { messages = msg, chats };
        }

        await WriteJson(ctx, 200, new
        {
            ok = true,
            time = DateTimeOffset.Now,
            wacli_db = db,
            wacli_db_exists = exists,
            counts,
        });
    }

    private static async Task HandleSearch(HttpListenerContext ctx)
    {
        var q = ctx.Request.QueryString["q"] ?? "";
        var limit = 10;
        if (int.TryParse(ctx.Request.QueryString["limit"], out var n))
            limit = Math.Clamp(n, 1, 50);

        var db = AppConfig.ResolveReadableDbPath();
        if (!File.Exists(db))
        {
            await WriteJson(ctx, 404, new { error = "wacli.db not found", path = db });
            return;
        }

        var items = HiAgentMessageQuery.Search(db, q, limit);
        await WriteJson(ctx, 200, new
        {
            query = q,
            limit,
            count = items.Count,
            db,
            items,
        });
    }

    private static async Task HandleUpload(HttpListenerContext ctx)
    {
        using var reader = new StreamReader(ctx.Request.InputStream, ctx.Request.ContentEncoding);
        var body = await reader.ReadToEndAsync();
        var logPath = Path.Combine(AppConfig.RuntimeDir, "hiagent-uploads.jsonl");
        var line = JsonSerializer.Serialize(new { time = DateTimeOffset.Now, body });
        await File.AppendAllTextAsync(logPath, line + Environment.NewLine);
        await WriteJson(ctx, 200, new { ok = true, log = logPath });
    }

    private static async Task WriteJson(HttpListenerContext ctx, int code, object payload)
    {
        var bytes = Encoding.UTF8.GetBytes(JsonSerializer.Serialize(payload));
        ctx.Response.StatusCode = code;
        ctx.Response.ContentType = "application/json; charset=utf-8";
        ctx.Response.ContentLength64 = bytes.Length;
        await ctx.Response.OutputStream.WriteAsync(bytes);
        ctx.Response.Close();
    }

    public void Dispose() => Stop();
}

internal static class HiAgentMessageQuery
{
    public static List<Dictionary<string, object?>> Search(string dbPath, string q, int limit)
    {
        var list = new List<Dictionary<string, object?>>();
        using var conn = new SqliteConnection($"file:{dbPath}?mode=ro");
        conn.Open();
        var sql = """
            SELECT m.msg_id, m.chat_jid, COALESCE(m.chat_name,'') AS chat_name,
                   COALESCE(m.sender_name,'') AS sender_name,
                   datetime(m.ts,'unixepoch','localtime') AS message_time,
                   COALESCE(NULLIF(TRIM(m.display_text),''), NULLIF(TRIM(m.text),''), '') AS text,
                   COALESCE(m.media_type,'') AS media_type
            FROM messages m
            WHERE m.revoked = 0 AND m.deleted_for_me = 0
            """;
        if (!string.IsNullOrWhiteSpace(q))
            sql += """
             AND (COALESCE(m.text,'') LIKE @q OR COALESCE(m.display_text,'') LIKE @q
                  OR COALESCE(m.sender_name,'') LIKE @q OR COALESCE(m.chat_name,'') LIKE @q)
             """;
        sql += " ORDER BY m.ts DESC LIMIT @lim";
        using var cmd = conn.CreateCommand();
        cmd.CommandText = sql;
        if (!string.IsNullOrWhiteSpace(q))
            cmd.Parameters.AddWithValue("@q", $"%{q.Trim()}%");
        cmd.Parameters.AddWithValue("@lim", limit);
        using var r = cmd.ExecuteReader();
        while (r.Read())
        {
            list.Add(new Dictionary<string, object?>
            {
                ["msg_id"] = r.GetString(0),
                ["chat_jid"] = r.GetString(1),
                ["chat_name"] = r.GetString(2),
                ["sender_name"] = r.GetString(3),
                ["message_time"] = r.GetString(4),
                ["text"] = r.GetString(5),
                ["media_type"] = r.GetString(6),
            });
        }
        return list;
    }
}

internal static class SqliteScalarExt
{
    public static T ExecuteScalar<T>(this SqliteConnection conn, string sql)
    {
        using var cmd = conn.CreateCommand();
        cmd.CommandText = sql;
        var o = cmd.ExecuteScalar();
        return (T)Convert.ChangeType(o ?? default(T)!, typeof(T));
    }
}
