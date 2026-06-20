using System.IO;
using System.Windows;
using System.Windows.Media;
using System.Windows.Media.Imaging;

namespace WacliDesktop.Services;

public sealed class FileIconService
{
    private readonly Dictionary<string, BitmapSource> _cache = new(StringComparer.OrdinalIgnoreCase);
    private readonly string? _iconDir;
    private static readonly BitmapSource FallbackIcon = CreateFallbackIcon();

    public FileIconService()
    {
        var baseDir = Path.Combine(AppContext.BaseDirectory, "Assets", "FileIcons");
        _iconDir = Directory.Exists(baseDir) ? baseDir : null;
    }

    public BitmapSource GetIcon(string? mediaType, string? mimeType, string? filename, int size = 72)
    {
        var key = ResolveIconKey(mediaType, mimeType, filename);
        var cacheKey = $"{key}:{size}";
        if (_cache.TryGetValue(cacheKey, out var cached))
            return cached;

        var bmp = LoadScaledFromPack($"Assets/FileIcons/{key}.png", size)
                  ?? LoadScaledFromPack("Assets/FileIcons/generic.png", size)
                  ?? (_iconDir is not null ? LoadScaledFromFile(Path.Combine(_iconDir, $"{key}.png"), size) : null)
                  ?? (_iconDir is not null ? LoadScaledFromFile(Path.Combine(_iconDir, "generic.png"), size) : null)
                  ?? FallbackIcon;

        _cache[cacheKey] = bmp;
        return bmp;
    }

    private static string ResolveIconKey(string? mediaType, string? mimeType, string? filename)
    {
        var ext = Path.GetExtension(filename ?? "").TrimStart('.').ToLowerInvariant();
        if (!string.IsNullOrEmpty(ext))
        {
            if (ext is "doc" or "docx" or "wps" or "rtf" or "odt" or "txt")
                return "doc";
            if (ext is "pdf")
                return "pdf";
            if (ext is "xls" or "xlsx" or "csv" or "et")
                return "spreadsheet";
            if (ext is "ppt" or "pptx" or "dps")
                return "presentation";
            if (ext is "jpg" or "jpeg" or "png" or "gif" or "webp" or "bmp" or "heic")
                return "image";
            if (ext is "mp4" or "mov" or "avi" or "mkv" or "webm")
                return "video";
            if (ext is "mp3" or "wav" or "ogg" or "opus" or "m4a" or "aac")
                return "audio";
            if (ext is "exe" or "msi" or "bat" or "cmd" or "com")
                return "exe";
            if (ext is "zip" or "rar" or "7z" or "tar" or "gz")
                return "archive";
        }

        var mt = mediaType?.ToLowerInvariant() ?? "";
        if (mt is "image")
            return "image";
        if (mt is "sticker")
            return "sticker";
        if (mt is "video")
            return "video";
        if (mt is "audio" or "ptt")
            return "audio";
        if (mt is "document")
            return "doc";

        if (!string.IsNullOrWhiteSpace(mimeType))
        {
            if (mimeType.StartsWith("image/", StringComparison.OrdinalIgnoreCase))
                return "image";
            if (mimeType.StartsWith("video/", StringComparison.OrdinalIgnoreCase))
                return "video";
            if (mimeType.StartsWith("audio/", StringComparison.OrdinalIgnoreCase))
                return "audio";
            if (mimeType.Contains("pdf", StringComparison.OrdinalIgnoreCase))
                return "pdf";
            if (mimeType.Contains("word", StringComparison.OrdinalIgnoreCase))
                return "doc";
            if (mimeType.Contains("excel", StringComparison.OrdinalIgnoreCase) ||
                mimeType.Contains("spreadsheet", StringComparison.OrdinalIgnoreCase))
                return "spreadsheet";
            if (mimeType.Contains("powerpoint", StringComparison.OrdinalIgnoreCase) ||
                mimeType.Contains("presentation", StringComparison.OrdinalIgnoreCase))
                return "presentation";
        }

        return "generic";
    }

    private static BitmapSource? LoadScaledFromPack(string resourcePath, int size)
    {
        foreach (var uri in PackUris(resourcePath))
        {
            try
            {
                var streamInfo = Application.GetResourceStream(uri);
                if (streamInfo is null)
                    continue;

                using (streamInfo.Stream)
                {
                    var bmp = new BitmapImage();
                    bmp.BeginInit();
                    bmp.StreamSource = streamInfo.Stream;
                    bmp.DecodePixelWidth = size;
                    bmp.CacheOption = BitmapCacheOption.OnLoad;
                    bmp.EndInit();
                    bmp.Freeze();
                    return bmp;
                }
            }
            catch
            {
                /* try next uri */
            }
        }

        return null;
    }

    private static IEnumerable<Uri> PackUris(string resourcePath)
    {
        var normalized = resourcePath.Replace('\\', '/').TrimStart('/');
        yield return new Uri($"pack://application:,,,/{normalized}", UriKind.Absolute);

        var lower = normalized.ToLowerInvariant();
        if (!lower.Equals(normalized, StringComparison.Ordinal))
            yield return new Uri($"pack://application:,,,/{lower}", UriKind.Absolute);
    }

    private static BitmapSource? LoadScaledFromFile(string path, int size)
    {
        try
        {
            if (!File.Exists(path))
                return null;

            var bmp = new BitmapImage();
            bmp.BeginInit();
            bmp.UriSource = new Uri(path, UriKind.Absolute);
            bmp.DecodePixelWidth = size;
            bmp.CacheOption = BitmapCacheOption.OnLoad;
            bmp.EndInit();
            bmp.Freeze();
            return bmp;
        }
        catch
        {
            return null;
        }
    }

    private static BitmapSource CreateFallbackIcon()
    {
        var visual = new DrawingVisual();
        using (var dc = visual.RenderOpen())
        {
            dc.DrawRectangle(Brushes.Gainsboro, null, new Rect(0, 0, 32, 32));
            dc.DrawRectangle(Brushes.DarkGray, null, new Rect(8, 6, 16, 20));
        }

        var bmp = new RenderTargetBitmap(32, 32, 96, 96, PixelFormats.Pbgra32);
        bmp.Render(visual);
        bmp.Freeze();
        return bmp;
    }
}
