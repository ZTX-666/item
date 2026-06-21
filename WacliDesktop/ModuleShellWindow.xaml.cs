using System.Windows;

using WacliDesktop.Helpers;

namespace WacliDesktop;

public partial class ModuleShellWindow : Window
{
    public ModuleShellWindow(string title, UIElement content, double width = 920, double height = 620)
    {
        InitializeComponent();
        Title = AppBranding.ModuleWindowTitle(title);
        ModuleTitle.Text = title;
        ModuleContent.Content = content;
        Width = width;
        Height = height;
        MinWidth = Math.Max(760, width * 0.75);
        MinHeight = Math.Max(520, height * 0.75);
        ResizeMode = ResizeMode.CanResize;
        WindowStartupLocation = WindowStartupLocation.CenterScreen;
    }

    private void Close_Click(object sender, RoutedEventArgs e) => Close();
}
