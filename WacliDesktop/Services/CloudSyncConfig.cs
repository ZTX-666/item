using System.IO;
using System.Security.Cryptography;
using System.Text.Json;

namespace WacliDesktop.Services;

/// <summary>耀耀工厂 · 云端同步配置（runtime/cloud-sync.json）</summary>
public sealed class CloudSyncConfig
{
    /// <summary>0=仅元数据 1=含缩略图 2=含原文件媒体</summary>
    public int SyncTier { get; set; }

    public string ApiBaseUrl { get; set; } = "";
    public string OwnerId { get; set; } = "";
    public string SyncToken { get; set; } = "";

    public bool AutoSyncEnabled { get; set; }
    public int AutoSyncIntervalMinutes { get; set; } = 15;
    public int MessageBatchSize { get; set; } = 100;
    public int MaxRetryCount { get; set; } = 3;

    /// <summary>档位2：单文件最大字节，默认 50MB</summary>
    public long MaxMediaFileBytes { get; set; } = 52_428_800;

    /// <summary>档位1：缩略图最大字节，默认 5MB</summary>
    public long MaxThumbnailBytes { get; set; } = 5_242_880;

    public string? LastSuccessAt { get; set; }
    public string? LastError { get; set; }

    public static string ConfigPath => Path.Combine(AppConfig.RuntimeDir, "cloud-sync.json");

    public static CloudSyncConfig Load()
    {
        try
        {
            if (!File.Exists(ConfigPath))
                return new CloudSyncConfig();
            var json = File.ReadAllText(ConfigPath);
            var cfg = JsonSerializer.Deserialize<CloudSyncConfig>(json) ?? new CloudSyncConfig();
            if (!string.IsNullOrEmpty(cfg.SyncToken) && cfg.SyncToken.StartsWith("dpapi:", StringComparison.Ordinal))
                cfg.SyncToken = Unprotect(cfg.SyncToken["dpapi:".Length..]);
            return cfg;
        }
        catch
        {
            return new CloudSyncConfig();
        }
    }

    public void Save()
    {
        Directory.CreateDirectory(AppConfig.RuntimeDir);
        var copy = new CloudSyncConfig
        {
            SyncTier = SyncTier,
            ApiBaseUrl = ApiBaseUrl.Trim().TrimEnd('/'),
            OwnerId = OwnerId.Trim(),
            AutoSyncEnabled = AutoSyncEnabled,
            AutoSyncIntervalMinutes = Math.Clamp(AutoSyncIntervalMinutes, 5, 1440),
            MessageBatchSize = Math.Clamp(MessageBatchSize, 10, 500),
            MaxRetryCount = Math.Clamp(MaxRetryCount, 1, 10),
            MaxMediaFileBytes = MaxMediaFileBytes > 0 ? MaxMediaFileBytes : 52_428_800,
            MaxThumbnailBytes = MaxThumbnailBytes > 0 ? MaxThumbnailBytes : 5_242_880,
            LastSuccessAt = LastSuccessAt,
            LastError = LastError,
            SyncToken = string.IsNullOrEmpty(SyncToken) ? "" : "dpapi:" + Protect(SyncToken),
        };
        var json = JsonSerializer.Serialize(copy, new JsonSerializerOptions { WriteIndented = true });
        File.WriteAllText(ConfigPath, json);
    }

    public string HealthUrl() => $"{ApiBaseUrl.TrimEnd('/')}/sync/v1/health";
    public string MessagesUrl() => $"{ApiBaseUrl.TrimEnd('/')}/sync/v1/messages";
    public string MediaUrl() => $"{ApiBaseUrl.TrimEnd('/')}/sync/v1/media";

    public static string TierLabel(int tier) => tier switch
    {
        0 => "档位1：仅消息元数据",
        1 => "档位2：元数据 + 缩略图",
        2 => "档位3：元数据 + 缩略图 + 原文件",
        _ => "未知档位",
    };

    private static string Protect(string plain)
    {
        var bytes = System.Text.Encoding.UTF8.GetBytes(plain);
        var enc = ProtectedData.Protect(bytes, null, DataProtectionScope.CurrentUser);
        return Convert.ToBase64String(enc);
    }

    private static string Unprotect(string b64)
    {
        try
        {
            var enc = Convert.FromBase64String(b64);
            var dec = ProtectedData.Unprotect(enc, null, DataProtectionScope.CurrentUser);
            return System.Text.Encoding.UTF8.GetString(dec);
        }
        catch
        {
            return "";
        }
    }
}
