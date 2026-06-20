using System.Diagnostics;
using System.IO;
using Microsoft.Win32;

namespace WacliDesktop.Services;

internal static class ToolDiscovery
{
    private static readonly Dictionary<string, WingetPackage> WingetPackages = new(StringComparer.OrdinalIgnoreCase)
    {
        ["git"] = new("Git.Git", "git"),
        ["go"] = new("GoLang.Go", "go"),
        ["gcc"] = new("BrechtSanders.WinLibs.POSIX.UCRT", "gcc"),
        ["python"] = new("Python.Python.3.12", "python"),
    };

    public static IReadOnlyDictionary<string, string?> ScanAll()
    {
        var result = new Dictionary<string, string?>(StringComparer.OrdinalIgnoreCase)
        {
            ["git"] = Find("git"),
            ["go"] = Find("go"),
            ["gcc"] = Find("gcc"),
            ["python"] = FindPython(),
            ["wacli"] = FindWacli(),
        };
        return result;
    }

    public static string? Find(string tool) =>
        FindFromManifest(tool)
        ?? FindViaCommand(tool)
        ?? FindFromRegistry(tool)
        ?? FindFromCommonPaths(tool)
        ?? FindFromWinGetLinks(tool)
        ?? FindFromWinGetPackages(tool)
        ?? FindViaWhere(tool);

    public static string? FindWacli()
    {
        if (File.Exists(AppConfig.LocalWacliExe) && VerifyWacli(AppConfig.LocalWacliExe))
            return AppConfig.LocalWacliExe;

        return FindFromManifest("wacli")
               ?? FindViaCommand("wacli")
               ?? FindFromLegacyPaths()
               ?? FindFromWinGetPackages("wacli")
               ?? FindViaWhere("wacli");
    }

    public static bool IsValidToolPath(string tool, string path)
    {
        if (string.IsNullOrWhiteSpace(path) || !File.Exists(path))
            return false;

        return tool switch
        {
            "wacli" => VerifyWacli(path),
            "python" => VerifyPython(path),
            _ => VerifyGeneric(tool, path),
        };
    }

    public static bool VerifyWacli(string path) =>
        RunQuick(path, "--version") || RunQuick(path, "doctor");

    public static bool VerifyGeneric(string tool, string path)
    {
        var args = tool == "go" ? "version" : "--version";
        return RunQuick(path, args);
    }

    public static bool VerifyPython(string path) => RunQuick(path, "--version");

    public static string? GetVersion(string tool, string path)
    {
        try
        {
            using var proc = Process.Start(CreatePsi(path, tool == "go" ? "version" : "--version"));
            if (proc is null) return null;
            var line = proc.StandardOutput.ReadLine() ?? proc.StandardError.ReadLine();
            proc.WaitForExit(8000);
            return line?.Trim();
        }
        catch
        {
            return null;
        }
    }

    public static void ApplyDiscoveredPath(ProcessStartInfo psi)
    {
        var extra = new List<string>();
        foreach (var tool in new[] { "go", "gcc", "git" })
        {
            var path = Find(tool);
            if (path is null || path.Equals(tool, StringComparison.OrdinalIgnoreCase))
                continue;
            var dir = Path.GetDirectoryName(path);
            if (!string.IsNullOrEmpty(dir))
                extra.Add(dir);
        }

        foreach (var segment in GetExpandedPath().Split(';'))
        {
            var trimmed = segment.Trim();
            if (trimmed.Length > 0)
                extra.Add(trimmed);
        }

        psi.Environment["PATH"] = string.Join(';', extra.Distinct(StringComparer.OrdinalIgnoreCase));
    }

    public static string GetExpandedPath()
    {
        var parts = new List<string>();
        try
        {
            var machine = Registry.GetValue(
                @"HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
                "Path", "") as string;
            if (!string.IsNullOrWhiteSpace(machine))
                parts.Add(Environment.ExpandEnvironmentVariables(machine));
        }
        catch { /* ignore */ }

        try
        {
            var user = Registry.GetValue(@"HKEY_CURRENT_USER\Environment", "Path", "") as string;
            if (!string.IsNullOrWhiteSpace(user))
                parts.Add(Environment.ExpandEnvironmentVariables(user));
        }
        catch { /* ignore */ }

        var processPath = Environment.GetEnvironmentVariable("PATH");
        if (!string.IsNullOrWhiteSpace(processPath))
            parts.Add(processPath);

        return string.Join(';', parts.Distinct(StringComparer.OrdinalIgnoreCase));
    }

