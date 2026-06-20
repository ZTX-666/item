using PaddlePdfOcrApp.Models;
using System.Data;

namespace PaddlePdfOcrApp.Services;

public sealed class OcrWorkflowService
{
    private readonly PdfRenderService _pdfRenderService;
    private readonly OcrEngineService _ocrEngineService;

    public OcrWorkflowService(PdfRenderService pdfRenderService, OcrEngineService ocrEngineService)
    {
        _pdfRenderService = pdfRenderService;
        _ocrEngineService = ocrEngineService;
    }

    public PageRecognitionResult RecognizeSinglePage(
        PdfPageData page,
        IReadOnlyList<OcrRegion> regions)
    {
        var result = new PageRecognitionResult
        {
            PageNumber = page.PageIndex + 1
        };
        foreach (var region in regions)
        {
            try
            {
                result.Values[region.Name] = _ocrEngineService.Recognize(page, region);
            }
            catch (Exception ex)
            {
                result.Values[region.Name] = $"[識別失敗]{ex.Message}";
            }
        }
        return result;
    }

    public List<PageRecognitionResult> RecognizeAllPages(
        string pdfPath,
        IReadOnlyList<OcrRegion> regions,
        int renderWidth,
        int renderHeight,
        IProgress<(int Current, int Total)>? progress = null,
        Action<PageRecognitionResult>? onPageRecognized = null,
        CancellationToken cancellationToken = default)
    {
        var results = new List<PageRecognitionResult>();
        var firstPage = _pdfRenderService.RenderPage(pdfPath, 0, renderWidth, renderHeight);
        var firstResult = RecognizeSinglePage(firstPage, regions);
        results.Add(firstResult);
        onPageRecognized?.Invoke(firstResult);
        progress?.Report((1, firstPage.PageCount));
        for (var pageIndex = 1; pageIndex < firstPage.PageCount; pageIndex++)
        {
            cancellationToken.ThrowIfCancellationRequested();
            PageRecognitionResult pageResult;
            try
            {
                var page = _pdfRenderService.RenderPage(pdfPath, pageIndex, renderWidth, renderHeight);
                pageResult = RecognizeSinglePage(page, regions);
            }
            catch (Exception ex)
            {
                pageResult = new PageRecognitionResult
                {
                    PageNumber = pageIndex + 1
                };

                foreach (var region in regions)
                {
                    pageResult.Values[region.Name] = $"[識別失敗]{ex.Message}";
                }
            }
            results.Add(pageResult);
            onPageRecognized?.Invoke(pageResult);
            progress?.Report((pageIndex + 1, firstPage.PageCount));
        }
        return results;
    }
}
