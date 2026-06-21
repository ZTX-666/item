using System.Windows;

namespace WacliDesktop.Services;

public sealed class ModuleWindowManager
{
    private readonly Dictionary<string, Window> _open = new();

    public void Open<T>(string key, Func<T> factory) where T : Window
    {
        if (_open.TryGetValue(key, out var existing) && existing.IsLoaded)
        {
            if (existing.WindowState == WindowState.Minimized)
                existing.WindowState = WindowState.Normal;
            existing.Activate();
            return;
        }

        var window = factory();
        _open[key] = window;
        window.Closed += (_, _) => _open.Remove(key);
        window.Show();
    }

    public void CloseAll()
    {
        foreach (var w in _open.Values.ToList())
            w.Close();
        _open.Clear();
    }
}
