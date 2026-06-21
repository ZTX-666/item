using System.IO;

namespace WacliDesktop.Models;

public sealed class MessageRowViewModel
{
    public string MessageDate { get; init; } = "";
    public string WhatsappId { get; init; } = "";
    public string SenderName { get; init; } = "";
    public string ChatJid { get; init; } = "";
    public string ChatName { get; init; } = "";
    public string GroupDisplay { get; init; } = "";
    public string Direction { get; init; } = "";
    public string MessageText { get; init; } = "";
    public string AttachmentType { get; init; } = "";
    public string AttachmentFilename { get; init; } = "";
    public string AttachmentMime { get; init; } = "";
    public string AttachmentCaption { get; init; } = "";
    public string AttachmentLocalPath { get; init; } = "";
    public string AttachmentStatus { get; init; } = "";
    public string MsgId { get; init; } = "";
    public System.Windows.Media.ImageSource? Thumbnail { get; init; }
    public bool HasLocalFile =>
        !string.IsNullOrWhiteSpace(AttachmentLocalPath) && File.Exists(AttachmentLocalPath);

    public bool CanOpenFile => HasLocalFile;
}
