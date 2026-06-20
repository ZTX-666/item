using System.IO;

namespace WacliDesktop.Services;

/// <summary>按数据目录跨进程互斥，避免双开或 sync/导入同时写同一库。</summary>
public sealed class DatabaseStoreMutex : IDisposable
{
    private readonly Mutex? _mutex;
    private bool _owned;

    private DatabaseStoreMutex(Mutex? mutex, bool owned)
    {
        _mutex = mutex;
        _owned = owned;
    }

    public static DatabaseStoreMutex? TryAcquire(string storeDir, int timeoutMs = 15_000)
    {
        if (string.IsNullOrWhiteSpace(storeDir))
            return null;

        var name = BuildMutexName(storeDir);
        Mutex? mtx = null;
        try
        {
            mtx = new Mutex(false, name);
            if (!mtx.WaitOne(timeoutMs))
            {
                mtx.Dispose();
                return null;
            }
            return new DatabaseStoreMutex(mtx, true);
        }
        catch
        {
            mtx?.Dispose();
            return null;
        }
    }

    public void Dispose()
    {
        if (!_owned || _mutex is null)
            return;
        try
        {
            _mutex.ReleaseMutex();
        }
        catch
        {
            /* ignore */
        }
        _mutex.Dispose();
        _owned = false;
    }

    private static string BuildMutexName(string storeDir)
    {
        var full = Path.GetFullPath(storeDir).TrimEnd('\\', '/').ToLowerInvariant();
        var hash = Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(
            System.Text.Encoding.UTF8.GetBytes(full)));
        if (hash.Length > 16)
            hash = hash[..16];
        return @"Global\ChitongLingxun.Db." + hash;
    }
}
