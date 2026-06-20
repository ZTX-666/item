using Microsoft.Win32;
using PaddlePdfOcrApp.Models;
using PaddlePdfOcrApp.Services;
using System.Diagnostics;
using System.Data;
using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Media3D;
using System.Windows.Media.Imaging;
using System.Windows.Threading;
using Border = System.Windows.Controls.Border;

namespace PaddlePdfOcrApp;

public partial class MainWindow : Window
{
    private const int CanvasWidth = 900;
    private const int CanvasHeight = 1200;
    private const string SerialColumnName = "序號";

    private readonly AppConfigService _configService;
    private readonly PdfRenderService _pdfRenderService;
    private readonly OcrEngineService _ocrEngineService;
    private readonly OcrWorkflowService _ocrWorkflowService;
    private readonly ExcelExportService _excelExportService;
    private readonly ModelPathValidator _modelPathValidator;
    private readonly TemplatePersistenceService _templatePersistenceService;
    private AppConfig _appConfig;

    private string? _pdfPath;
    private PdfPageData? _currentPage;
    private int _pageCount;
    private int _currentPageIndex;

    private CancellationTokenSource? _batchCts;

    private readonly List<OcrRegion> _regions = [];
    private readonly Dictionary<OcrRegion, DragState> _dragStates = [];
    private readonly DataTable _resultTable = new("OCR");
    private bool _isBusy;
    private bool _isPanning;
    private Point _panStartPoint;
    private double _panStartX;
    private double _panStartY;
    private double _pdfZoom = 1.0;

    public MainWindow()
    {
        _configService = new AppConfigService(AppContext.BaseDirectory);
        _pdfRenderService = new PdfRenderService();
        _ocrEngineService = new OcrEngineService(CanvasWidth, CanvasHeight);
        _ocrWorkflowService = new OcrWorkflowService(_pdfRenderService, _ocrEngineService);
        _excelExportService = new ExcelExportService();
        _modelPathValidator = new ModelPathValidator();
        _templatePersistenceService = new TemplatePersistenceService();
        _appConfig = _configService.Load();
        TrySetDefaultModelPath();

        InitializeComponent();
        InitializeResultTable();
        SyncResultGridColumns();
        ResultGrid.ItemsSource = _resultTable.DefaultView;
        ApplyUiState();
    }

    private void InitializeResultTable()
    {
        _resultTable.Columns.Add(SerialColumnName, typeof(int));
    }

    private void ImportPdf_OnClick(object sender, RoutedEventArgs e)
    {
        var dialog = new OpenFileDialog
        {
            Filter = "PDF檔案|*.pdf",
            Multiselect = false
        };
        if (dialog.ShowDialog() != true)
        {
            return;
        }

        _pdfPath = dialog.FileName;
        _currentPageIndex = 0;
        RenderPage(0);
        PopulatePageRows();
        StatusText.Text = $"已載入：{System.IO.Path.GetFileName(_pdfPath)}";
    }

