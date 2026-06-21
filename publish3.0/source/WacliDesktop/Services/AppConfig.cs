using System.IO;

namespace WacliDesktop.Services;

public static class AppConfig
{
    /// <summary>publish 根目录（含 portable/、runtime/）。程序与 wacli 仍放此处。</summary>
    public static string AppRoot { get; } = ResolveAppRoot();

    /// <summary>运行时目录：bin、environment.json、云端同步配置等（不含 WhatsApp 数据库）。</summary>
    public static string RuntimeDir { get; } = Path.Combine(AppRoot, "runtime");

    public static string LocalBinDir { get; } = Path.Combine(RuntimeDir, "bin");
    public static string LocalWacliExe { get; } = Path.Combine(LocalBinDir, "wacli.exe");
    public static string WacliExe => RuntimeEnvironment.ResolveWacliExe();
    public static string WacliSrcDir { get; } = Path.Combine(RuntimeDir, "src", "wacli");
    public static string WacliWebDir { get; } = Path.Combine(RuntimeDir, "wacli-web");
    public static string EnvironmentManifestPath => RuntimeEnvironment.ManifestPath;
    public static string DatabaseProfilePath => DatabaseProfileStore.Instance.ProfilePath;
    public const string WacliGitUrl = "https://github.com/steipete/wacli.git";

    /// <summary>默认 WhatsApp 数据库根目录（用户 Profile 下 ChitongLingxun，可在数据浏览页修改）。</summary>
    public static string DefaultDatabaseRoot => DatabaseProfileStore.Instance.DefaultDatabaseRoot;

    public static string CurrentPhone => DatabaseProfileStore.Instance.CurrentPhone;

    /// <summary>当前账号 wacli 数据目录（WACLI_STORE_DIR）。</summary>
    public static string StoreDir => DatabaseProfileStore.Instance.GetActiveStoreDir();

    public static string DbPath => DatabaseProfileStore.Instance.GetActiveDbPath();

    public static string ThumbnailDir => DatabaseProfileStore.Instance.GetActiveThumbnailDir();

    public static string LegacyWacliDbPath => Path.Combine(StoreDir, "wacli.db");

    static AppConfig()
    {
        Directory.CreateDirectory(LocalBinDir);
        Directory.CreateDirectory(RuntimeDir);
        Directory.CreateDirectory(DefaultDatabaseRoot);
    }

    public static bool TryBindPhoneProfile(string? phone) =>
        DatabaseProfileStore.Instance.SwitchToPhone(phone, out _);

    public static bool SwitchToPhone(string? phone, out string message) =>
        DatabaseProfileStore.Instance.SwitchToPhone(phone, out message);

    public static bool SetDefaultDatabaseRoot(string path, out string message) =>
        DatabaseProfileStore.Instance.SetDefaultDatabaseRoot(path, out message);

    public static string ResolveReadableDbPath() =>
        DatabaseProfileStore.Instance.ResolveReadableDbPath();

    public static bool ImportDatabase(string sourcePath, out string message) =>
        DatabaseProfileStore.Instance.ImportDatabase(sourcePath, out message);

    public static bool ExportDatabase(string targetPath, out string message) =>
        DatabaseProfileStore.Instance.ExportDatabase(targetPath, out message);

    public static DatabaseStoreMutex? AcquireStoreMutex(int timeoutMs = 15_000) =>
        DatabaseStoreMutex.TryAcquire(StoreDir, timeoutMs);

    public static void ApplyWacliEnvironment(IDictionary<string, string?> env)
    {
        Directory.CreateDirectory(StoreDir);
        Directory.CreateDirectory(ThumbnailDir);
        env["WACLI_STORE_DIR"] = StoreDir;
    }

    private static string ResolveAppRoot()
    {
        var overrideRoot = Environment.GetEnvironmentVariable("CHITONG_APP_ROOT");
        if (!string.IsNullOrWhiteSpace(overrideRoot))
        {
            var full = Path.GetFullPath(overrideRoot.Trim());
            if (Directory.Exists(full))
                return full.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        }

        var exeDir = GetExecutableDirectory();
        if (Path.GetFileName(exeDir).Equals("portable", StringComparison.OrdinalIgnoreCase))
            return Path.GetDirectoryName(exeDir) ?? exeDir;
        return exeDir;
    }

    private static string GetExecutableDirectory()
    {
        var processPath = Environment.ProcessPath;
        if (!string.IsNullOrEmpty(processPath))
        {
            var dir = Path.GetDirectoryName(processPath);
            if (!string.IsNullOrEmpty(dir) && Directory.Exists(dir))
                return dir.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        }

        return AppContext.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
    }
}
