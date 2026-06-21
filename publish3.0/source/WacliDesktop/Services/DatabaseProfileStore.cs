using System.IO;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Text.RegularExpressions;

namespace WacliDesktop.Services;

/// <summary>
/// 按 WhatsApp 手机号管理数据库：同号复用、异号新建；默认根目录在用户 Profile 下。
/// 配置保存在 AppRoot/runtime/database-profile.json。
/// </summary>
public sealed class DatabaseProfileStore
{
    private static readonly Regex PhoneRegex = new(@"^\+?\d{6,20}$", RegexOptions.Compiled);
    private static readonly object Gate = new();
    private static DatabaseProfileStore? _instance;

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
    };

    public sealed class AccountRecord
    {
        [JsonPropertyName("storeDir")]
        public string StoreDir { get; set; } = "";

        [JsonPropertyName("dbFileName")]
        public string DbFileName { get; set; } = "";
    }

    private sealed class ProfileDocument
    {
        [JsonPropertyName("version")]
        public int Version { get; set; } = 2;

        [JsonPropertyName("defaultDatabaseRoot")]
        public string DefaultDatabaseRoot { get; set; } = "";

        [JsonPropertyName("currentPhone")]
        public string CurrentPhone { get; set; } = "";

        [JsonPropertyName("accounts")]
        public Dictionary<string, AccountRecord> Accounts { get; set; } = new(StringComparer.Ordinal);
    }

    private ProfileDocument _doc = new();

    public static DatabaseProfileStore Instance
    {
        get
        {
            lock (Gate)
                return _instance ??= Load();
        }
    }

    public static void Reload()
    {
        lock (Gate)
            _instance = Load();
    }

    public string DefaultDatabaseRoot
    {
        get
        {
            lock (Gate)
            {
                if (!string.IsNullOrWhiteSpace(_doc.DefaultDatabaseRoot))
                    return _doc.DefaultDatabaseRoot;
                return GetBuiltInDefaultRoot();
            }
        }
    }

    public string CurrentPhone
    {
        get
        {
            lock (Gate)
                return _doc.CurrentPhone;
        }
    }

    public string ProfilePath => Path.Combine(AppConfig.RuntimeDir, "database-profile.json");

    public event Action<string>? PhoneSwitched;

    public bool SetDefaultDatabaseRoot(string path, out string message)
    {
        message = "";
        try
        {
            var full = Path.GetFullPath(path.Trim());
            Directory.CreateDirectory(full);

            int movedCount = 0;
            int keptCount = 0;
            bool unboundMoved;

            lock (Gate)
            {
                var current = _doc.DefaultDatabaseRoot;
                if (string.Equals(current, full, StringComparison.OrdinalIgnoreCase))
                {
                    message = $"默认数据库根目录未变化：{full}";
                    return true;
                }

                var updated = new Dictionary<string, AccountRecord>(StringComparer.Ordinal);
                foreach (var (phone, rec) in _doc.Accounts)
                {
                    var targetStore = Path.Combine(full, BuildDatabaseStem(phone));
                    var targetRec = new AccountRecord
                    {
                        StoreDir = targetStore,
                        DbFileName = string.IsNullOrWhiteSpace(rec.DbFileName) ? BuildDatabaseStem(phone) + ".db" : rec.DbFileName,
                    };

                    if (TryMigrateStore(rec.StoreDir, targetStore))
                        movedCount++;
                    else
                        keptCount++;

                    updated[phone] = targetRec;
                }

                var oldUnbound = Path.Combine(current, "_unbound");
                var newUnbound = Path.Combine(full, "_unbound");
                unboundMoved = TryMigrateStore(oldUnbound, newUnbound);

                _doc.DefaultDatabaseRoot = full;
                _doc.Accounts = updated;
                SaveLocked();
            }

            message =
                $"默认数据库根目录已设为：{full}{Environment.NewLine}" +
                $"账号库迁移：成功 {movedCount}，保留原位 {keptCount}{Environment.NewLine}" +
                $"未绑定库(_unbound)：{(unboundMoved ? "已迁移" : "无数据或已存在目标")}";
            return true;
        }
        catch (Exception ex)
        {
            message = ex.Message;
            return false;
        }
    }

    public bool TryNormalizePhone(string? input, out string normalized)
    {
        normalized = "";
        if (string.IsNullOrWhiteSpace(input))
            return false;
        normalized = NormalizePhone(input);
        return normalized.Length > 0 && PhoneRegex.IsMatch(normalized);
    }

    /// <summary>切换到指定手机号的数据库（复用已有或新建）。</summary>
    public bool SwitchToPhone(string? phone, out string message)
    {
        message = "";
        if (!TryNormalizePhone(phone, out var normalized))
            return false;

        AccountRecord account;
        lock (Gate)
        {
            if (string.Equals(_doc.CurrentPhone, normalized, StringComparison.Ordinal)
                && _doc.Accounts.TryGetValue(normalized, out var existing)
                && Directory.Exists(existing.StoreDir))
            {
                return false;
            }

            account = GetOrCreateAccountLocked(normalized);
        }

        using var mtx = DatabaseStoreMutex.TryAcquire(account.StoreDir);
        if (mtx is null)
        {
            message = "无法锁定数据库目录，可能另一赤瞳实例正在使用该账号数据。";
            return false;
        }

        lock (Gate)
        {
            _doc.CurrentPhone = normalized;
            SaveLocked();
        }

        MigrateUnboundStoreToAccount(account);
        MigrateLegacyRuntimeLayout(normalized, account);
        EnsureAccountDatabase(account);
        message = $"已使用账号 {normalized} 的数据库：{GetDbPath(account)}";
        PhoneSwitched?.Invoke(normalized);
        return true;
    }

    public string GetActiveStoreDir()
    {
        lock (Gate)
        {
            if (!string.IsNullOrWhiteSpace(_doc.CurrentPhone)
                && _doc.Accounts.TryGetValue(_doc.CurrentPhone, out var acc))
                return acc.StoreDir;

            return GetUnboundStoreDir();
        }
    }

    public string GetActiveDbPath()
    {
        lock (Gate)
        {
            if (!string.IsNullOrWhiteSpace(_doc.CurrentPhone)
                && _doc.Accounts.TryGetValue(_doc.CurrentPhone, out var acc))
                return GetDbPath(acc);

            return Path.Combine(GetUnboundStoreDir(), "wacli.db");
        }
    }

    public string GetActiveThumbnailDir() => Path.Combine(GetActiveStoreDir(), "thumbnails");

    public string ResolveReadableDbPath()
    {
        var db = GetActiveDbPath();
        var store = GetActiveStoreDir();
        var legacy = Path.Combine(store, "wacli.db");

        Directory.CreateDirectory(store);
        Directory.CreateDirectory(GetActiveThumbnailDir());

        if (File.Exists(db))
            return db;

        if (File.Exists(legacy))
        {
            TryCopyFile(legacy, db);
            if (File.Exists(db))
                return db;
            return legacy;
        }

        return db;
    }

    public bool ImportDatabase(string sourcePath, out string message)
    {
        message = "";
        if (!File.Exists(sourcePath))
        {
            message = "未找到要加载的数据库文件。";
            return false;
        }

        var store = GetActiveStoreDir();
        using var mtx = DatabaseStoreMutex.TryAcquire(store);
        if (mtx is null)
        {
            message = "数据库目录被占用，请关闭其他赤瞳实例后重试。";
            return false;
        }

        try
        {
            var target = ResolveReadableDbPath();
            Directory.CreateDirectory(Path.GetDirectoryName(target)!);
            File.Copy(sourcePath, target, overwrite: true);
            message = $"已加载数据库：{target}";
            return true;
        }
        catch (Exception ex)
        {
            message = ex.Message;
            return false;
        }
    }

    public bool ExportDatabase(string targetPath, out string message)
    {
        message = "";
        var source = ResolveReadableDbPath();
        if (!File.Exists(source))
        {
            message = "当前没有可导出的数据库。";
            return false;
        }

        var store = GetActiveStoreDir();
        using var mtx = DatabaseStoreMutex.TryAcquire(store);
        if (mtx is null)
        {
            message = "数据库目录被占用，请关闭其他赤瞳实例后重试。";
            return false;
        }

        try
        {
            var dir = Path.GetDirectoryName(targetPath);
            if (!string.IsNullOrWhiteSpace(dir))
                Directory.CreateDirectory(dir);
            File.Copy(source, targetPath, overwrite: true);
            message = $"已导出数据库：{targetPath}";
            return true;
        }
        catch (Exception ex)
        {
            message = ex.Message;
            return false;
        }
    }

    private AccountRecord GetOrCreateAccountLocked(string normalizedPhone)
    {
        if (_doc.Accounts.TryGetValue(normalizedPhone, out var existing)
            && !string.IsNullOrWhiteSpace(existing.StoreDir))
        {
            Directory.CreateDirectory(existing.StoreDir);
            return existing;
        }

        var stem = BuildDatabaseStem(normalizedPhone);
        var storeDir = Path.Combine(DefaultDatabaseRoot, stem);
        var record = new AccountRecord
        {
            StoreDir = storeDir,
            DbFileName = stem + ".db",
        };
        Directory.CreateDirectory(storeDir);
        _doc.Accounts[normalizedPhone] = record;
        return record;
    }

    private static string GetDbPath(AccountRecord account) =>
        Path.Combine(account.StoreDir, account.DbFileName);

    private string GetUnboundStoreDir() => Path.Combine(DefaultDatabaseRoot, "_unbound");

    private void MigrateUnboundStoreToAccount(AccountRecord account)
    {
        var unbound = GetUnboundStoreDir();
        var srcDb = Path.Combine(unbound, "wacli.db");
        var dstDb = GetDbPath(account);
        if (!File.Exists(srcDb))
            return;
        if (File.Exists(dstDb))
            return;

        Directory.CreateDirectory(account.StoreDir);
        TryCopyFile(srcDb, dstDb);

        var unboundThumb = Path.Combine(unbound, "thumbnails");
        var dstThumb = Path.Combine(account.StoreDir, "thumbnails");
        if (Directory.Exists(unboundThumb))
            TryCopyDirectory(unboundThumb, dstThumb);
    }

    private void MigrateLegacyRuntimeLayout(string phone, AccountRecord account)
    {
        var stem = BuildDatabaseStem(phone);
        var legacyDir = Path.Combine(AppConfig.RuntimeDir, stem);
        var legacyDb = Path.Combine(legacyDir, stem + ".db");
        var legacyWacli = Path.Combine(legacyDir, "wacli.db");
        var targetDb = GetDbPath(account);

        if (File.Exists(targetDb))
            return;

        if (File.Exists(legacyDb))
        {
            TryCopyFile(legacyDb, targetDb);
            return;
        }

        if (File.Exists(legacyWacli))
            TryCopyFile(legacyWacli, targetDb);

        var legacyData = Path.Combine(AppConfig.RuntimeDir, "data", "wacli.db");
        if (!File.Exists(targetDb) && File.Exists(legacyData))
            TryCopyFile(legacyData, targetDb);
    }

    private static void EnsureAccountDatabase(AccountRecord account)
    {
        Directory.CreateDirectory(account.StoreDir);
        Directory.CreateDirectory(Path.Combine(account.StoreDir, "thumbnails"));
        var db = GetDbPath(account);
        var legacy = Path.Combine(account.StoreDir, "wacli.db");
        if (!File.Exists(db) && File.Exists(legacy))
            TryCopyFile(legacy, db);
    }

    private static string BuildDatabaseStem(string phone)
    {
        var safe = NormalizePhone(phone).Replace("+", "");
        if (string.IsNullOrWhiteSpace(safe))
            safe = "default";
        return safe + "Data Base";
    }

    private static string NormalizePhone(string input)
    {
        var trimmed = input.Trim();
        if (trimmed.StartsWith("+", StringComparison.Ordinal))
            return "+" + new string(trimmed.Skip(1).Where(char.IsDigit).ToArray());
        return new string(trimmed.Where(char.IsDigit).ToArray());
    }

    public static string GetBuiltInDefaultRoot() =>
        Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "ChitongLingxun");

    private void SaveLocked()
    {
        Directory.CreateDirectory(AppConfig.RuntimeDir);
        if (string.IsNullOrWhiteSpace(_doc.DefaultDatabaseRoot))
            _doc.DefaultDatabaseRoot = GetBuiltInDefaultRoot();
        File.WriteAllText(ProfilePath, JsonSerializer.Serialize(_doc, JsonOptions));
    }

    private static DatabaseProfileStore Load()
    {
        var store = new DatabaseProfileStore();
        try
        {
            if (File.Exists(store.ProfilePath))
            {
                var json = File.ReadAllText(store.ProfilePath);
                store._doc = JsonSerializer.Deserialize<ProfileDocument>(json, JsonOptions) ?? new ProfileDocument();
                try
                {
                    using var doc = JsonDocument.Parse(json);
                    if (string.IsNullOrWhiteSpace(store._doc.CurrentPhone)
                        && doc.RootElement.TryGetProperty("phone", out var legacyPhone))
                    {
                        store._doc.CurrentPhone = legacyPhone.GetString() ?? "";
                    }
                }
                catch
                {
                    /* ignore */
                }
            }
        }
        catch
        {
            store._doc = new ProfileDocument();
        }

        if (string.IsNullOrWhiteSpace(store._doc.DefaultDatabaseRoot))
            store._doc.DefaultDatabaseRoot = GetBuiltInDefaultRoot();

        Directory.CreateDirectory(store.DefaultDatabaseRoot);
        Directory.CreateDirectory(store.GetUnboundStoreDir());

        store.MigrateOldSinglePhoneProfile();
        return store;
    }

    private void MigrateOldSinglePhoneProfile()
    {
        if (_doc.Accounts.Count > 0)
            return;

        if (string.IsNullOrWhiteSpace(_doc.CurrentPhone))
            return;

        if (!TryNormalizePhone(_doc.CurrentPhone, out var phone))
            return;

        var legacyStem = BuildDatabaseStem(phone);
        var legacyDir = Path.Combine(AppConfig.RuntimeDir, legacyStem);
        if (Directory.Exists(legacyDir))
        {
            _doc.Accounts[phone] = new AccountRecord
            {
                StoreDir = legacyDir,
                DbFileName = legacyStem + ".db",
            };
            SaveLocked();
        }
    }

    private static void TryCopyFile(string src, string dst)
    {
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(dst)!);
            File.Copy(src, dst, overwrite: true);
        }
        catch
        {
            /* ignore */
        }
    }

    private static void TryCopyDirectory(string src, string dst)
    {
        try
        {
            Directory.CreateDirectory(dst);
            foreach (var file in Directory.EnumerateFiles(src, "*", SearchOption.AllDirectories))
            {
                var rel = Path.GetRelativePath(src, file);
                var target = Path.Combine(dst, rel);
                Directory.CreateDirectory(Path.GetDirectoryName(target)!);
                File.Copy(file, target, overwrite: true);
            }
        }
        catch
        {
            /* ignore */
        }
    }

    private static bool TryMigrateStore(string src, string dst)
    {
        try
        {
            if (!Directory.Exists(src))
            {
                Directory.CreateDirectory(dst);
                Directory.CreateDirectory(Path.Combine(dst, "thumbnails"));
                return false;
            }

            Directory.CreateDirectory(dst);
            Directory.CreateDirectory(Path.Combine(dst, "thumbnails"));

            using var srcLock = DatabaseStoreMutex.TryAcquire(src, 3_000);
            using var dstLock = DatabaseStoreMutex.TryAcquire(dst, 3_000);
            if (srcLock is null || dstLock is null)
                return false;

            foreach (var file in Directory.EnumerateFiles(src, "*", SearchOption.AllDirectories))
            {
                var rel = Path.GetRelativePath(src, file);
                var target = Path.Combine(dst, rel);
                Directory.CreateDirectory(Path.GetDirectoryName(target)!);
                File.Copy(file, target, overwrite: true);
            }

            // 尝试清理旧目录（失败可忽略，避免数据丢失）
            try
            {
                if (!string.Equals(src, dst, StringComparison.OrdinalIgnoreCase))
                    Directory.Delete(src, recursive: true);
            }
            catch
            {
                /* keep old copy as fallback */
            }

            return true;
        }
        catch
        {
            return false;
        }
    }
}
