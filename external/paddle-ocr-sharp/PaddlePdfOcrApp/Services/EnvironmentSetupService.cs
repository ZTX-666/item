using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Net.Http;
using System.Text;
using System.Text.Json;

namespace PaddlePdfOcrApp.Services;

/// <summary>
/// 一鍵下載並配置：.NET Windows Desktop Runtime（僅框架依賴版需要）、可攜式 Python + OCR 依賴。
/// </summary>
public sealed class EnvironmentSetupService : IDisposable
{
    private const string PythonEmbedVersion = "3.11.9";
    private const string EmbedZipName = "python-3.11.9-embed-amd64.zip";
    private const string EmbedUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip";
    private const string GetPipUrl = "https://bootstrap.pypa.io/get-pip.py";
    private const string DotNetDesktopRuntimeUrl = "https://aka.ms/dotnet/8.0/windowsdesktop-runtime-win-x64.exe";

    private readonly string _baseDirectory;
    private readonly HttpClient _http = new() { Timeout = TimeSpan.FromMinutes(30) };

    public EnvironmentSetupService(string baseDirectory)
    {
        _baseDirectory = baseDirectory.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
    }

    public static bool IsSelfContainedBundle(string appBaseDirectory)
    {
        var path = Path.Combine(appBaseDirectory, "PaddlePdfOcrApp.runtimeconfig.json");
        if (!File.Exists(path))
        {
            return false;
        }

        try
        {
            using var doc = JsonDocument.Parse(File.ReadAllText(path));
            if (!doc.RootElement.TryGetProperty("runtimeOptions", out var ro))
            {
                return false;
            }

            if (!ro.TryGetProperty("includedFrameworks", out var inc))
            {
                return false;
            }

            return inc.ValueKind == JsonValueKind.Array && inc.GetArrayLength() > 0;
        }
        catch
        {
            return false;
        }
    }

    /// <summary>是否已安裝可支援 net8.0-windows 的 Windows Desktop 8.x runtime。</summary>
    public static bool IsWindowsDesktop8RuntimeInstalled()
    {
        var programFiles = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles);
        var desktopRoot = Path.Combine(programFiles, "dotnet", "shared", "Microsoft.WindowsDesktop.App");
        if (!Directory.Exists(desktopRoot))
        {
            return false;
        }

        foreach (var dir in Directory.EnumerateDirectories(desktopRoot))
        {
            var name = Path.GetFileName(dir);
            if (name.StartsWith("8.", StringComparison.Ordinal) || name.StartsWith("8.0", StringComparison.Ordinal))
            {
                return true;
            }
        }