    public static bool IsWingetInstalled(string packageId)
    {
        try
        {
            using var proc = Process.Start(new ProcessStartInfo
            {
                FileName = "winget",
                Arguments = $"list --id {packageId} -e",
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true,
            });
            if (proc is null) return false;
            var output = proc.StandardOutput.ReadToEnd();
            proc.WaitForExit(15000);
            return proc.ExitCode == 0 && output.Contains(packageId, StringComparison.OrdinalIgnoreCase);
        }
        catch
        {
            return false;
        }
    }

    public static string? GetWingetPackageId(string tool) =>
        WingetPackages.TryGetValue(tool, out var pkg) ? pkg.Id : null;

    private static string? FindFromManifest(string tool)
    {
        if (!RuntimeEnvironment.Current.Tools.TryGetValue(tool, out var saved))
            return null;
        return IsValidToolPath(tool, saved.Path) ? saved.Path : null;
    }

    private static string? FindViaCommand(string tool)
    {
        if (!CanRunBare(tool))
            return null;
        return FindViaWhere(tool) ?? tool;
    }

    private static string? FindFromRegistry(string tool)
    {
        return tool switch
        {
            "git" => FindGitFromRegistry(),
            "go" => FindGoFromRegistry(),
            _ => null,
        };
    }

    private static string? FindGitFromRegistry()
    {
        var keys = new[]
        {
            @"HKEY_LOCAL_MACHINE\SOFTWARE\GitForWindows",
            @"HKEY_LOCAL_MACHINE\SOFTWARE\WOW6432Node\GitForWindows",
        };
        foreach (var key in keys)
        {
            var install = Registry.GetValue(key, "InstallPath", null) as string;
            if (string.IsNullOrWhiteSpace(install)) continue;
            var cmd = Path.Combine(install.TrimEnd('\\'), "cmd", "git.exe");
            if (File.Exists(cmd)) return cmd;
            var bin = Path.Combine(install.TrimEnd('\\'), "bin", "git.exe");
            if (File.Exists(bin)) return bin;
        }

        return FindFromUninstall("Git_is1", "git.exe");
    }

    private static string? FindGoFromRegistry()
    {
        var goRoot = Registry.GetValue(@"HKEY_LOCAL_MACHINE\SOFTWARE\Go", "InstallPath", null) as string
                     ?? Environment.GetEnvironmentVariable("GOROOT");
        if (!string.IsNullOrWhiteSpace(goRoot))
        {
            var exe = Path.Combine(goRoot.TrimEnd('\\'), "bin", "go.exe");
            if (File.Exists(exe)) return exe;
        }

        return FindFromUninstall("Go Programming Language", "go.exe")
               ?? FindFromUninstall("Go Programming Language 386", "go.exe");
    }

    private static string? FindFromUninstall(string nameHint, string exeName)
    {
        foreach (var root in new[] { Registry.LocalMachine, Registry.CurrentUser })
        {
            foreach (var sub in new[] { @"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", @"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall" })
            {
                try
                {
                    using var key = root.OpenSubKey(sub);
                    if (key is null) continue;
                    foreach (var subName in key.GetSubKeyNames())
                    {
                        using var app = key.OpenSubKey(subName);
                        var display = app?.GetValue("DisplayName") as string ?? "";
                        if (!display.Contains(nameHint, StringComparison.OrdinalIgnoreCase))
                            continue;
                        var loc = app?.GetValue("InstallLocation") as string;
                        if (string.IsNullOrWhiteSpace(loc)) continue;
                        var exe = Directory.GetFiles(loc, exeName, SearchOption.AllDirectories).FirstOrDefault();
                        if (exe is not null) return exe;
                    }
                }
                catch { /* ignore */ }
            }
        }

        return null;
    }

