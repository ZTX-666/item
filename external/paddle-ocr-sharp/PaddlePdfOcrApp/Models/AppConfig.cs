namespace PaddlePdfOcrApp.Models;

public sealed class AppConfig
{
    public string? ModelRootPath { get; set; }
    public string? PythonExePath { get; set; }
    public int RenderWidth { get; set; } = 1500;
    public int RenderHeight { get; set; } = 2000;
    public bool FastMode { get; set; } = true;
}
