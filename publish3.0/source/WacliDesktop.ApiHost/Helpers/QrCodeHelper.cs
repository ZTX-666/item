using System.Drawing;
using System.Drawing.Imaging;
using QRCoder;

namespace WacliDesktop.ApiHost.Helpers;

internal static class QrCodeHelper
{
    public static string ToBase64Png(string payload, int pixelsPerModule = 8)
    {
        using var generator = new QRCodeGenerator();
        using var data = generator.CreateQrCode(payload, QRCodeGenerator.ECCLevel.Q);
        using var qr = new QRCode(data);
        using Bitmap bitmap = qr.GetGraphic(pixelsPerModule);
        using var stream = new MemoryStream();
        bitmap.Save(stream, ImageFormat.Png);
        return Convert.ToBase64String(stream.ToArray());
    }
}
