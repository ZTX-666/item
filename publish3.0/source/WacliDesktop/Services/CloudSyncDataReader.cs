using System.IO;
using Microsoft.Data.Sqlite;

namespace WacliDesktop.Services;

internal sealed record CloudMessageRow(
    string MsgId,
    string ChatJid,
    string ChatName,
    string SenderName,
    string SenderJid,
    long Ts,
    string Text,
    string DisplayText,
    string MediaType,
    string LocalPath,
    string Filename,
    int Revoked,
    int DeletedForMe);

internal static class CloudSyncDataReader
{
    private static SqliteConnection OpenReadOnlyConnection(string dbPath)
    {
        var csb = new SqliteConnectionStringBuilder
        {
            DataSource = dbPath,
            Mode = SqliteOpenMode.ReadOnly,
            Cache = SqliteCacheMode.Shared,
        };
        var conn = new SqliteConnection(csb.ToString());
        conn.Open();
        return conn;
    }

    public static List<CloudMessageRow> FetchMessagesSince(long sinceTs, int limit)
    {
        var list = new List<CloudMessageRow>();
        var db = AppConfig.ResolveReadableDbPath();
        if (!File.Exists(db))
            return list;

        using var conn = OpenReadOnlyConnection(db);
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            SELECT msg_id, chat_jid,
                   COALESCE(chat_name,''), COALESCE(sender_name,''), COALESCE(sender_jid,''),
                   ts,
                   COALESCE(text,''), COALESCE(display_text,''),
                   COALESCE(media_type,''), COALESCE(local_path,''), COALESCE(filename,''),
                   COALESCE(revoked,0), COALESCE(deleted_for_me,0)
            FROM messages
            WHERE ts > $since
            ORDER BY ts ASC
            LIMIT $lim
            """;
        cmd.Parameters.AddWithValue("$since", sinceTs);
        cmd.Parameters.AddWithValue("$lim", limit);
        using var r = cmd.ExecuteReader();
        while (r.Read())
        {
            list.Add(new CloudMessageRow(
                r.GetString(0),
                r.GetString(1),
                r.GetString(2),
                r.GetString(3),
                r.GetString(4),
                r.GetInt64(5),
                r.GetString(6),
                r.GetString(7),
                r.GetString(8),
                r.GetString(9),
                r.GetString(10),
                r.GetInt32(11),
                r.GetInt32(12)));
        }
        return list;
    }

    public static List<(string MsgId, string ChatJid, string LocalPath, string MediaType)> FetchMediaPending(
        int tier,
        CloudSyncState state,
        int limit)
    {
        var list = new List<(string, string, string, string)>();
        var db = AppConfig.ResolveReadableDbPath();
        if (!File.Exists(db))
            return list;

        using var conn = OpenReadOnlyConnection(db);
        using var cmd = conn.CreateCommand();
        cmd.CommandText = """
            SELECT msg_id, chat_jid, local_path, COALESCE(media_type,'')
            FROM messages
            WHERE media_type IS NOT NULL AND TRIM(media_type) != ''
              AND local_path IS NOT NULL AND TRIM(local_path) != ''
            ORDER BY ts DESC
            LIMIT $lim
            """;
        cmd.Parameters.AddWithValue("$lim", Math.Max(limit, 500));
        using var r = cmd.ExecuteReader();
        while (r.Read())
        {
            var msgId = r.GetString(0);
            if (state.SyncedFullMediaMsgIds.Contains(msgId))
                continue;
            if (tier == 1 && state.SyncedThumbnailMsgIds.Contains(msgId))
                continue;
            list.Add((msgId, r.GetString(1), r.GetString(2), r.GetString(3)));
            if (list.Count >= limit)
                break;
        }
        return list;
    }

    public static string? ResolveMediaPath(string localPath)
    {
        if (string.IsNullOrWhiteSpace(localPath))
            return null;
        if (Path.IsPathRooted(localPath) && File.Exists(localPath))
            return localPath;
        var underStore = Path.Combine(AppConfig.StoreDir, localPath.TrimStart('/', '\\'));
        if (File.Exists(underStore))
            return underStore;
        var underRuntime = Path.Combine(AppConfig.RuntimeDir, localPath.TrimStart('/', '\\'));
        if (File.Exists(underRuntime))
            return underRuntime;
        return File.Exists(localPath) ? localPath : null;
    }

    public static List<(string MsgId, string ChatJid, string ThumbPath)> ListThumbnailUploadCandidates(
        CloudSyncState state,
        int limit)
    {
        var list = new List<(string, string, string)>();
        var dir = AppConfig.ThumbnailDir;
        if (!Directory.Exists(dir))
            return list;

        var chatByMsg = new Dictionary<string, string>(StringComparer.Ordinal);
        var db = AppConfig.ResolveReadableDbPath();
        if (File.Exists(db))
        {
            using var conn = OpenReadOnlyConnection(db);
            using var cmd = conn.CreateCommand();
            cmd.CommandText = "SELECT msg_id, chat_jid FROM messages";
            using var r = cmd.ExecuteReader();
            while (r.Read())
                chatByMsg[r.GetString(0)] = r.GetString(1);
        }

        foreach (var file in Directory.EnumerateFiles(dir).OrderByDescending(File.GetLastWriteTimeUtc))
        {
            if (list.Count >= limit)
                break;
            var name = Path.GetFileNameWithoutExtension(file);
            if (string.IsNullOrEmpty(name) || state.SyncedThumbnailMsgIds.Contains(name))
                continue;
            chatByMsg.TryGetValue(name, out var chatJid);
            list.Add((name, chatJid ?? "", file));
        }
        return list;
    }

    public static string? FindThumbnailPath(string msgId)
    {
        var dir = AppConfig.ThumbnailDir;
        if (!Directory.Exists(dir))
            return null;
        foreach (var ext in new[] { ".jpg", ".jpeg", ".png", ".webp" })
        {
            var p = Path.Combine(dir, msgId + ext);
            if (File.Exists(p))
                return p;
        }
        return Directory.GetFiles(dir, msgId + ".*").FirstOrDefault();
    }
}
