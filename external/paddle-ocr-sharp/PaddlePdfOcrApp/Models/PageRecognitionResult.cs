namespace PaddlePdfOcrApp.Models;

public sealed class PageRecognitionResult
{
    public int PageNumber { get; set; }
    public Dictionary<string, string> Values { get; set; } = [];
}
