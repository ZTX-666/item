using System.Data;

namespace WacliDesktop.ApiHost.Helpers;

internal static class ApiJsonHelper
{
    public static object DataTableToPayload(DataTable table)
    {
        var columns = table.Columns.Cast<DataColumn>().Select(c => c.ColumnName).ToList();
        var rows = new List<Dictionary<string, object?>>();
        foreach (DataRow row in table.Rows)
        {
            var item = new Dictionary<string, object?>();
            foreach (var col in columns)
            {
                var value = row[col];
                item[col] = value == DBNull.Value ? null : value;
            }
            rows.Add(item);
        }

        return new
        {
            columns,
            rows,
            count = rows.Count,
        };
    }
}
