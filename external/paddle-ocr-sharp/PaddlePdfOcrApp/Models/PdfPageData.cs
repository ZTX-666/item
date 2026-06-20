namespace PaddlePdfOcrApp.Models;

public sealed class PdfPageData
{
    public required byte[] Pixels { get; init; }
    public required int Width { get; init; }
    public required int Height { get; init; }
    public required int PageIndex { get; init; }
    public required int PageCount { get; init; }
}
