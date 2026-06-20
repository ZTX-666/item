using System.Drawing;
using System.IO;
using System.Windows.Media.Imaging;
using QRCoder;

namespace WacliDesktop.Helpers;

public static class QrHelper
{
    public static BitmapImage CreateImage(string payload, int pixelsPerModule = 8)
    {
        using var generator = new QRCodeGenerator();
        using var data = generator.CreateQrCode(payload, QRCodeGenerator.ECCLevel.Q);
        using var qr = new QRCode(data);
        using Bitmap bitmap = qr.GetGraphic(pixelsPerModule);

        using var stream = new MemoryStream();
        bitmap.Save(stream, System.Drawing.Imaging.ImageFormat.Png);
        stream.Position = 0;

        var image = new BitmapImage();
        image.BeginInit();
        image.CacheOption = BitmapCacheOption.OnLoad;
        image.StreamSource = stream;
        image.EndInit();
        image.Freeze();
        return image;
    }
}
