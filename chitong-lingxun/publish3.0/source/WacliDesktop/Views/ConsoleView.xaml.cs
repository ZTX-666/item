using System.Windows;
using System.Windows.Controls;
using WacliDesktop.Services;

namespace WacliDesktop.Views;

public partial class ConsoleView : UserControl
{
    private readonly AppServices _app = AppServices.Instance;

    public ConsoleView()
    {
        InitializeComponent();
        Loaded += (_, _) => BuildQuickCommands();
    }

    private void BuildQuickCommands()
    {
        QuickCmdGroups.Items.Clear();
        foreach (var group in WacliQuickCommands.All)
        {
            var panel = new StackPanel { Margin = new Thickness(0, 0, 0, 6) };
            panel.Children.Add(new TextBlock
            {
                Text = group.Title,
                FontSize = 12,
                FontWeight = FontWeights.SemiBold,
                Foreground = (System.Windows.Media.Brush)FindResource("SgPrimaryBrush"),
                Margin = new Thickness(0, 0, 0, 2),
            });

            var wrap = new WrapPanel();
            foreach (var cmd in group.Commands)
            {
                var btn = new Button
                {
                    Content = cmd.Label,
                    Tag = cmd.Args,
                    Style = (Style)FindResource("CompactButton"),
                    ToolTip = cmd.Args,
                };
                btn.Click += QuickCmd_Click;
                wrap.Children.Add(btn);
            }
            panel.Children.Add(wrap);
            QuickCmdGroups.Items.Add(panel);
        }
    }

    private void QuickCmd_Click(object sender, RoutedEventArgs e)
    {
        if (sender is Button btn && btn.Tag is string tag)
        {
            CmdArgsInput.Text = tag;
            RunWacliArgs(tag.Split(' ', StringSplitOptions.RemoveEmptyEntries));
        }
    }

    private void BtnCmdRun_Click(object sender, RoutedEventArgs e)
    {
        var text = CmdArgsInput.Text.Trim();
        if (!string.IsNullOrEmpty(text))
            RunWacliArgs(text.Split(' ', StringSplitOptions.RemoveEmptyEntries));
    }

    private void RunWacliArgs(string[] args)
    {
        try
        {
            var result = _app.Wacli.Run(args);
            CmdOutput.Text = string.Join(Environment.NewLine + "---" + Environment.NewLine,
                new[] { result.Stdout, result.Stderr }.Where(s => !string.IsNullOrWhiteSpace(s)));
        }
        catch (Exception ex) { CmdOutput.Text = ex.Message; }
    }
}
