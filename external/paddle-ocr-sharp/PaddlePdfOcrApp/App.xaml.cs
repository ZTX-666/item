using System.Windows;
using PaddlePdfOcrApp.Services;

namespace PaddlePdfOcrApp;

/// <summary>
/// Interaction logic for App.xaml
/// </summary>
public partial class App : Application
{
    protected override void OnStartup(StartupEventArgs e)
    {
        CrashLogger.Initialize(AppContext.BaseDirectory);

        DispatcherUnhandledException += (_, args) =>
        {
            CrashLogger.WriteError("DispatcherUnhandledException", args.Exception);
            args.Handled = false;
        };
        AppDomain.CurrentDomain.UnhandledException += (_, args) =>
        {
            var ex = args.ExceptionObject as Exception;
            CrashLogger.WriteError($"AppDomain.UnhandledException (IsTerminating={args.IsTerminating})", ex);
        };
        TaskScheduler.UnobservedTaskException += (_, args) =>
        {
            CrashLogger.WriteError("TaskScheduler.UnobservedTaskException", args.Exception);
            args.SetObserved();
        };

        var window = new MainWindow();
        window.Show();
        base.OnStartup(e);
    }
}

