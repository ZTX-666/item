using System.Data;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Data;
using WacliDesktop.Models;
using WacliDesktop.Services;

namespace WacliDesktop.Views;

public partial class SqlView : UserControl
{
    private readonly AppServices _app = AppServices.Instance;

    public SqlView()
    {
        InitializeComponent();
        Loaded += (_, _) =>
        {
            try { TableList.ItemsSource = _app.Sqlite.ListTables(); }
            catch (Exception ex) { SchemaBox.Text = ex.Message; }
        };
    }

    private void TableList_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (TableList.SelectedItem is not string table) return;
        try
        {
            var schema = _app.Sqlite.GetSchema(table);
            SchemaBox.Text = string.Join(Environment.NewLine,
                schema.Select(c => $"{c.Name} {c.Type}{(c.Pk ? " PK" : "")}"));
            SqlInput.Text = table.Equals("messages", StringComparison.OrdinalIgnoreCase)
                ? SqliteQueryService.MessagesDetailSql + " LIMIT 50"
                : $"SELECT * FROM {table} LIMIT 20";
        }
        catch (Exception ex) { SchemaBox.Text = ex.Message; }
    }

    private static bool IsMessageResult(DataTable table) =>
        table.Columns.Contains("msg_id") || table.Columns.Contains("sender_jid") ||
        table.Columns.Contains("whatsapp_id");

    private void BindSqlResults(DataTable table)
    {
        if (IsMessageResult(table))
        {
            SqlGrid.Visibility = Visibility.Collapsed;
            SqlMessageListView.Visibility = Visibility.Visible;
            var rows = MessageRowMapper.FromDataTable(table, _app.Thumbnails);
            SqlMessageListView.ItemsSource = rows;
            if (rows.Count > 0)
            {
                SqlMessageListView.SelectedIndex = 0;
                SqlPreviewImage.Source = rows[0].Thumbnail;
            }
            else SqlPreviewImage.Source = null;
        }
        else
        {
            SqlMessageListView.Visibility = Visibility.Collapsed;
            SqlGrid.Visibility = Visibility.Visible;
            BindDataGrid(table);
            SqlPreviewImage.Source = null;
        }
    }

    private void BindDataGrid(DataTable table)
    {
        SqlGrid.Columns.Clear();
        var cellStyle = new Style(typeof(TextBlock));
        cellStyle.Setters.Add(new Setter(TextBlock.TextTrimmingProperty, TextTrimming.CharacterEllipsis));
        cellStyle.Setters.Add(new Setter(TextBlock.TextWrappingProperty, TextWrapping.NoWrap));

        foreach (DataColumn col in table.Columns)
        {
            SqlGrid.Columns.Add(new DataGridTextColumn
            {
                Header = col.ColumnName,
                Binding = new Binding(col.ColumnName) { Mode = BindingMode.OneWay },
                Width = new DataGridLength(1, DataGridLengthUnitType.Star),
                ElementStyle = cellStyle,
            });
        }
        SqlGrid.ItemsSource = table.DefaultView;
    }

    private void SqlMessageListView_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (SqlMessageListView.SelectedItem is MessageRowViewModel row)
            SqlPreviewImage.Source = row.Thumbnail;
    }

    private void SqlGrid_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (SqlGrid.SelectedItem is DataRowView drv)
            SqlPreviewImage.Source = MessageRowMapper.FromDataRow(drv.Row, _app.Thumbnails).Thumbnail;
    }

    private void BtnSqlRun_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            if (!int.TryParse(SqlLimitInput.Text, out var limit)) limit = 100;
            BindSqlResults(_app.Sqlite.RunSelect(SqlInput.Text, limit));
        }
        catch (Exception ex) { MessageBox.Show(ex.Message, "SQL 错误"); }
    }
}
