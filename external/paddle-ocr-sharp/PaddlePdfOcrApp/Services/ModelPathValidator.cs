using System.IO;

namespace PaddlePdfOcrApp.Services;

public sealed class ModelPathValidator
{
    public (bool IsValid, string Message) Validate(string? modelRootPath)
    {
        if (string.IsNullOrWhiteSpace(modelRootPath))
        {
            return (false, "模型目錄為空。");
        }

        if (!Directory.Exists(modelRootPath))
        {
            return (false, $"模型目錄不存在：{modelRootPath}");
        }

        var hasV5 = Directory.Exists(Path.Combine(modelRootPath, "PP-OCRv5_mobile_det_infer"))
                    && Directory.Exists(Path.Combine(modelRootPath, "ch_ppocr_mobile_v5.0_cls_infer"))
                    && Directory.Exists(Path.Combine(modelRootPath, "PP-OCRv5_mobile_rec_infer"))
                    && File.Exists(Path.Combine(modelRootPath, "ppocr_keys.txt"));

        var hasV4 = Directory.Exists(Path.Combine(modelRootPath, "ch_PP-OCRv4_det_infer"))
                    && Directory.Exists(Path.Combine(modelRootPath, "ch_ppocr_mobile_v2.0_cls_infer"))
                    && Directory.Exists(Path.Combine(modelRootPath, "ch_PP-OCRv4_rec_infer"))
                    && File.Exists(Path.Combine(modelRootPath, "ppocr_keys.txt"));

        if (!hasV5 && !hasV4)
        {
            return (false, $"缺少模型資源：{modelRootPath}（需滿足 v5 或 v4 目錄結構）");
        }

        return (true, hasV5 ? "檢測到 v5 模型目錄。" : "檢測到 v4 模型目錄。");
    }
}
