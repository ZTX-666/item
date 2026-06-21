using System.Diagnostics;
using System.IO;

namespace WacliDesktopLauncher;

internal static class Program
{
    private static int Main()
    {
        var launcherDir = AppContext.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        var parentDir = Path.GetDirectoryName(launcherDir);

        var candidates = new List<string>
        {
            Path.Combine(launcherDir, "portable", "WacliDesktop.exe"),
            Path.Combine(launcherDir, "ChitongLingxun-standalone.exe"),
            Path.Combine(launcherDir, "WacliDesktop.exe"),
        };

        if (parentDir is not null)
        {
            foreach (var ver in new[] { "publish3.0", "publish23", "publish22", "publish21", "publish20", "publish12", "publish11", "publish10", "publish9" })
            {
                candidates.Add(Path.Combine(parentDir, ver, "portable", "WacliDesktop.exe"));
                candidates.Add(Path.Combine(parentDir, ver, "ChitongLingxun-standalone.exe"));
            }
        }

        var home = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
        candidates.AddRange([
            Path.Combine(home, ".wacli", "publish11", "portable", "WacliDesktop.exe"),
            Path.Combine(home, ".wacli", "WacliDesktop", "publish11", "portable", "WacliDesktop.exe"),
            Path.Combine(home, ".wacli", "WacliDesktop", "publish10", "portable", "WacliDesktop.exe"),
        ]);

        foreach (var exe in candidates)
        {
            if (!File.Exists(exe))
                continue;

            Process.Start(new ProcessStartInfo
            {
                FileName = exe,
                WorkingDirectory = Path.GetDirectoryName(exe)!,
                UseShellExecute = true,
            });
            return 0;
        }

        Console.Error.WriteLine("赤瞳灵讯未找到。请运行 publish11\\start.bat 或 portable\\WacliDesktop.exe。");
        return 1;
    }
}
