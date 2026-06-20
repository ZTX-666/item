namespace PaddlePdfOcrApp.Models;

public sealed class RecognitionTemplate
{
    public List<OcrRegion> Regions { get; set; } = [];
    public List<PageResultRow> Rows { get; set; } = [];
}

public sealed class PageResultRow
{
    public int Page { get; set; }
    public Dictionary<string, string> Values { get; set; } = [];
}