    private static string? FindFromCommonPaths(string tool)
    {
        var fileName = tool + ".exe";
        var localApp = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        var programFiles = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles);
        var programFilesX86 = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86);

        IEnumerable<string> candidates = tool switch
        {
            "go" =>
            [
                Path.Combine(programFiles, "Go", "bin", fileName),
                Path.Combine(localApp, "Programs", "Go", "bin", fileName),
            ],
            "gcc" =>
            [
                Path.Combine(programFiles, "mingw64", "bin", fileName),
                Path.Combine(programFiles, "WinLibs", "mingw64", "bin", fileName),
                Path.Combine(programFilesX86, "mingw-w64", "bin", fileName),
            ],
            "git" =>
            [
                Path.Combine(programFiles, "Git", "cmd", fileName),
                Path.Combine(programFiles, "Git", "bin", fileName),
            ],
            "python" =>
            [
                Path.Combine(localApp, "Programs", "Python", "Python312", fileName),
                Path.Combine(programFiles, "Python312", fileName),
            ],
            _ => [],
        };

        foreach (var path in candidates)
        {
            if (File.Exists(path))
                return path;
        }

        return null;
    }

    private static string? FindFromLegacyPaths()
    {
        var home = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
        var legacy = Path.Combine(home, ".local", "bin", "wacli.exe");
        return File.Exists(legacy) && VerifyWacli(legacy) ? legacy : null;
    }

    private static string? FindFromWinGetLinks(string tool)
    {
        var links = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "Microsoft", "WinGet", "Links");
        if (!Directory.Exists(links)) return null;
        var exe = Path.Combine(links, tool + ".exe");
        return File.Exists(exe) ? exe : null;
    }

    private static string? FindFromWinGetPackages(string tool)
    {
        var packagesRoot = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "Microsoft", "WinGet", "Packages");
        if (!Directory.Exists(packagesRoot)) return null;

        var fileName = tool + ".exe";
        try
        {
            return Directory.EnumerateFiles(packagesRoot, fileName, SearchOption.AllDirectories).FirstOrDefault();
        }
        catch
        {
            return null;
        }
    }

    private static string? FindViaWhere(string command)
    {
        try
        {
            using var proc = Process.Start(new ProcessStartInfo
            {
                FileName = "where.exe",
                Arguments = command,
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true,
            });
            if (proc is null) return null;
            var output = proc.StandardOutput.ReadToEnd();
            proc.WaitForExit(8000);
            if (proc.ExitCode != 0) return null;

            foreach (var line in output.Split('\n', StringSplitOptions.RemoveEmptyEntries))
            {
                var path = line.Trim();
                if (File.Exists(path))
                    return path;
            }
        }
        catch { /* ignore */ }

        return null;
    }

    public static string? FindPython() =>
        Find("python") ?? FindPyLauncher();

    private static string? FindPyLauncher()
    {
        try
        {
            using var proc = Process.Start(new ProcessStartInfo
            {
                FileName = "py",
                Arguments = "-3 -c \"import sys; print(sys.executable)\"",
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true,
            });
            if (proc is null) return null;
            var output = proc.StandardOutput.ReadToEnd().Trim();
            proc.WaitForExit(8000);
            return proc.ExitCode == 0 && File.Exists(output) ? output : null;
        }
        catch
        {
            return null;
        }
    }

    private static bool CanRunBare(string command)
    {
        try
        {
            using var proc = Process.Start(CreatePsi(command, command == "go" ? "version" : "--version"));
            if (proc is null) return false;
            proc.WaitForExit(8000);
            return proc.ExitCode == 0;
        }
        catch
        {
            return false;
        }
    }

    private static bool RunQuick(string exe, string args)
    {
        try
        {
            using var proc = Process.Start(CreatePsi(exe, args));
            if (proc is null) return false;
            proc.WaitForExit(15000);
            return proc.ExitCode == 0;
        }
        catch
        {
            return false;
        }
    }

    private static ProcessStartInfo CreatePsi(string file, string args)
    {
        var psi = new ProcessStartInfo
        {
            FileName = file,
            Arguments = args,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
        };
        psi.Environment["PATH"] = GetExpandedPath();
        return psi;
    }

    private sealed record WingetPackage(string Id, string Command);
}
