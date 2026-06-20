using System.Data;
using System.IO;
using WacliDesktop.Models;

namespace WacliDesktop.Services;

public static class MessageRowMapper
{
    public static List<MessageRowViewModel> FromDataTable(DataTable table, ThumbnailService thumbnails)
    {
        var rows = new List<MessageRowViewModel>();
        foreach (DataRow dr in table.Rows)
            rows.Add(FromDataRow(dr, thumbnails));
        return rows;
    }

    public static MessageRowViewModel FromDataRow(DataRow dr, ThumbnailService thumbnails)
    {
        var localPath = Pick(dr, "attachment_local_path", "local_path");
        var mediaType = Pick(dr, "attachment_type", "media_type");
        var mime = Pick(dr, "attachment_mime", "mime_type");
        var msgId = Pick(dr, "msg_id");
        var status = Pick(dr, "attachment_status");
        if (string.IsNullOrEmpty(status))
        {
            status = string.IsNullOrEmpty(localPath) ? "无附件" :
                File.Exists(localPath) ? "已下载" : "未下载";
        }

        return new MessageRowViewModel
        {
            MessageDate = PickDate(dr),
            WhatsappId = Pick(dr, "whatsapp_id", "sender_jid"),
            SenderName = Pick(dr, "sender_name"),
            ChatJid = Pick(dr, "chat_jid"),
            ChatName = Pick(dr, "chat_name"),
            GroupDisplay = ResolveGroupDisplay(Pick(dr, "chat_jid"), Pick(dr, "chat_name")),
            Direction = Pick(dr, "direction"),
            MessageText = Pick(dr, "message_text", "text", "display_text"),
            AttachmentType = mediaType,
            AttachmentFilename = Pick(dr, "attachment_filename", "filename"),
            AttachmentMime = mime,
            AttachmentCaption = Pick(dr, "attachment_caption", "media_caption"),
            AttachmentLocalPath = localPath,
            AttachmentStatus = status,
            MsgId = msgId,
            Thumbnail = thumbnails.GetThumbnail(
                localPath, mediaType, mime, msgId,
                Pick(dr, "attachment_filename", "filename")),
        };
    }

    private static string PickDate(DataRow dr)
    {
        var formatted = Pick(dr, "message_date");
        if (!string.IsNullOrEmpty(formatted))
            return formatted;
        var ts = Pick(dr, "ts", "ts_unix");
        if (long.TryParse(ts, out var unix))
            return DateTimeOffset.FromUnixTimeSeconds(unix).LocalDateTime.ToString("yyyy-MM-dd HH:mm:ss");
        return "";
    }

    private static string Pick(DataRow dr, params string[] columns)
    {
        foreach (var col in columns)
        {
            if (!dr.Table.Columns.Contains(col)) continue;
            var value = dr[col]?.ToString()?.Trim();
            if (!string.IsNullOrEmpty(value))
                return value;
        }
        return "";
    }

    private static string ResolveGroupDisplay(string chatJid, string chatName)
    {
        if (string.IsNullOrWhiteSpace(chatJid))
            return "—";
        if (chatJid.EndsWith("@g.us", StringComparison.OrdinalIgnoreCase))
            return string.IsNullOrWhiteSpace(chatName) ? chatJid : chatName;
        return "私聊";
    }
}
