using PaddlePdfOcrApp.Models;
using System.Data;
using System.IO;
using System.Text.Json;

namespace PaddlePdfOcrApp.Services;

public sealed class TemplatePersistenceService
{
    private const string SerialColumnName = "序號";

    public void Save(string filePath, IReadOnlyList<OcrRegion> regions, DataTable resultTable)
    {
        var template = new RecognitionTemplate
        {
            Regions = regions.Select(r => new OcrRegion
            {
                Name = r.Name,
                X = r.X,
                Y = r.Y,
                Width = r.Width,
                Height = r.Height,
                Angle = r.Angle
            }).ToList(),
            Rows = ConvertRows(resultTable)
        };

        var json = JsonSerializer.Serialize(template, new JsonSerializerOptions { WriteIndented = true });
        File.WriteAllText(filePath, json);
    }

    public RecognitionTemplate Load(string filePath)
    {
        var json = File.ReadAllText(filePath);
        return JsonSerializer.Deserialize<RecognitionTemplate>(json) ?? new RecognitionTemplate();
    }

    public void FillDataTable(DataTable table, RecognitionTemplate template)
    {
        table.Rows.Clear();
        foreach (var row in template.Rows)
        {
            var dataRow = table.NewRow();
            dataRow[SerialColumnName] = row.Page;
            foreach (var pair in row.Values)
            {
                if (!table.Columns.Contains(pair.Key))
                {
                    table.Columns.Add(pair.Key, typeof(string));
                }
                dataRow[pair.Key] = pair.Value;
            }
            table.Rows.Add(dataRow);
        }
    }

    private static List<PageResultRow> ConvertRows(DataTable table)
    {
        var rows = new List<PageResultRow>();
        foreach (DataRow row in table.Rows)
        {
            var item = new PageResultRow
            {
                Page = row.Field<int>(SerialColumnName)
            };

            foreach (DataColumn column in table.Columns)
            {
                if (column.ColumnName == SerialColumnName)
                {
                    continue;
                }

                item.Values[column.ColumnName] = row[column]?.ToString() ?? string.Empty;
            }
            rows.Add(item);
        }
        return rows;
    }
}
