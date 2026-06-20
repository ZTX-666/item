using System.Text.Json;
using PaddlePdfOcrApp.Models;
using System.IO;

namespace PaddlePdfOcrApp.Services;

public sealed class AppConfigService
{
    private readonly string _configPath;

    public AppConfigService(string baseDirectory)
    {
        _configPath = Path.Combine(baseDirectory, "appsettings.local.json");
    }

    public AppConfig Load()
    {
        if (!File.Exists(_configPath))
        {
            var defaultConfig = new AppConfig();
            Save(defaultConfig);
            return defaultConfig;
        }

        var json = File.ReadAllText(_configPath);
        return JsonSerializer.Deserialize<AppConfig>(json) ?? new AppConfig();
    }

    public void Save(AppConfig config)
    {
        var json = JsonSerializer.Serialize(config, new JsonSerializerOptions { WriteIndented = true });
        File.WriteAllText(_configPath, json);
    }
}
