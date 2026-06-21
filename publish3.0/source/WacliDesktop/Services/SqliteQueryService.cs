using System.Data;
using System.IO;
using WacliDesktop.Models;
using System.Text.RegularExpressions;
using Microsoft.Data.Sqlite;

namespace WacliDesktop.Services;

public sealed class SqliteQueryService
{
    /// <summary>Standard message view: date, WhatsApp sender ID, attachment metadata.</summary>
    public const string MessagesDetailSql = """
        SELECT
            datetime(m.ts, 'unixepoch', 'localtime') AS message_date,
            m.sender_jid AS whatsapp_id,
            m.sender_name,
            m.chat_jid,
            m.chat_name,
            CASE WHEN m.from_me = 1 THEN '发出' ELSE '收到' END AS direction,
            COALESCE(NULLIF(TRIM(m.text), ''), NULLIF(TRIM(m.display_text), ''), '') AS message_text,
            COALESCE(NULLIF(TRIM(m.media_type), ''), '') AS attachment_type,
            COALESCE(NULLIF(TRIM(m.filename), ''), '') AS attachment_filename,
            COALESCE(NULLIF(TRIM(m.mime_type), ''), '') AS attachment_mime,
            COALESCE(NULLIF(TRIM(m.media_caption), ''), '') AS attachment_caption,
            COALESCE(NULLIF(TRIM(m.local_path), ''), '') AS attachment_local_path,
            CASE
                WHEN m.local_path IS NOT NULL AND TRIM(m.local_path) != '' THEN '已下载'
                WHEN m.media_type IS NOT NULL AND TRIM(m.media_type) != '' THEN '未下载'
                ELSE '无附件'
            END AS attachment_status,
            m.msg_id,
            m.ts AS ts_unix
        FROM messages m
        ORDER BY m.ts DESC
        """;

    public const string MessagesWithAttachmentSql = """
        SELECT
            datetime(m.ts, 'unixepoch', 'localtime') AS message_date,
            m.sender_jid AS whatsapp_id,
            m.sender_name,
            m.chat_jid,
            m.chat_name,
            COALESCE(NULLIF(TRIM(m.text), ''), NULLIF(TRIM(m.display_text), ''), '') AS message_text,
            m.media_type AS attachment_type,
            COALESCE(m.filename, '') AS attachment_filename,
            COALESCE(m.mime_type, '') AS attachment_mime,
            COALESCE(m.media_caption, '') AS attachment_caption,
            COALESCE(m.local_path, '') AS attachment_local_path,
            CASE
                WHEN m.local_path IS NOT NULL AND TRIM(m.local_path) != '' THEN '已下载'
                ELSE '未下载'
            END AS attachment_status,
            m.msg_id
        FROM messages m
        WHERE m.media_type IS NOT NULL AND TRIM(m.media_type) != ''
        ORDER BY m.ts DESC
        """;

    private static readonly Regex Forbidden = new(
        @"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|ATTACH|DETACH|VACUUM|REINDEX)\b",
        RegexOptions.IgnoreCase | RegexOptions.Compiled);

    public IReadOnlyList<string> ListTables()
    {
        using var conn = OpenReadOnly();
        conn.Open();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name";
        var list = new List<string>();
        using var reader = cmd.ExecuteReader();
        while (reader.Read())
            list.Add(reader.GetString(0));
        return list;
    }

    public IReadOnlyList<(string Name, string Type, bool Pk)> GetSchema(string table)
    {
        if (!Regex.IsMatch(table, @"^[A-Za-z0-9_]+$"))
            throw new ArgumentException("Invalid table name");

        using var conn = OpenReadOnly();
        conn.Open();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = $"PRAGMA table_info({table})";
        var list = new List<(string, string, bool)>();
        using var reader = cmd.ExecuteReader();
        while (reader.Read())
        {
            list.Add((reader.GetString(1), reader.GetString(2), reader.GetInt32(5) == 1));
        }
        return list;
    }

