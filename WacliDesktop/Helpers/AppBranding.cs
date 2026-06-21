namespace WacliDesktop.Helpers;

public static class AppBranding
{
    public const string AppName = "赤瞳灵讯";
    public const string Tagline = "登录配对 · 消息同步 · 数据浏览 · SQLite 查询 · 命令工具";

    public static string ModuleWindowTitle(string module) => $"{AppName} · {module}";
}
