using System.Diagnostics;
using System.IO;
using System.Text.Json;
using System.Text.Json.Serialization;
using Microsoft.Win32;

namespace WacliDesktop.Services;

public sealed class RuntimeEnvironmentManifest
{
    [JsonPropertyName("version")]
    public int Version { get; set; } = 1;

    [JsonPropertyName("appRoot")]
    public string AppRoot { get; set; } = "";

    [JsonPropertyName("storeDir")]
    public string StoreDir { get; set; } = "";

    [JsonPropertyName("updatedAt")]
    public DateTime UpdatedAt { get; set; }

    [JsonPropertyName("tools")]
    public Dictionary<string, ToolRecord> Tools { get; set; } = new();
}

public sealed class ToolRecord
{
    [JsonPropertyName("path")]
    public string Path { get; set; } = "";

    /// <summary>system | winget | local-built | local-copied | manifest</summary>
    [JsonPropertyName("source")]
    public string Source { get; set; } = "";

    [JsonPropertyName("version")]
    public string? Version { get; set; }
}

public static class RuntimeEnvironment
{
    private static readonly object Gate = new();
    private static RuntimeEnvironmentManifest? _cached;

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
    };

    public static string ManifestPath => Path.Combine(AppConfig.RuntimeDir, "environment.json");

    public static RuntimeEnvironmentManifest Current
    {
        get
        {
            lock (Gate)
                return _cached ??= LoadFromDisk();
        }
    }

    public static void Reload()
    {
        lock (Gate)
            _cached = null;
    }

    public static void Save(RuntimeEnvironmentManifest manifest)
    {
        Directory.CreateDirectory(AppConfig.RuntimeDir);
        manifest.UpdatedAt = DateTime.UtcNow;
        manifest.AppRoot = AppConfig.AppRoot;
        manifest.StoreDir = AppConfig.StoreDir;
        File.WriteAllText(ManifestPath, JsonSerializer.Serialize(manifest, JsonOptions));
        lock (Gate)
            _cached = manifest;
    }

    public static string? ResolveToolPath(string tool)
    {
        if (Current.Tools.TryGetValue(tool, out var saved)
            && ToolDiscovery.IsValidToolPath(tool, saved.Path))
            return saved.Path;

        return ToolDiscovery.Find(tool);
    }

    public static string ResolveWacliExe()
    {
        var local = AppConfig.LocalWacliExe;
        if (File.Exists(local) && ToolDiscovery.VerifyWacli(local))
            return local;

        var resolved = ResolveToolPath("wacli");
        if (!string.IsNullOrEmpty(resolved))
            return resolved;

        return local;
    }

    private static RuntimeEnvironmentManifest LoadFromDisk()
    {
        try
        {
            if (!File.Exists(ManifestPath))
                return new RuntimeEnvironmentManifest();

            var json = File.ReadAllText(ManifestPath);
            var manifest = JsonSerializer.Deserialize<RuntimeEnvironmentManifest>(json, JsonOptions)
                           ?? new RuntimeEnvironmentManifest();

            if (!string.Equals(manifest.AppRoot, AppConfig.AppRoot, StringComparison.OrdinalIgnoreCase))
            {
                // 程序目录变了，丢弃旧 manifest 中的路径缓存（wacli 本地路径除外）
                manifest.Tools.Remove("git");
                manifest.Tools.Remove("go");
                manifest.Tools.Remove("gcc");
            }

            return manifest;
        }
        catch
        {
            return new RuntimeEnvironmentManifest();
        }
    }
}
