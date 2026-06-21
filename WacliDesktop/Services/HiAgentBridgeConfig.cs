using System.IO;
using System.Text.Json;

namespace WacliDesktop.Services;

public sealed class HiAgentBridgeConfig
{
    public string ApiKey { get; set; } = "";
    public int Port { get; set; } = 8787;
    public string? PublicBaseUrl { get; set; }
    public string? LastStartedAt { get; set; }

    public static string ConfigPath => Path.Combine(AppConfig.RuntimeDir, "hiagent-bridge.json");

    public static HiAgentBridgeConfig Load()
    {
        try
        {
            if (!File.Exists(ConfigPath))
                return new HiAgentBridgeConfig();
            var json = File.ReadAllText(ConfigPath);
            return JsonSerializer.Deserialize<HiAgentBridgeConfig>(json) ?? new HiAgentBridgeConfig();
        }
        catch
        {
            return new HiAgentBridgeConfig();
        }
    }

    public void Save()
    {
        Directory.CreateDirectory(AppConfig.RuntimeDir);
        var json = JsonSerializer.Serialize(this, new JsonSerializerOptions { WriteIndented = true });
        File.WriteAllText(ConfigPath, json);
    }

    public static string GenerateApiKey() =>
        Convert.ToHexString(Guid.NewGuid().ToByteArray()).ToLowerInvariant();
}
