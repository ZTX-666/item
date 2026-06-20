using PaddlePdfOcrApp.Models;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Text.Json;
using System.Windows;
using System.Windows.Media;
using System.Windows.Media.Imaging;

namespace PaddlePdfOcrApp.Services;

public sealed class OcrEngineService : IDisposable
{
    private readonly int _canvasWidth;
    private readonly int _canvasHeight;
    private readonly object _workerLock = new();
    private string? _pythonExePath;
    private Process? _workerProcess;
    private StreamWriter? _workerInput;
    private StreamReader? _workerOutput;
    private bool _fastMode = true;
    private string? _workerScriptPath;

    public OcrEngineService(int canvasWidth, int canvasHeight)
    {
        _canvasWidth = canvasWidth;
        _canvasHeight = canvasHeight;
    }

    public void EnsureInitialized(string? pythonExePath, bool fastMode = true)
    {
        if (string.IsNullOrWhiteSpace(pythonExePath) || !File.Exists(pythonExePath))
        {
            throw new InvalidOperationException("Python OCR環境未配置或 python.exe 不存在。");
        }

        _fastMode = fastMode;
        if (string.Equals(_pythonExePath, pythonExePath, StringComparison.OrdinalIgnoreCase) && IsWorkerHealthy())
        {
            return;
        }

        StopWorker();
        _pythonExePath = pythonExePath;
        StartWorker();
    }

    public string Recognize(PdfPageData page, OcrRegion region)
    {
        if (string.IsNullOrWhiteSpace(_pythonExePath))
        {
            throw new InvalidOperationException("OCR引擎未初始化。");
        }

        // 1) First pass: fast mode on the original crop.
        var firstText = RecognizeWithCrop(page, region, _pythonExePath, _fastMode, paddingPixels: 0);
        if (IsUsefulResult(firstText))
        {
            return firstText;
        }

        // 2) Fallback pass: expand crop + disable fast mode for better handwritten robustness.
        var secondText = RecognizeWithCrop(page, region, _pythonExePath, false, paddingPixels: 16);
        return string.IsNullOrWhiteSpace(secondText) ? firstText : secondText;
    }

    public void Dispose()
    {
        StopWorker();
    }

    public BitmapSource CreateCropPreview(PdfPageData page, OcrRegion region)
    {
        return CreateCropPreview(page, region, 0);
    }

    private BitmapSource CreateCropPreview(PdfPageData page, OcrRegion region, int paddingPixels)
    {
        var source = BitmapSource.Create(
            page.Width,
            page.Height,
            96,
            96,
            PixelFormats.Bgra32,
            null,
            page.Pixels,
            page.Width * 4);

        var composed = ComposeToCanvas(source);
        var rect = BuildCropRect(region, paddingPixels);
        var cropped = (BitmapSource)new CroppedBitmap(composed, rect);
        if (Math.Abs(region.Angle) > 0.01d)
        {
            cropped = RotateBitmap(cropped, -region.Angle);
        }

        return cropped;
    }

    private static BitmapSource RotateBitmap(BitmapSource source, double angle)
    {
        var normalized = angle % 360d;
        if (Math.Abs(normalized) < 0.01d)
        {
            return source;
        }

        var radians = normalized * Math.PI / 180d;
        var cos = Math.Abs(Math.Cos(radians));
        var sin = Math.Abs(Math.Sin(radians));
        var newWidth = Math.Max(1, (int)Math.Round(source.PixelWidth * cos + source.PixelHeight * sin));
        var newHeight = Math.Max(1, (int)Math.Round(source.PixelWidth * sin + source.PixelHeight * cos));

        var visual = new DrawingVisual();
        using (var ctx = visual.RenderOpen())
        {
            ctx.PushTransform(new TranslateTransform(newWidth / 2d, newHeight / 2d));
            ctx.PushTransform(new RotateTransform(normalized));
            ctx.DrawImage(source, new Rect(-source.PixelWidth / 2d, -source.PixelHeight / 2d, source.PixelWidth, source.PixelHeight));
        }

        var target = new RenderTargetBitmap(newWidth, newHeight, 96, 96, PixelFormats.Pbgra32);
        target.Render(visual);
        target.Freeze();
        return target;
    }

