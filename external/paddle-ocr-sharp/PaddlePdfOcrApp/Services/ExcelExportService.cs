using ClosedXML.Excel;
using System.Data;

namespace PaddlePdfOcrApp.Services;

public sealed class ExcelExportService
{
    public void Export(DataTable dataTable, string outputPath)
    {
        using var workbook = new XLWorkbook();
        workbook.Worksheets.Add(dataTable, "OCR結果");
        workbook.SaveAs(outputPath);
    }
}
