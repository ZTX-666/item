using Docnet.Core;
using Docnet.Core.Models;
using PaddlePdfOcrApp.Models;

namespace PaddlePdfOcrApp.Services;

public sealed class PdfRenderService
{
    public PdfPageData RenderPage(string pdfPath, int pageIndex, int renderWidth, int renderHeight)
    {
        if (renderWidth <= 0 || renderHeight <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(renderWidth), "渲染尺寸必須大於 0。");
        }

        using var probeReader = DocLib.Instance.GetDocReader(pdfPath, new PageDimensions(1, 1));
        var pageCount = probeReader.GetPageCount();
        if (pageCount <= 0)
        {
            throw new InvalidOperationException("PDF 沒有可讀取頁面。");
        }

        if (pageIndex < 0 || pageIndex >= pageCount)
        {
            throw new ArgumentOutOfRangeException(nameof(pageIndex), "頁碼超出範圍。");
        }

        using var probePageReader = probeReader.GetPageReader(pageIndex);
        var sourceWidth = Math.Max(1, probePageReader.GetPageWidth());
        var sourceHeight = Math.Max(1, probePageReader.GetPageHeight());
        var scale = Math.Min((double)renderWidth / sourceWidth, (double)renderHeight / sourceHeight);
        var targetWidth = Math.Max(1, (int)Math.Round(sourceWidth * scale));
        var targetHeight = Math.Max(1, (int)Math.Round(sourceHeight * scale));

        using var docReader = DocLib.Instance.GetDocReader(pdfPath, new PageDimensions(targetWidth, targetHeight));
        using var pageReader = docReader.GetPageReader(pageIndex);
        return new PdfPageData
        {
            Pixels = pageReader.GetImage(),
            Width = pageReader.GetPageWidth(),
            Height = pageReader.GetPageHeight(),
            PageIndex = pageIndex,
            PageCount = pageCount
        };
    }
}