    private BitmapSource ComposeToCanvas(BitmapSource source)
    {
        var target = new RenderTargetBitmap(_canvasWidth, _canvasHeight, 96, 96, PixelFormats.Pbgra32);
        var visual = new DrawingVisual();
        using (var ctx = visual.RenderOpen())
        {
            ctx.DrawRectangle(Brushes.White, null, new Rect(0, 0, _canvasWidth, _canvasHeight));

            var scale = Math.Min((double)_canvasWidth / source.PixelWidth, (double)_canvasHeight / source.PixelHeight);
            var drawWidth = source.PixelWidth * scale;
            var drawHeight = source.PixelHeight * scale;
            var drawX = (_canvasWidth - drawWidth) / 2d;
            var drawY = (_canvasHeight - drawHeight) / 2d;
            ctx.DrawImage(source, new Rect(drawX, drawY, drawWidth, drawHeight));
        }

        target.Render(visual);
        return target;
    }

    private Int32Rect BuildCropRect(OcrRegion region, int paddingPixels = 0)
    {
        var pixelX = (int)Math.Round(region.X) - paddingPixels;
        var pixelY = (int)Math.Round(region.Y) - paddingPixels;
        var pixelW = (int)Math.Round(region.Width) + paddingPixels * 2;
        var pixelH = (int)Math.Round(region.Height) + paddingPixels * 2;

        pixelX = Math.Clamp(pixelX, 0, _canvasWidth - 1);
        pixelY = Math.Clamp(pixelY, 0, _canvasHeight - 1);
        pixelW = Math.Clamp(pixelW, 1, _canvasWidth - pixelX);
        pixelH = Math.Clamp(pixelH, 1, _canvasHeight - pixelY);
        if (pixelW <= 0 || pixelH <= 0)
        {
            throw new Exception("識別框無效：裁剪尺寸為 0，請重新框選更大的區域。");
        }

        return new Int32Rect(pixelX, pixelY, pixelW, pixelH);
    }

    private string RecognizeWithCrop(PdfPageData page, OcrRegion region, string pythonExePath, bool fastMode, int paddingPixels)
    {
        var cropped = CreateCropPreview(page, region, paddingPixels);
        var tempFile = Path.Combine(Path.GetTempPath(), $"ocr_region_{Guid.NewGuid():N}.png");
        SaveBitmapForOcr(cropped, tempFile);
        var fileInfo = new FileInfo(tempFile);
        if (!fileInfo.Exists || fileInfo.Length <= 0)
        {
            throw new Exception("裁剪圖像為空，請調整識別框位置或大小後重試。");
        }

        try
        {
            return RunInWorker(tempFile, pythonExePath, fastMode);
        }
        finally
        {
            if (File.Exists(tempFile))
            {
                File.Delete(tempFile);
            }
        }
    }

