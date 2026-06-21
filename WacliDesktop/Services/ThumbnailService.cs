using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.IO;
using System.Windows.Media.Imaging;

namespace WacliDesktop.Services;

public sealed class ThumbnailService
{
    private const int DefaultSize = 72;
    private readonly FileIconService _fileIcons;
    private static readonly HashSet<string> ImageExtensions = new(StringComparer.OrdinalIgnoreCase)
    {
        ".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".heic"
    };

    public ThumbnailService(FileIconService fileIcons)
    {
        _fileIcons = fileIcons;
    }

    public BitmapSource? GetThumbnail(
        string? localPath,
        string? mediaType,
        string? mimeType,
        string? msgId,
        string? filename = null,
        int size = DefaultSize)
    {
        if (!string.IsNullOrWhiteSpace(localPath) && File.Exists(localPath) && IsImageFile(localPath, mediaType, mimeType))
        {
            if (!string.IsNullOrWhiteSpace(msgId))
            {
                var cachePath = Path.Combine(AppConfig.ThumbnailDir, $"{SanitizeFileName(msgId)}.jpg");
                if (File.Exists(cachePath))
                    return LoadBitmapSource(cachePath, size);
                try
                {
                    SaveImageThumbnail(localPath, cachePath, size);
                    return LoadBitmapSource(cachePath, size);
                }
                catch
                {
                    /* fall through to icon */
                }
            }
            else
            {
                try
                {
                    return LoadBitmapSource(localPath, size);
                }
                catch
                {
                    /* fall through */
                }
            }
        }

        if (!string.IsNullOrWhiteSpace(mediaType) || !string.IsNullOrWhiteSpace(mimeType) ||
            !string.IsNullOrWhiteSpace(filename))
        {
            return _fileIcons.GetIcon(mediaType, mimeType, filename, size);
        }

        return _fileIcons.GetIcon(null, null, null, size);
    }

    public void Invalidate(string msgId)
    {
        var cachePath = Path.Combine(AppConfig.ThumbnailDir, $"{SanitizeFileName(msgId)}.jpg");
        if (File.Exists(cachePath))
        {
            try { File.Delete(cachePath); } catch { /* ignore */ }
        }
    }

    private static bool IsImageFile(string path, string? mediaType, string? mimeType)
    {
        if (mediaType is "image" or "sticker")
            return true;
        if (!string.IsNullOrWhiteSpace(mimeType) && mimeType.StartsWith("image/", StringComparison.OrdinalIgnoreCase))
            return true;
        return ImageExtensions.Contains(Path.GetExtension(path));
    }

    private static void SaveImageThumbnail(string sourcePath, string cachePath, int size)
    {
        using var image = Image.FromFile(sourcePath);
        var scale = Math.Min((double)size / image.Width, (double)size / image.Height);
        var w = Math.Max(1, (int)(image.Width * scale));
        var h = Math.Max(1, (int)(image.Height * scale));
        using var thumb = new Bitmap(w, h);
        using (var g = Graphics.FromImage(thumb))
        {
            g.InterpolationMode = InterpolationMode.HighQualityBicubic;
            g.DrawImage(image, 0, 0, w, h);
        }
        thumb.Save(cachePath, ImageFormat.Jpeg);
    }

    private static BitmapSource LoadBitmapSource(string path, int decodeWidth)
    {
        var bmp = new BitmapImage();
        bmp.BeginInit();
        bmp.UriSource = new Uri(path, UriKind.Absolute);
        bmp.DecodePixelWidth = decodeWidth;
        bmp.CacheOption = BitmapCacheOption.OnLoad;
        bmp.EndInit();
        bmp.Freeze();
        return bmp;
    }

    private static string SanitizeFileName(string msgId) =>
        string.Concat(msgId.Select(ch => Path.GetInvalidFileNameChars().Contains(ch) ? '_' : ch));
}
