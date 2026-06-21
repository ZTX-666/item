using System.IO;
using System.Text.Json;

namespace WacliDesktop.Services;

public sealed class CloudSyncState
{
    public long LastMessageTs { get; set; }
    public HashSet<string> SyncedThumbnailMsgIds { get; set; } = new(StringComparer.Ordinal);
    public HashSet<string> SyncedFullMediaMsgIds { get; set; } = new(StringComparer.Ordinal);

    public static string StatePath => Path.Combine(AppConfig.RuntimeDir, "cloud-sync-state.json");

    public static CloudSyncState Load()
    {
        try
        {
            if (!File.Exists(StatePath))
                return new CloudSyncState();
            var json = File.ReadAllText(StatePath);
            return JsonSerializer.Deserialize<CloudSyncState>(json) ?? new CloudSyncState();
        }
        catch
        {
            return new CloudSyncState();
        }
    }

    public void Save()
    {
        Directory.CreateDirectory(AppConfig.RuntimeDir);
        PruneSets();
        var json = JsonSerializer.Serialize(this, new JsonSerializerOptions { WriteIndented = true });
        File.WriteAllText(StatePath, json);
    }

    private void PruneSets()
    {
        const int max = 80_000;
        if (SyncedThumbnailMsgIds.Count > max)
            SyncedThumbnailMsgIds = SyncedThumbnailMsgIds.OrderBy(x => x).Skip(SyncedThumbnailMsgIds.Count - max).ToHashSet(StringComparer.Ordinal);
        if (SyncedFullMediaMsgIds.Count > max)
            SyncedFullMediaMsgIds = SyncedFullMediaMsgIds.OrderBy(x => x).Skip(SyncedFullMediaMsgIds.Count - max).ToHashSet(StringComparer.Ordinal);
    }
}
