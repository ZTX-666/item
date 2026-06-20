namespace PaddlePdfOcrApp.Models;

public sealed class OcrRegion
{
    public string Name { get; set; } = string.Empty;
    public double X { get; set; }
    public double Y { get; set; }
    public double Width { get; set; }
    public double Height { get; set; }
    public double Angle { get; set; }
}
