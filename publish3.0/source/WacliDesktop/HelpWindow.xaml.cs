using System.Windows;
using WacliDesktop.Helpers;
using WacliDesktop.Services;

namespace WacliDesktop;

public partial class HelpWindow : Window
{
    public HelpWindow()
    {
        InitializeComponent();
        HelpText.Text = HelpContent.Manual
            .Replace("%RUNTIME_DIR%", AppConfig.RuntimeDir, StringComparison.OrdinalIgnoreCase);
    }

    private void Close_Click(object sender, RoutedEventArgs e) => Close();
}