        return false;
    }

    public async Task RunFullSetupAsync(IProgress<string> log, CancellationToken cancellationToken)
    {
        if (IsSelfContainedBundle(_baseDirectory))
        {
            log.Report("偵測到自包含發佈：執行檔已內含 .NET，略過 .NET 安裝步驟。");
        }
        else
        {
            if (IsWindowsDesktop8RuntimeInstalled())
            {
                log.Report("已偵測到 .NET 8 Windows Desktop Runtime，略過 .NET 安裝。");
            }
            else
            {
                log.Report("正在下載 .NET 8 Windows Desktop Runtime（約 55MB，視網速而定）…");
                var installerPath = Path.Combine(Path.GetTempPath(), "windowsdesktop-runtime-8-win-x64-setup.exe");
                await DownloadFileAsync(DotNetDesktopRuntimeUrl, installerPath, log, cancellationToken).ConfigureAwait(false);

                log.Report("即將以系統管理員權限啟動安裝程式（若出現 UAC 請同意）。完成後若提示重新開機，請重新開機後再開啟本程式。");
                await RunProcessElevatedAsync(installerPath, "/install /quiet /norestart", log, cancellationToken).ConfigureAwait(false);

                if (!IsWindowsDesktop8RuntimeInstalled())
                {
                    log.Report("警告：安裝程式已結束，但未偵測到 Desktop Runtime。若本程式仍無法啟動，請手動安裝 Microsoft .NET 8 Desktop Runtime (x64)。");
                }
                else
                {
                    log.Report(".NET 8 Windows Desktop Runtime 安裝完成。");
                }
            }
        }

        await SetupPythonPortableAsync(log, cancellationToken).ConfigureAwait(false);
    }

    private async Task SetupPythonPortableAsync(IProgress<string> log, CancellationToken cancellationToken)
    {
        var dest = Path.Combine(_baseDirectory, "python_portable");
        var pythonExe = Path.Combine(dest, "python.exe");

        if (File.Exists(pythonExe))
        {
            log.Report("偵測到既有 python_portable，將重新安裝 pip 套件並覆寫目錄…");
            try
            {
                Directory.Delete(dest, recursive: true);
            }
            catch (Exception ex)
            {
                throw new InvalidOperationException($"無法刪除舊的 python_portable：{ex.Message}。請關閉可能占用該資料夾的程式後重試。", ex);
            }
        }

        Directory.CreateDirectory(dest);
        var zipPath = Path.Combine(Path.GetTempPath(), EmbedZipName);
        log.Report($"正在下載可攜式 Python {PythonEmbedVersion}…");
        await DownloadFileAsync(EmbedUrl, zipPath, log, cancellationToken).ConfigureAwait(false);

        log.Report("解壓縮 Python…");
        await Task.Run(() => ZipFile.ExtractToDirectory(zipPath, dest, overwriteFiles: true), cancellationToken).ConfigureAwait(false);

        await EnsureImportSiteInPthAsync(dest, cancellationToken).ConfigureAwait(false);

        var getPipPath = Path.Combine(Path.GetTempPath(), "get-pip.py");
        log.Report("下載 get-pip.py…");
        await DownloadFileAsync(GetPipUrl, getPipPath, log, cancellationToken).ConfigureAwait(false);

        log.Report("安裝 pip（請稍候）…");
        await RunPythonAsync(pythonExe, $"\"{getPipPath}\" --no-warn-script-location", log, cancellationToken).ConfigureAwait(false);

        log.Report("安裝 rapidocr-onnxruntime、pillow（下載較大，請耐心等候）…");
        await RunPythonAsync(pythonExe, "-m pip install --upgrade pip", log, cancellationToken).ConfigureAwait(false);
        await RunPythonAsync(pythonExe, "-m pip install rapidocr-onnxruntime pillow", log, cancellationToken).ConfigureAwait(false);

        if (!File.Exists(pythonExe))
        {
            throw new InvalidOperationException("可攜式 Python 安裝後仍找不到 python.exe。");
        }

        log.Report($"Python 環境就緒：{pythonExe}");
    }

    private static async Task EnsureImportSiteInPthAsync(string pythonDir, CancellationToken cancellationToken)
    {
        await Task.Run(() =>
        {
            var pth = Directory.GetFiles(pythonDir, "python*._pth").FirstOrDefault();
            if (pth == null)
            {
                throw new InvalidOperationException("找不到 python*._pth，可攜式套件可能不完整。");
            }

            var text = File.ReadAllText(pth, Encoding.UTF8);
            if (!RegexIsMultilineImportSite(text))
            {
                File.AppendAllText(pth, "\r\nimport site\r\n", Encoding.UTF8);
            }
        }, cancellationToken).ConfigureAwait(false);
    }

    private static bool RegexIsMultilineImportSite(string text) =>
        text.Split('\n').Any(l => string.Equals(l.Trim(), "import site", StringComparison.Ordinal));

    private async Task DownloadFileAsync(string url, string destinationPath, IProgress<string> log, CancellationToken cancellationToken)
    {
        using var response = await _http.GetAsync(url, HttpCompletionOption.ResponseHeadersRead, cancellationToken).ConfigureAwait(false);
        response.EnsureSuccessStatusCode();
        await using var fs = new FileStream(destinationPath, FileMode.Create, FileAccess.Write, FileShare.None, 81920, useAsync: true);
        await using var stream = await response.Content.ReadAsStreamAsync(cancellationToken).ConfigureAwait(false);
        var total = response.Content.Headers.ContentLength;
        var buffer = new byte[81920];
        long read = 0;
        int n;
        var lastReport = DateTime.UtcNow;
        while ((n = await stream.ReadAsync(buffer.AsMemory(0, buffer.Length), cancellationToken).ConfigureAwait(false)) > 0)
        {
            await fs.WriteAsync(buffer.AsMemory(0, n), cancellationToken).ConfigureAwait(false);
            read += n;
            if (total.HasValue && (DateTime.UtcNow - lastReport).TotalSeconds >= 2)
            {
                var pct = (int)(100 * read / total.Value);
                log.Report($"下載進度：{pct}% ({read / 1024 / 1024} MB / {total.Value / 1024 / 1024} MB)");
                lastReport = DateTime.UtcNow;
            }
        }
    }

    private async Task RunPythonAsync(string pythonExe, string arguments, IProgress<string> log, CancellationToken cancellationToken)
    {
        await Task.Run(() =>
        {
            using var p = new Process
            {
                StartInfo = new ProcessStartInfo
                {
                    FileName = pythonExe,
                    Arguments = arguments,
                    UseShellExecute = false,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    CreateNoWindow = true,
                    WorkingDirectory = Path.GetDirectoryName(pythonExe) ?? _baseDirectory
                }
            };

            var sb = new StringBuilder();
            p.OutputDataReceived += (_, e) => { if (e.Data != null) { sb.AppendLine(e.Data); } };
            p.ErrorDataReceived += (_, e) => { if (e.Data != null) { sb.AppendLine(e.Data); } };

            p.Start();
            p.BeginOutputReadLine();
            p.BeginErrorReadLine();
            p.WaitForExit();
            if (p.ExitCode != 0)
            {
                log.Report(sb.ToString());
                throw new InvalidOperationException($"命令失敗（結束代碼 {p.ExitCode}）：python {arguments}");
            }
        }, cancellationToken).ConfigureAwait(false);
    }

    private static async Task RunProcessElevatedAsync(string exePath, string arguments, IProgress<string> log, CancellationToken cancellationToken)
    {
        await Task.Run(() =>
        {
            using var p = new Process
            {
                StartInfo = new ProcessStartInfo
                {
                    FileName = exePath,
                    Arguments = arguments,
                    UseShellExecute = true,
                    Verb = "runas",
                    WindowStyle = ProcessWindowStyle.Hidden
                }
            };

            try
            {
                p.Start();
            }
            catch (Exception ex)
            {
                throw new InvalidOperationException("無法啟動安裝程式（可能需要管理員同意）。", ex);
            }

            p.WaitForExit();
            // 1638 = newer version already installed
            if (p.ExitCode != 0 && p.ExitCode != 1638)
            {
                log.Report($"安裝程式結束代碼：{p.ExitCode}（若非 0 請檢查是否被防毒軟體阻擋）。");
            }
        }, cancellationToken).ConfigureAwait(false);
    }

    public void Dispose() => _http.Dispose();
}