    public DataTable RunSelect(string sql, int limit = 100)
    {
        var text = sql.Trim().TrimEnd(';');
        if (!text.StartsWith("SELECT", StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("Only SELECT statements are allowed");
        if (Forbidden.IsMatch(text))
            throw new InvalidOperationException("Statement contains forbidden keywords");
        if (text.Contains(';'))
            throw new InvalidOperationException("Multiple statements are not allowed");

        limit = Math.Clamp(limit, 1, 500);
        var wrapped = $"SELECT * FROM ({text}) LIMIT {limit}";

        using var conn = OpenReadOnly();
        conn.Open();
        using var cmd = conn.CreateCommand();
        cmd.CommandText = wrapped;
        using var reader = cmd.ExecuteReader();
        var table = new DataTable();
        table.Load(reader);
        return table;
    }

    public DataTable QueryMessagesDetail(int limit = 100) =>
        RunSelect(MessagesDetailSql, limit);

    public static IReadOnlyDictionary<string, string> Presets { get; } =
        new Dictionary<string, string>
        {
            ["message_detail"] = MessagesDetailSql,
            ["messages_with_attachment"] = MessagesWithAttachmentSql,
            ["chat_summary"] = """
                SELECT kind, name, jid, last_message_ts, unread_count
                FROM chats ORDER BY last_message_ts DESC LIMIT 50
                """.Trim(),
            ["message_count"] = "SELECT COUNT(*) AS total FROM messages",
            ["attachment_count"] = """
                SELECT COUNT(*) AS total FROM messages
                WHERE media_type IS NOT NULL AND TRIM(media_type) != ''
                """.Trim(),
            ["contact_count"] = "SELECT COUNT(*) AS total FROM contacts",
        };

    public static string FormatAttachmentDetail(MessageRowViewModel? row)
    {
        if (row is null)
            return "选中一行消息以查看附件详情。";

        var lines = new List<string>
        {
            $"日期：{(string.IsNullOrEmpty(row.MessageDate) ? "—" : row.MessageDate)}",
            $"发送人 WhatsApp ID：{(string.IsNullOrEmpty(row.WhatsappId) ? "—" : row.WhatsappId)}",
            $"发送人显示名：{(string.IsNullOrEmpty(row.SenderName) ? "—" : row.SenderName)}",
            $"群组：{(string.IsNullOrEmpty(row.GroupDisplay) ? "—" : row.GroupDisplay)}",
            $"消息内容：{(string.IsNullOrEmpty(row.MessageText) ? "—" : row.MessageText)}",
            "",
            $"附件状态：{row.AttachmentStatus}",
            $"附件类型：{(string.IsNullOrEmpty(row.AttachmentType) ? "无" : row.AttachmentType)}",
            $"文件名：{(string.IsNullOrEmpty(row.AttachmentFilename) ? "—" : row.AttachmentFilename)}",
            $"MIME：{(string.IsNullOrEmpty(row.AttachmentMime) ? "—" : row.AttachmentMime)}",
            $"说明/标题：{(string.IsNullOrEmpty(row.AttachmentCaption) ? "—" : row.AttachmentCaption)}",
            $"本地路径：{(string.IsNullOrEmpty(row.AttachmentLocalPath) ? "—" : row.AttachmentLocalPath)}",
            "",
            $"msg_id：{row.MsgId}",
            $"chat_jid：{row.ChatJid}",
        };

        if (row.AttachmentStatus == "未下载" && !string.IsNullOrEmpty(row.AttachmentType))
        {
            lines.Add("");
            lines.Add("后台正在自动下载附件；sync 已启用 --download-media。");
        }

        return string.Join(Environment.NewLine, lines);
    }

    private static SqliteConnection OpenReadOnly()
    {
        var db = AppConfig.ResolveReadableDbPath();
        if (!File.Exists(db))
            throw new FileNotFoundException("Database not found", db);
        return new SqliteConnection($"Data Source={db};Mode=ReadOnly");
    }
}
