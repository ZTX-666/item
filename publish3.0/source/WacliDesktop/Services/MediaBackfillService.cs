using System.IO;
using Microsoft.Data.Sqlite;

namespace WacliDesktop.Services;

public sealed class MediaBackfillService : IDisposable
{
    private readonly WacliService _wacli;
    private readonly ThumbnailService _thumbnails;
    private CancellationTokenSource? _cts;
    private Task? _worker;

    public event Action<int, int, string>? ProgressUpdated;
    public event Action? DownloadsCompleted;

    public bool IsRunning => _worker is { IsCompleted: false };

    public MediaBackfillService(WacliService wacli, ThumbnailService thumbnails)
    {
        _wacli = wacli;
        _thumbnails = thumbnails;
    }

    public void Start()
    {
        if (IsRunning) return;
        _cts = new CancellationTokenSource();
        _worker = Task.Run(() => RunLoopAsync(_cts.Token));
    }

    public void Stop()
    {
        _cts?.Cancel();
    }

    public (int Pending, int Downloaded) GetCounts()
    {
        var db = AppConfig.ResolveReadableDbPath();
        if (!File.Exists(db))
            return (0, 0);
        using var conn = new SqliteConnection($"Data Source={db};Mode=ReadOnly");
        conn.Open();
        return (Scalar(conn, PendingCountSql), Scalar(conn, DownloadedCountSql));
    }

    private async Task RunLoopAsync(CancellationToken ct)
    {
        while (!ct.IsCancellationRequested)
        {
            try
            {
                if (_wacli.SyncRunning || _wacli.AuthRunning)
                {
                    await Task.Delay(4000, ct);
                    continue;
                }

                var pending = QueryPending(8);
                if (pending.Count == 0)
                {
                    var counts = GetCounts();
                    ProgressUpdated?.Invoke(counts.Downloaded, counts.Downloaded + counts.Pending, "");
                    await Task.Delay(12000, ct);
                    continue;
                }

                var (done, remain) = GetCounts();
                foreach (var item in pending)
                {
                    if (ct.IsCancellationRequested || _wacli.SyncRunning || _wacli.AuthRunning) break;

                    using var storeMutex = AppConfig.AcquireStoreMutex(3_000);
                    if (storeMutex is null)
                        break;

                    ProgressUpdated?.Invoke(done, done + remain, item.MsgId);
                    _wacli.Run(
                        ["media", "download", "--chat", item.ChatJid, "--id", item.MsgId],
                        timeoutMs: 300_000);
                    _thumbnails.Invalidate(item.MsgId);
                    done++;
                    remain = Math.Max(0, remain - 1);
                    ProgressUpdated?.Invoke(done, done + remain, item.MsgId);
                    await Task.Delay(800, ct);
                }

                DownloadsCompleted?.Invoke();
            }
            catch (OperationCanceledException)
            {
                break;
            }
            catch
            {
                await Task.Delay(5000, ct);
            }
        }
    }

    public static IReadOnlyList<(string ChatJid, string MsgId)> QueryPending(int limit)
    {
        var db = AppConfig.ResolveReadableDbPath();
        if (!File.Exists(db))
            return Array.Empty<(string, string)>();
        using var conn = new SqliteConnection($"Data Source={db};Mode=ReadOnly");
        conn.Open();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            SELECT chat_jid, msg_id FROM messages
            WHERE media_type IS NOT NULL AND TRIM(media_type) != ''
              AND (local_path IS NULL OR TRIM(local_path) = '')
            ORDER BY ts DESC
            LIMIT $limit
            """;
        cmd.Parameters.AddWithValue("$limit", limit);
        var list = new List<(string, string)>();
        using var reader = cmd.ExecuteReader();
        while (reader.Read())
            list.Add((reader.GetString(0), reader.GetString(1)));
        return list;
    }

    private static int Scalar(SqliteConnection conn, string sql)
    {
        using var cmd = conn.CreateCommand();
        cmd.CommandText = sql;
        return Convert.ToInt32(cmd.ExecuteScalar());
    }

    private const string PendingCountSql = """
        SELECT COUNT(*) FROM messages
        WHERE media_type IS NOT NULL AND TRIM(media_type) != ''
          AND (local_path IS NULL OR TRIM(local_path) = '')
        """;

    private const string DownloadedCountSql = """
        SELECT COUNT(*) FROM messages
        WHERE media_type IS NOT NULL AND TRIM(media_type) != ''
          AND local_path IS NOT NULL AND TRIM(local_path) != ''
        """;

    public void Dispose()
    {
        Stop();
        _cts?.Dispose();
    }
}
