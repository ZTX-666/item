using System.Text;
using System.IO;

namespace PaddlePdfOcrApp.Services;

public static class CrashLogger
{
    private static readonly object Sync = new();
    private static string _logDir = Path.Combine(AppContext.BaseDirectory, "log");

    public static void Initialize(string? baseDir = null)
    {
        if (!string.IsNullOrWhiteSpace(baseDir))
        {
            _logDir = Path.Combine(baseDir, "log");
        }

        Directory.CreateDirectory(_logDir);
        WriteInfo("Crash logger initialized.");
    }

    public static void WriteInfo(string message)
    {
        Write("INFO", message, null);
    }

    public static void WriteError(string message, Exception? ex = null)
    {
        Write("ERROR", message, ex);
    }

    private static void Write(string level, string message, Exception? ex)
    {
        try
        {
            lock (Sync)
            {
                Directory.CreateDirectory(_logDir);
                var filePath = Path.Combine(_logDir, $"app-{DateTime.Now:yyyyMMdd}.log");
                var sb = new StringBuilder();
                sb.AppendLine($"[{DateTime.Now:yyyy-MM-dd HH:mm:ss.fff}] [{level}] {message}");
                if (ex != null)
                {
                    sb.AppendLine(ex.ToString());
                }

                File.AppendAllText(filePath, sb.ToString(), Encoding.UTF8);
            }
        }
        catch
        {
            // Intentionally swallow logging failures.
        }
    }
}