    private void RenderPage(int pageIndex)
    {
        if (string.IsNullOrWhiteSpace(_pdfPath))
        {
            return;
        }
        try
        {
            _currentPage = _pdfRenderService.RenderPage(_pdfPath, pageIndex, _appConfig.RenderWidth, _appConfig.RenderHeight);
            _currentPageIndex = _currentPage.PageIndex;
            _pageCount = _currentPage.PageCount;

            var bmp = BitmapSource.Create(
                _currentPage.Width,
                _currentPage.Height,
                96,
                96,
                System.Windows.Media.PixelFormats.Bgra32,
                null,
                _currentPage.Pixels,
                _currentPage.Width * 4);
            PdfPageImage.Source = bmp;

            PageIndexBox.Text = (_currentPageIndex + 1).ToString();
            PageInfoText.Text = $"/ {_pageCount}";
            RedrawRegions();
        }
        catch (Exception ex)
        {
            CrashLogger.WriteError($"RenderPage failed. pageIndex={pageIndex}", ex);
            MessageBox.Show($"頁面渲染失敗：{ex.Message}", "錯誤", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private void AddRegion_OnClick(object sender, RoutedEventArgs e)
    {
        if (_currentPage == null)
        {
            StatusText.Text = "請先導入PDF。";
            return;
        }

        const double defaultWidth = 180;
        const double defaultHeight = 80;
        var region = new OcrRegion
        {
            Name = $"欄位{_regions.Count + 1}",
            X = (CanvasWidth - defaultWidth) / 2,
            Y = (CanvasHeight - defaultHeight) / 2,
            Width = defaultWidth,
            Height = defaultHeight
        };

        _regions.Add(region);
        EnsureResultColumn(region.Name);
        RedrawRegions();
        StatusText.Text = $"已新增識別框：{region.Name}（按住Ctrl+滾輪可旋轉）";
    }

    private void RedrawRegions()
    {
        RegionCanvas.Children.Clear();
        foreach (var region in _regions)
        {
            var regionCanvas = new Canvas
            {
                Width = region.Width,
                Height = region.Height,
                Cursor = Cursors.SizeAll,
                Tag = region,
                RenderTransformOrigin = new Point(0.5, 0.5),
                RenderTransform = new RotateTransform(region.Angle)
            };

            var border = new Border
            {
                Width = region.Width,
                Height = region.Height,
                BorderBrush = System.Windows.Media.Brushes.DeepSkyBlue,
                BorderThickness = new Thickness(2),
                Background = new System.Windows.Media.SolidColorBrush(System.Windows.Media.Color.FromArgb(30, 0, 191, 255))
            };

            var label = new TextBlock
            {
                Text = $"{region.Name} ({region.Angle:F0}°)",
                Background = System.Windows.Media.Brushes.DeepSkyBlue,
                Foreground = System.Windows.Media.Brushes.White,
                Padding = new Thickness(4, 1, 4, 1),
                FontSize = 12
            };

            var resizeThumb = new Thumb
            {
                Width = 16,
                Height = 16,
                Cursor = Cursors.SizeNWSE,
                Background = System.Windows.Media.Brushes.DeepSkyBlue,
                Tag = region
            };

            regionCanvas.Children.Add(border);
            regionCanvas.Children.Add(label);
            regionCanvas.Children.Add(resizeThumb);
            Canvas.SetLeft(label, 0);
            Canvas.SetTop(label, 0);
            Canvas.SetLeft(resizeThumb, region.Width - resizeThumb.Width);
            Canvas.SetTop(resizeThumb, region.Height - resizeThumb.Height);

            regionCanvas.MouseLeftButtonDown += RegionRect_MouseLeftButtonDown;
            regionCanvas.MouseMove += RegionRect_MouseMove;
            regionCanvas.MouseLeftButtonUp += RegionRect_MouseLeftButtonUp;
            regionCanvas.MouseWheel += RegionRect_MouseWheel;
            resizeThumb.DragDelta += ResizeThumb_DragDelta;

            Canvas.SetLeft(regionCanvas, region.X);
            Canvas.SetTop(regionCanvas, region.Y);
            RegionCanvas.Children.Add(regionCanvas);
        }
    }

    private void RegionRect_MouseLeftButtonDown(object sender, MouseButtonEventArgs e)
    {
        if (sender is not Canvas regionCanvas || regionCanvas.Tag is not OcrRegion region)
        {
            return;
        }

        var p = e.GetPosition(RegionCanvas);
        _dragStates[region] = new DragState
        {
            IsDragging = true,
            DragOffset = new Point(p.X - region.X, p.Y - region.Y)
        };
        regionCanvas.CaptureMouse();
        e.Handled = true;
    }

    private void RegionRect_MouseMove(object sender, MouseEventArgs e)
    {
        if (sender is not Canvas regionCanvas || regionCanvas.Tag is not OcrRegion region)
        {
            return;
        }

        if (!_dragStates.TryGetValue(region, out var state) || !state.IsDragging)
        {
            return;
        }

        var pos = e.GetPosition(RegionCanvas);
        region.X = Math.Clamp(pos.X - state.DragOffset.X, 0, CanvasWidth - region.Width);
        region.Y = Math.Clamp(pos.Y - state.DragOffset.Y, 0, CanvasHeight - region.Height);
        Canvas.SetLeft(regionCanvas, region.X);
        Canvas.SetTop(regionCanvas, region.Y);
    }

    private void RegionRect_MouseLeftButtonUp(object sender, MouseButtonEventArgs e)
    {
        if (sender is not Canvas regionCanvas || regionCanvas.Tag is not OcrRegion region)
        {
            return;
        }

        _dragStates[region] = new DragState { IsDragging = false, DragOffset = default };
        regionCanvas.ReleaseMouseCapture();
        e.Handled = true;
    }

    private void RegionRect_MouseWheel(object sender, MouseWheelEventArgs e)
    {
        if (sender is not Canvas regionCanvas || regionCanvas.Tag is not OcrRegion region)
        {
            return;
        }

        if ((Keyboard.Modifiers & ModifierKeys.Control) == 0)
        {
            return;
        }

        region.Angle += e.Delta > 0 ? 2d : -2d;
        if (region.Angle > 180d)
        {
            region.Angle -= 360d;
        }
        else if (region.Angle < -180d)
        {
            region.Angle += 360d;
        }

        RedrawRegions();
        e.Handled = true;
    }

    private void ResizeThumb_DragDelta(object sender, DragDeltaEventArgs e)
    {
        if (sender is not Thumb thumb || thumb.Tag is not OcrRegion region || thumb.Parent is not Canvas regionCanvas)
        {
            return;
        }

        region.Width = Math.Clamp(region.Width + e.HorizontalChange, 30, CanvasWidth - region.X);
        region.Height = Math.Clamp(region.Height + e.VerticalChange, 30, CanvasHeight - region.Y);
        regionCanvas.Width = region.Width;
        regionCanvas.Height = region.Height;

        if (regionCanvas.Children[0] is Border border)
        {
            border.Width = region.Width;
            border.Height = region.Height;
        }

        Canvas.SetLeft(thumb, region.Width - thumb.Width);
        Canvas.SetTop(thumb, region.Height - thumb.Height);
    }

    private void EnsureResultColumn(string columnName)
    {
        if (!_resultTable.Columns.Contains(columnName))
        {
            _resultTable.Columns.Add(columnName, typeof(string));
            SyncResultGridColumns();
        }
    }

    private void SyncResultGridColumns()
    {
        ResultGrid.Columns.Clear();
        foreach (DataColumn column in _resultTable.Columns)
        {
            var width = string.Equals(column.ColumnName, SerialColumnName, StringComparison.Ordinal)
                ? 60d
                : 180d;
            ResultGrid.Columns.Add(new DataGridTextColumn
            {
                Header = column.ColumnName,
                Binding = new System.Windows.Data.Binding($"[{column.ColumnName}]"),
                Width = width
            });
        }
    }

    private void ResultGrid_MouseDoubleClick(object sender, MouseButtonEventArgs e)
    {
        var current = e.OriginalSource as DependencyObject;
        while (current != null && current is not DataGridColumnHeader)
        {
            current = GetParentObject(current);
        }

        if (current is not DataGridColumnHeader header)
        {
            return;
        }

        var oldName = header.Column?.Header?.ToString();
        if (string.IsNullOrWhiteSpace(oldName) || string.Equals(oldName, SerialColumnName, StringComparison.Ordinal))
        {
            return;
        }
        CrashLogger.WriteInfo($"Column rename requested. oldName={oldName}");

        // Avoid DataGrid re-entrancy while handling a double-click event.
        Dispatcher.BeginInvoke(new Action(() =>
        {
            var newName = ShowRenameDialog(oldName);
            if (string.IsNullOrWhiteSpace(newName) || string.Equals(newName, oldName, StringComparison.Ordinal))
            {
                CrashLogger.WriteInfo($"Column rename cancelled. oldName={oldName}");
                return;
            }

            try
            {
                if (_resultTable.Columns.Contains(newName))
                {
                    MessageBox.Show("該列名已存在，請使用其他名稱。", "提示", MessageBoxButton.OK, MessageBoxImage.Information);
                    CrashLogger.WriteInfo($"Column rename rejected. duplicateName={newName}");
                    return;
                }

                var column = _resultTable.Columns[oldName];
                if (column == null)
                {
                    return;
                }

                column.ColumnName = newName;
                foreach (var region in _regions.Where(r => string.Equals(r.Name, oldName, StringComparison.Ordinal)))
                {
                    region.Name = newName;
                }

                SyncResultGridColumns();
                RedrawRegions();
                ResultGrid.Items.Refresh();
                CrashLogger.WriteInfo($"Column rename success. oldName={oldName}, newName={newName}");
            }
            catch (Exception ex)
            {
                CrashLogger.WriteError($"Column rename failed. oldName={oldName}, newName={newName}", ex);
                MessageBox.Show($"修改列名失敗：{ex.Message}", "錯誤", MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }), DispatcherPriority.Background);
    }

    private static DependencyObject? GetParentObject(DependencyObject child)
    {
        if (child is Visual || child is Visual3D)
        {
            return VisualTreeHelper.GetParent(child);
        }

        if (child is FrameworkContentElement contentElement)
        {
            return contentElement.Parent;
        }

        return null;
    }

    private static string ShowRenameDialog(string oldName)
    {
        var dialog = new Window
        {
            Title = "修改列名",
            Width = 360,
            Height = 160,
            ResizeMode = ResizeMode.NoResize,
            WindowStartupLocation = WindowStartupLocation.CenterOwner,
            ShowInTaskbar = false
        };

        var root = new Grid { Margin = new Thickness(12) };
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });

        var label = new TextBlock { Text = "請輸入新的列名：" };
        Grid.SetRow(label, 0);

        var input = new TextBox { Text = oldName, Margin = new Thickness(0, 8, 0, 8) };
        Grid.SetRow(input, 1);

        var btnPanel = new StackPanel { Orientation = Orientation.Horizontal, HorizontalAlignment = HorizontalAlignment.Right };
        var okBtn = new Button { Content = "確定", Width = 70, Margin = new Thickness(0, 0, 8, 0), IsDefault = true };
        var cancelBtn = new Button { Content = "取消", Width = 70, IsCancel = true };
        btnPanel.Children.Add(okBtn);
        btnPanel.Children.Add(cancelBtn);
        Grid.SetRow(btnPanel, 2);

        root.Children.Add(label);
        root.Children.Add(input);
        root.Children.Add(btnPanel);
        dialog.Content = root;

        okBtn.Click += (_, _) => dialog.DialogResult = true;
        cancelBtn.Click += (_, _) => dialog.DialogResult = false;

        var owner = Application.Current?.Windows.OfType<Window>().FirstOrDefault(w => w.IsActive);
        if (owner != null)
        {
            dialog.Owner = owner;
        }

        var result = dialog.ShowDialog();
        return result == true ? input.Text.Trim() : oldName;
    }

    private void PreviewCrop_OnClick(object sender, RoutedEventArgs e)
    {
        if (_currentPage == null || _regions.Count == 0)
        {
            MessageBox.Show("請先導入PDF並添加識別框。", "提示", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }
        try
        {
            var tabControl = new TabControl();
            foreach (var region in _regions)
            {
                FrameworkElement content;
                try
                {
                    var image = new Image
                    {
                        Source = _ocrEngineService.CreateCropPreview(_currentPage, region),
                        Stretch = Stretch.Uniform,
                        Margin = new Thickness(8)
                    };

                    content = new ScrollViewer
                    {
                        HorizontalScrollBarVisibility = ScrollBarVisibility.Auto,
                        VerticalScrollBarVisibility = ScrollBarVisibility.Auto,
                        Content = image
                    };
                }
                catch (Exception ex)
                {
                    CrashLogger.WriteError($"CreateCropPreview failed. region={region.Name}", ex);
                    content = new TextBlock
                    {
                        Text = $"預覽失敗：{ex.Message}",
                        Foreground = Brushes.Red,
                        Margin = new Thickness(12)
                    };
                }

                tabControl.Items.Add(new TabItem
                {
                    Header = region.Name,
                    Content = content
                });
            }

            var previewWin = new Window
            {
                Title = $"裁剪預覽 - 第 {_currentPageIndex + 1} 頁",
                Width = 900,
                Height = 700,
                Content = tabControl,
                Owner = this,
                WindowStartupLocation = WindowStartupLocation.CenterOwner
            };
            previewWin.ShowDialog();
        }
        catch (Exception ex)
        {
            CrashLogger.WriteError("PreviewCrop_OnClick failed", ex);
            MessageBox.Show($"裁剪預覽失敗：{ex.Message}", "錯誤", MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private void ZoomIn_OnClick(object sender, RoutedEventArgs e)
    {
        SetPdfZoom(_pdfZoom + 0.1);
    }

    private void ZoomOut_OnClick(object sender, RoutedEventArgs e)
    {
        SetPdfZoom(_pdfZoom - 0.1);
    }

    private void ZoomReset_OnClick(object sender, RoutedEventArgs e)
    {
        SetPdfZoom(1.0);
    }

    private void SetPdfZoom(double zoom)
    {
        _pdfZoom = Math.Clamp(zoom, 0.5, 3.0);
        PdfZoomTransform.ScaleX = _pdfZoom;
        PdfZoomTransform.ScaleY = _pdfZoom;
        if (Math.Abs(_pdfZoom - 1.0) < 0.001)
        {
            PdfPanTransform.X = 0;
            PdfPanTransform.Y = 0;
            _isPanning = false;
            PdfViewport.ReleaseMouseCapture();
        }

        ApplyUiState();
    }

    private void PdfViewport_MouseLeftButtonDown(object sender, MouseButtonEventArgs e)
    {
        if (_pdfZoom <= 1.0)
        {
            return;
        }

        var source = e.OriginalSource as DependencyObject;
        if (source == null)
        {
            return;
        }

        // Only pan when pointer is on actual PDF display zone.
        if (!IsDescendantOf(source, PdfViewbox))
        {
            return;
        }

        // Region operation always has higher priority than PDF panning.
        if (IsRegionElement(source))
        {
            return;
        }

        _isPanning = true;
        _panStartPoint = e.GetPosition(PdfViewport);
        _panStartX = PdfPanTransform.X;
        _panStartY = PdfPanTransform.Y;
        PdfViewport.CaptureMouse();
        PdfViewport.Cursor = Cursors.SizeAll;
        e.Handled = true;
    }

    private void PdfViewport_MouseMove(object sender, MouseEventArgs e)
    {
        if (!_isPanning || _pdfZoom <= 1.0)
        {
            return;
        }

        var current = e.GetPosition(PdfViewport);
        var delta = current - _panStartPoint;
        PdfPanTransform.X = _panStartX + delta.X;
        PdfPanTransform.Y = _panStartY + delta.Y;
    }

    private void PdfViewport_MouseLeftButtonUp(object sender, MouseButtonEventArgs e)
    {
        if (!_isPanning)
        {
            return;
        }

        _isPanning = false;
        PdfViewport.ReleaseMouseCapture();
        PdfViewport.Cursor = Cursors.Arrow;
        e.Handled = true;
    }

    private static bool IsDescendantOf(DependencyObject? child, DependencyObject parent)
    {
        var current = child;
        while (current != null)
        {
            if (ReferenceEquals(current, parent))
            {
                return true;
            }
            current = GetParentObject(current);
        }

        return false;
    }

    private static bool IsRegionElement(DependencyObject child)
    {
        var current = child;
        while (current != null)
        {
            if (current is FrameworkElement fe)
            {
                if (fe.Tag is OcrRegion)
                {
                    return true;
                }
            }
            current = GetParentObject(current);
        }

        return false;
    }

    private void ApplyUiState()
    {
        var isOneToOne = Math.Abs(_pdfZoom - 1.0) < 0.001;
        var canUseCoordinateActions = !_isBusy && isOneToOne;

        ImportPdfButton.IsEnabled = !_isBusy;
        UsageGuideButton.IsEnabled = !_isBusy;
        EnvironmentSetupButton.IsEnabled = !_isBusy;
        ExportExcelButton.IsEnabled = !_isBusy;

        AddRegionButton.IsEnabled = canUseCoordinateActions;
        PreviewCropButton.IsEnabled = canUseCoordinateActions;
        RecognizePageButton.IsEnabled = canUseCoordinateActions;
        RecognizeAllButton.IsEnabled = canUseCoordinateActions;
        SaveTemplateButton.IsEnabled = canUseCoordinateActions;
        LoadTemplateButton.IsEnabled = canUseCoordinateActions;

        CancelBatchButton.IsEnabled = _isBusy;
    }

    private void PopulatePageRows()
    {
        _resultTable.Rows.Clear();
        for (var pageNumber = 1; pageNumber <= _pageCount; pageNumber++)
        {
            var row = _resultTable.NewRow();
            row[SerialColumnName] = pageNumber;
            _resultTable.Rows.Add(row);
        }
    }

    private DataRow? FindRowByPageNumber(int pageNumber)
    {
        foreach (DataRow row in _resultTable.Rows)
        {
            if ((int)row[SerialColumnName] == pageNumber)
            {
                return row;
            }
        }
        return null;
    }

    private void ApplyRecognitionResult(PageRecognitionResult result)
    {
        var row = FindRowByPageNumber(result.PageNumber);
        if (row == null)
        {
            row = _resultTable.NewRow();
            row[SerialColumnName] = result.PageNumber;
            _resultTable.Rows.Add(row);
        }

        foreach (var pair in result.Values)
        {
            EnsureResultColumn(pair.Key);
            row[pair.Key] = pair.Value;
        }
    }

    private async void RecognizePage_OnClick(object sender, RoutedEventArgs e)
    {
        if (_currentPage == null || _regions.Count == 0)
        {
            StatusText.Text = "請先導入PDF並添加識別框。";
            return;
        }

        try
        {
            if (string.IsNullOrWhiteSpace(_appConfig.PythonExePath) || !File.Exists(_appConfig.PythonExePath))
            {
                MessageBox.Show(
                    "找不到可用的 Python。請點「一鍵配置環境」，或安裝 Python 後於 appsettings.local.json 設定 PythonExePath，或將 python_portable 置於程式 exe 同目錄。",
                    "OCR配置錯誤",
                    MessageBoxButton.OK,
                    MessageBoxImage.Warning);
                return;
            }
            _ocrEngineService.EnsureInitialized(_appConfig.PythonExePath, _appConfig.FastMode);
        }
        catch (Exception ex)
        {
            MessageBox.Show(FormatOcrInitFailureMessage(ex), "錯誤", MessageBoxButton.OK, MessageBoxImage.Error);
            return;
        }

        SetBusyState(true);
        try
        {
            var result = await Task.Run(() => _ocrWorkflowService.RecognizeSinglePage(_currentPage, _regions));
            ApplyRecognitionResult(result);
            ResultGrid.Items.Refresh();
            StatusText.Text = $"第 {_currentPageIndex + 1} 頁識別完成";
        }
        catch (Exception ex)
        {
            MessageBox.Show($"識別失敗：{ex.Message}", "錯誤", MessageBoxButton.OK, MessageBoxImage.Error);
            StatusText.Text = "識別失敗";
        }
        finally
        {
            SetBusyState(false);
        }
    }

    private void ExportExcel_OnClick(object sender, RoutedEventArgs e)
    {
        if (_resultTable.Rows.Count == 0)
        {
            StatusText.Text = "沒有可導出的識別結果。";
            return;
        }

        var dialog = new SaveFileDialog
        {
            Filter = "Excel 檔案|*.xlsx",
            FileName = "ocr_result.xlsx"
        };

        if (dialog.ShowDialog() != true)
        {
            return;
        }

        _excelExportService.Export(_resultTable, dialog.FileName);
        StatusText.Text = $"已導出：{System.IO.Path.GetFileName(dialog.FileName)}";
    }

    private void UsageGuide_OnClick(object sender, RoutedEventArgs e)
    {
        const string guide = """
【地盤票據識別助手 - 使用教學】

一、基礎流程
1) 點擊「導入 PDF」選擇票據檔案。
2) 點擊「新增識別框」新增欄位框（可拖動位置、右下角縮放）。
3) 如票據傾斜，按住 Ctrl + 滾輪旋轉識別框角度。
4) 點擊「識別當前頁」識別當前頁內容。
5) 點擊「導出 Excel」導出右側識別結果。

二、批量識別（推薦）
1) 先在第一頁調整好所有識別框位置與大小。
2) 點擊「批量識別」自動按頁識別並回填右側表格。
3) 識別過程中可點擊「取消批量」中止任務。
4) 完成後點擊「導出 Excel」導出整批資料。

三、模板功能
1) 點擊「儲存模板」將當前識別框佈局和欄位儲存為模板。
2) 下次同版式票據，點擊「載入模板」可快速復用。

四、輔助功能
1) 雙擊右側欄位列名可改名，左側框名會同步。
2) 點擊「裁剪預覽」可查看每個識別框實際送 OCR 的圖像。

五、識別建議
1) 手寫內容建議框稍大一些，避免切邊。
2) 框內盡量只包含目標欄位，減少章、線條干擾。
3) 模糊頁面可先調整框位置後再進行批量識別。

六、一鍵配置環境（建議）
1) 點「一鍵配置環境」：可下載並安裝 .NET 8 Desktop Runtime（僅「框架依賴」小體積版需要，需管理員 UAC），並在程式目錄建立 python_portable 與 OCR 依賴。
2) 若電腦尚未安裝 .NET、無法啟動程式：請以系統管理員身分執行與 exe 同目錄的 install-environment.ps1，完成後再開啟本程式。
3) 進階：亦可在開發機執行 tools\Prepare-PythonPortable.ps1，將產生的 python_portable 與發佈檔一併複製。
""";

        MessageBox.Show(guide, "使用教學", MessageBoxButton.OK, MessageBoxImage.Information);
    }

    private void EnvironmentSetup_OnClick(object sender, RoutedEventArgs e)
    {
        var win = new EnvironmentSetupWindow(AppContext.BaseDirectory)
        {
            Owner = this
        };
        if (win.ShowDialog() != true || string.IsNullOrWhiteSpace(win.InstalledPythonPath))
        {
            return;
        }

        _appConfig.PythonExePath = win.InstalledPythonPath;
        _configService.Save(_appConfig);
        TrySetDefaultModelPath();
        try
        {
            _ocrEngineService.EnsureInitialized(_appConfig.PythonExePath, _appConfig.FastMode);
        }
        catch (Exception ex)
        {
            CrashLogger.WriteError("環境配置後 OCR 初始化", ex);
            MessageBox.Show(FormatOcrInitFailureMessage(ex), "提示", MessageBoxButton.OK, MessageBoxImage.Warning);
        }

        StatusText.Text = "環境已更新，可進行識別。";
    }

    private void PrevPage_OnClick(object sender, RoutedEventArgs e)
    {
        if (_currentPageIndex > 0)
        {
            RenderPage(_currentPageIndex - 1);
        }
    }

    private void NextPage_OnClick(object sender, RoutedEventArgs e)
    {
        if (_currentPageIndex < _pageCount - 1)
        {
            RenderPage(_currentPageIndex + 1);
        }
    }

    private void JumpPage_OnClick(object sender, RoutedEventArgs e)
    {
        if (!int.TryParse(PageIndexBox.Text, out var targetPage))
        {
            StatusText.Text = "頁碼格式錯誤。";
            return;
        }

        targetPage = Math.Clamp(targetPage, 1, _pageCount);
        RenderPage(targetPage - 1);
    }

    protected override void OnClosed(EventArgs e)
    {
        _ocrEngineService.Dispose();
        base.OnClosed(e);
    }

    private void TrySetDefaultModelPath()
    {
        var resolvedPythonPath = ResolvePythonExePath(_appConfig.PythonExePath);
        if (!string.Equals(resolvedPythonPath, _appConfig.PythonExePath, StringComparison.OrdinalIgnoreCase))
        {
            _appConfig.PythonExePath = resolvedPythonPath;
            _configService.Save(_appConfig);
        }

        if (!string.IsNullOrWhiteSpace(_appConfig.ModelRootPath))
        {
            return;
        }

        var candidate = Path.Combine(AppContext.BaseDirectory, "inference");
        if (Directory.Exists(candidate))
        {
            _appConfig.ModelRootPath = candidate;
            _configService.Save(_appConfig);
        }
    }

    private static string? ResolvePythonExePath(string? configuredPath)
    {
        if (!string.IsNullOrWhiteSpace(configuredPath) && File.Exists(configuredPath))
        {
            return configuredPath;
        }

        var bundled = Path.Combine(GetExecutableDirectory(), "python_portable", "python.exe");
        if (File.Exists(bundled))
        {
            return bundled;
        }

        var candidates = new[]
        {
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "Python", "Python311", "python.exe"),
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Microsoft", "WindowsApps", "python.exe")
        };

        foreach (var candidate in candidates)
        {
            if (File.Exists(candidate))
            {
                return candidate;
            }
        }

        return TryResolvePythonFromCommand();
    }

    /// <summary>Directory containing the app executable (works for single-file publish).</summary>
    private static string GetExecutableDirectory()
    {
        var processPath = Environment.ProcessPath;
        if (!string.IsNullOrEmpty(processPath))
        {
            var dir = Path.GetDirectoryName(processPath);
            if (!string.IsNullOrEmpty(dir))
            {
                return dir;
            }
        }

        return AppContext.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
    }

    private static string FormatOcrInitFailureMessage(Exception ex)
    {
        var detail = ex.Message;
        var hint =
            "\n\n若電腦未安裝 Python：請點「一鍵配置環境」，或在開發機執行 tools\\Prepare-PythonPortable.ps1 後將 python_portable 與程式一併發佈。";
        if (detail.Contains("Python worker", StringComparison.OrdinalIgnoreCase)
            || detail.Contains("python", StringComparison.OrdinalIgnoreCase)
            || detail.Contains("ModuleNotFoundError", StringComparison.OrdinalIgnoreCase)
            || detail.Contains("DLL load failed", StringComparison.OrdinalIgnoreCase))
        {
            return $"OCR引擎啟動失敗：{detail}{hint}";
        }

        return $"OCR引擎初始化失敗：{detail}\n請檢查 inference 模型目錄或上述 Python 配置。";
    }

    private static string? TryResolvePythonFromCommand()
    {
        try
        {
            using var process = new Process
            {
                StartInfo = new ProcessStartInfo
                {
                    FileName = "python",
                    Arguments = "-c \"import sys;print(sys.executable)\"",
                    UseShellExecute = false,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    CreateNoWindow = true
                }
            };

            process.Start();
            var output = process.StandardOutput.ReadToEnd().Trim();
            process.WaitForExit(5000);
            if (process.ExitCode == 0 && !string.IsNullOrWhiteSpace(output) && File.Exists(output))
            {
                return output;
            }
        }
        catch
        {
            // Ignore command lookup failures and keep manual configuration path.
        }

        return null;
    }

    private void SaveCurrentTemplate(string filePath)
    {
        _templatePersistenceService.Save(filePath, _regions, _resultTable);
    }

    private void LoadTemplate(string filePath)
    {
        var template = _templatePersistenceService.Load(filePath);
        _regions.Clear();
        _dragStates.Clear();
        foreach (var region in template.Regions)
        {
            _regions.Add(region);
            EnsureResultColumn(region.Name);
        }

        _templatePersistenceService.FillDataTable(_resultTable, template);
        RedrawRegions();
    }

    private async Task RecognizeAllPagesAsync()
    {
        if (string.IsNullOrWhiteSpace(_pdfPath) || _regions.Count == 0)
        {
            StatusText.Text = "請先導入PDF並添加識別框。";
            return;
        }

        if (string.IsNullOrWhiteSpace(_appConfig.PythonExePath) || !File.Exists(_appConfig.PythonExePath))
        {
            MessageBox.Show(
                "找不到可用的 Python（含內建 python_portable）。請點「一鍵配置環境」，或安裝 Python 3.11+ 並配置 appsettings.local.json 的 PythonExePath。",
                "OCR配置錯誤",
                MessageBoxButton.OK,
                MessageBoxImage.Warning);
            return;
        }

        try
        {
            _ocrEngineService.EnsureInitialized(_appConfig.PythonExePath, _appConfig.FastMode);
        }
        catch (Exception ex)
        {
            MessageBox.Show(FormatOcrInitFailureMessage(ex), "錯誤", MessageBoxButton.OK, MessageBoxImage.Error);
            return;
        }

        _batchCts?.Cancel();
        _batchCts = new CancellationTokenSource();
        SetBusyState(true);
        var progress = new Progress<(int Current, int Total)>(p =>
        {
            StatusText.Text = $"批量識別中：{p.Current}/{p.Total}";
        });

        try
        {
            await Task.Run(() =>
            {
                return _ocrWorkflowService.RecognizeAllPages(
                    _pdfPath,
                    _regions,
                    _appConfig.RenderWidth,
                    _appConfig.RenderHeight,
                    progress,
                    result =>
                    {
                        Dispatcher.Invoke(() =>
                        {
                            ApplyRecognitionResult(result);
                            ResultGrid.Items.Refresh();
                        }, DispatcherPriority.Background);
                    },
                    _batchCts.Token);
            });
            ResultGrid.Items.Refresh();
            StatusText.Text = "批量識別完成";
        }
        catch (OperationCanceledException)
        {
            StatusText.Text = "批量識別已取消";
        }
        catch (Exception ex)
        {
            MessageBox.Show($"批量識別失敗：{ex.Message}", "錯誤", MessageBoxButton.OK, MessageBoxImage.Error);
            StatusText.Text = "批量識別失敗";
        }
        finally
        {
            SetBusyState(false);
        }
    }

    private void SetBusyState(bool isBusy)
    {
        _isBusy = isBusy;
        ApplyUiState();
    }

    private async void RecognizeAll_OnClick(object sender, RoutedEventArgs e)
    {
        await RecognizeAllPagesAsync();
    }

    private void CancelBatch_OnClick(object sender, RoutedEventArgs e)
    {
        _batchCts?.Cancel();
    }

    private void SaveTemplate_OnClick(object sender, RoutedEventArgs e)
    {
        var dialog = new SaveFileDialog
        {
            Filter = "模板檔案|*.json",
            FileName = "ocr_template.json"
        };
        if (dialog.ShowDialog() != true)
        {
            return;
        }

        SaveCurrentTemplate(dialog.FileName);
        StatusText.Text = $"模板已儲存：{Path.GetFileName(dialog.FileName)}";
    }

    private void LoadTemplate_OnClick(object sender, RoutedEventArgs e)
    {
        var dialog = new OpenFileDialog
        {
            Filter = "模板檔案|*.json",
            Multiselect = false
        };
        if (dialog.ShowDialog() != true)
        {
            return;
        }

        LoadTemplate(dialog.FileName);
        StatusText.Text = $"模板已載入：{Path.GetFileName(dialog.FileName)}";
    }
}

internal sealed class DragState
{
    public bool IsDragging { get; set; }
    public Point DragOffset { get; set; }
}