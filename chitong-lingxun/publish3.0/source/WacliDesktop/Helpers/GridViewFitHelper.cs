using System.Windows;
using System.Windows.Controls;

namespace WacliDesktop.Helpers;

public static class GridViewFitHelper
{
    public static readonly DependencyProperty AutoFitLastColumnProperty =
        DependencyProperty.RegisterAttached(
            "AutoFitLastColumn",
            typeof(bool),
            typeof(GridViewFitHelper),
            new PropertyMetadata(false, OnAutoFitChanged));

    public static bool GetAutoFitLastColumn(DependencyObject obj) =>
        (bool)obj.GetValue(AutoFitLastColumnProperty);

    public static void SetAutoFitLastColumn(DependencyObject obj, bool value) =>
        obj.SetValue(AutoFitLastColumnProperty, value);

    private static void OnAutoFitChanged(DependencyObject d, DependencyPropertyChangedEventArgs e)
    {
        if (d is not ListView listView || e.NewValue is not true)
            return;

        listView.Loaded += (_, _) => FitLastColumn(listView);
        listView.SizeChanged += (_, _) => FitLastColumn(listView);
    }

    public static void FitLastColumn(ListView listView)
    {
        if (listView.View is not GridView gridView || gridView.Columns.Count == 0)
            return;

        listView.UpdateLayout();
        var available = listView.ActualWidth - 28;
        if (available <= 0)
            return;

        var fixedWidth = 0.0;
        for (var i = 0; i < gridView.Columns.Count - 1; i++)
            fixedWidth += gridView.Columns[i].ActualWidth;

        var last = gridView.Columns[^1];
        last.Width = Math.Max(80, available - fixedWidth);
    }
}