    private static bool IsUsefulResult(string? text)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return false;
        }

        var compact = text.Trim();
        return compact.Length >= 2;
    }

    private static void SaveBitmapForOcr(BitmapSource source, string outputPath)
    {
        // Upscale tiny crops to help handwritten stroke visibility.
        const int minSize = 96;
        BitmapSource finalSource = source;
        if (source.PixelWidth < minSize || source.PixelHeight < minSize)
        {
            var scale = Math.Max((double)minSize / source.PixelWidth, (double)minSize / source.PixelHeight);
            finalSource = new TransformedBitmap(source, new ScaleTransform(scale, scale));
        }

        using var fs = File.OpenWrite(outputPath);
        var encoder = new PngBitmapEncoder();
        encoder.Frames.Add(BitmapFrame.Create(finalSource));
        encoder.Save(fs);
    }

    private string RunInWorker(string imagePath, string pythonExePath, bool fastMode)
    {
        if (!IsWorkerHealthy())
        {
            EnsureInitialized(pythonExePath, _fastMode);
        }

        if (_workerInput == null || _workerOutput == null)
        {
            throw new InvalidOperationException("Python OCR worker 未就緒。");
        }

        lock (_workerLock)
        {
            var reqId = Guid.NewGuid().ToString("N");
            var payload = JsonSerializer.Serialize(new WorkerRequest
            {
                id = reqId,
                cmd = "recognize",
                image = imagePath,
                fast_mode = fastMode
            });

            _workerInput.WriteLine(payload);
            _workerInput.Flush();

            var timeout = TimeSpan.FromSeconds(60);
            var startAt = DateTime.UtcNow;
            while (DateTime.UtcNow - startAt < timeout)
            {
                var elapsed = DateTime.UtcNow - startAt;
                var remaining = timeout - elapsed;
                if (remaining <= TimeSpan.Zero)
                {
                    break;
                }

                string? line;
                try
                {
                    line = _workerOutput.ReadLineAsync().WaitAsync(remaining).GetAwaiter().GetResult();
                }
                catch (TimeoutException)
                {
                    throw new TimeoutException("OCR 處理超時，Python worker 未在 60 秒內返回。");
                }

                if (line == null)
                {
                    throw new Exception("Python worker 已斷開。");
                }

                WorkerResponse? response;
                try
                {
                    response = JsonSerializer.Deserialize<WorkerResponse>(line);
                }
                catch
                {
                    continue;
                }

                if (response == null || !string.Equals(response.id, reqId, StringComparison.Ordinal))
                {
                    continue;
                }

                if (!response.ok)
                {
                    throw new Exception(response.error ?? "Python OCR 處理失敗。");
                }

                return response.text ?? string.Empty;
            }
        }

        throw new TimeoutException("OCR 處理超時，Python worker 未在 60 秒內返回。");
    }

    private void StartWorker()
    {
        if (string.IsNullOrWhiteSpace(_pythonExePath))
        {
            throw new InvalidOperationException("Python 路徑未初始化。");
        }

        var scriptPath = EnsureWorkerScriptFile();

        var process = new Process
        {
            StartInfo = new ProcessStartInfo
            {
                FileName = _pythonExePath,
                Arguments = $"\"{scriptPath}\" --server",
                WorkingDirectory = AppContext.BaseDirectory,
                UseShellExecute = false,
                CreateNoWindow = true,
                WindowStyle = ProcessWindowStyle.Hidden,
                RedirectStandardInput = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true
            }
        };

        process.Start();
        var readyLine = process.StandardOutput.ReadLineAsync().WaitAsync(TimeSpan.FromSeconds(15)).GetAwaiter().GetResult();
        if (!string.Equals(readyLine, "READY", StringComparison.Ordinal))
        {
            var stderr = process.StandardError.ReadToEnd();
            try
            {
                process.Kill(true);
            }
            catch
            {
            }
            throw new Exception($"Python worker 啟動失敗：{readyLine} {stderr}");
        }

        _workerProcess = process;
        _workerInput = process.StandardInput;
        _workerOutput = process.StandardOutput;
    }

    private bool IsWorkerHealthy()
    {
        return _workerProcess is { HasExited: false } && _workerInput != null && _workerOutput != null;
    }

    private string EnsureWorkerScriptFile()
    {
        if (!string.IsNullOrWhiteSpace(_workerScriptPath) && File.Exists(_workerScriptPath))
        {
            return _workerScriptPath;
        }

        var asm = Assembly.GetExecutingAssembly();
        var resourceName = asm.GetManifestResourceNames()
            .FirstOrDefault(n => n.EndsWith(".rapid_ocr_worker.py", StringComparison.OrdinalIgnoreCase));
        if (resourceName == null)
        {
            throw new FileNotFoundException("缺少內嵌 OCR 腳本資源。");
        }

        var tempDir = Path.Combine(Path.GetTempPath(), "PaddlePdfOcrApp");
        Directory.CreateDirectory(tempDir);
        var scriptPath = Path.Combine(tempDir, "rapid_ocr_worker.py");

        using var stream = asm.GetManifestResourceStream(resourceName)
            ?? throw new FileNotFoundException("讀取內嵌 OCR 腳本失敗。");
        using var file = File.Open(scriptPath, FileMode.Create, FileAccess.Write, FileShare.Read);
        stream.CopyTo(file);

        _workerScriptPath = scriptPath;
        return scriptPath;
    }

    private void StopWorker()
    {
        lock (_workerLock)
        {
            try
            {
                if (_workerInput != null)
                {
                    var payload = JsonSerializer.Serialize(new WorkerRequest
                    {
                        id = Guid.NewGuid().ToString("N"),
                        cmd = "shutdown",
                        image = string.Empty
                    });
                    _workerInput.WriteLine(payload);
                    _workerInput.Flush();
                }
            }
            catch
            {
            }

            try
            {
                if (_workerProcess != null && !_workerProcess.HasExited)
                {
                    _workerProcess.Kill(true);
                }
            }
            catch
            {
            }
            finally
            {
                _workerInput?.Dispose();
                _workerOutput?.Dispose();
                _workerProcess?.Dispose();
                _workerInput = null;
                _workerOutput = null;
                _workerProcess = null;
            }
        }
    }

    private sealed class WorkerRequest
    {
        public string id { get; set; } = string.Empty;
        public string cmd { get; set; } = "recognize";
        public string image { get; set; } = string.Empty;
        public bool fast_mode { get; set; } = true;
    }

    private sealed class WorkerResponse
    {
        public string id { get; set; } = string.Empty;
        public bool ok { get; set; }
        public string? text { get; set; }
        public string? error { get; set; }
    }
}
