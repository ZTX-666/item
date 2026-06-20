using System.IO;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;

namespace WacliDesktop.Services;

public sealed class CloudSyncService : IDisposable
{
    private static readonly CloudSyncService Shared = new();
    public static CloudSyncService Instance => Shared;

    private readonly SemaphoreSlim _gate = new(1, 1);
    private readonly HttpClient _http = new() { Timeout = TimeSpan.FromMinutes(10) };
    private Timer? _autoTimer;
    private CloudSyncConfig _config = CloudSyncConfig.Load();
    private CloudSyncState _state = CloudSyncState.Load();

    public CloudSyncConfig Config => _config;
    public bool IsRunning { get; private set; }

    public event Action<string>? LogLine;
    public event Action? StateChanged;

    public void Reload()
    {
        _config = CloudSyncConfig.Load();
        _state = CloudSyncState.Load();
        ApplyAutoTimer();
        RaiseChanged();
    }

    public void UpdateConfig(CloudSyncConfig cfg)
    {
        _config = cfg;
        _config.Save();
        ApplyAutoTimer();
        RaiseChanged();
    }

    public void ApplyAutoTimer()
    {
        _autoTimer?.Dispose();
        _autoTimer = null;
        if (!_config.AutoSyncEnabled || string.IsNullOrWhiteSpace(_config.ApiBaseUrl))
            return;

        var interval = TimeSpan.FromMinutes(Math.Clamp(_config.AutoSyncIntervalMinutes, 5, 1440));
        _autoTimer = new Timer(_ =>
        {
            _ = RunSyncAsync(new Progress<string>(s => Log(s)), CancellationToken.None);
        }, null, interval, interval);
        Log($"已启用自动同步，间隔 {_config.AutoSyncIntervalMinutes} 分钟。");
    }

    public async Task<bool> TestConnectionAsync(IProgress<string>? log = null, CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(_config.ApiBaseUrl))
        {
            log?.Report("请填写云端 API 地址。");
            return false;
        }

        try
        {
            using var req = BuildRequest(HttpMethod.Get, _config.HealthUrl());
            var resp = await _http.SendAsync(req, ct);
            var body = await resp.Content.ReadAsStringAsync(ct);
            if (resp.IsSuccessStatusCode)
            {
                log?.Report($"连接成功：{body.Trim()}");
                return true;
            }
            log?.Report($"连接失败 HTTP {(int)resp.StatusCode}：{body}");
            return false;
        }
        catch (Exception ex)
        {
            log?.Report($"连接失败：{ex.Message}");
            return false;
        }
    }

    public async Task RunSyncAsync(IProgress<string> log, CancellationToken ct = default)
    {
        if (!await _gate.WaitAsync(0, ct))
        {
            log.Report("同步正在进行中，请稍候。");
            return;
        }

        IsRunning = true;
        RaiseChanged();
        try
        {
            using var storeMutex = AppConfig.AcquireStoreMutex();
            if (storeMutex is null)
            {
                log.Report("云端同步已跳过：数据库目录被其他实例占用。");
                return;
            }

            _config = CloudSyncConfig.Load();
            _state = CloudSyncState.Load();

            if (string.IsNullOrWhiteSpace(_config.ApiBaseUrl))
                throw new InvalidOperationException("未配置云端 API 地址。");
            if (string.IsNullOrWhiteSpace(_config.SyncToken))
                throw new InvalidOperationException("未配置同步 Token。");
            if (string.IsNullOrWhiteSpace(_config.OwnerId))
                throw new InvalidOperationException("未配置 OwnerId（用户标识）。");
            var db = AppConfig.ResolveReadableDbPath();
            if (!File.Exists(db))
                throw new FileNotFoundException("未找到数据库，请先完成 WhatsApp 同步。", db);

            log.Report($"━━━ 耀耀工厂云端同步 · {CloudSyncConfig.TierLabel(_config.SyncTier)} ━━━");

            var ok = await TestConnectionAsync(log, ct);
            if (!ok)
                throw new InvalidOperationException("云端健康检查未通过。");

            var totalMsg = 0;
            while (true)
            {
                ct.ThrowIfCancellationRequested();
                var batch = CloudSyncDataReader.FetchMessagesSince(_state.LastMessageTs, _config.MessageBatchSize);
                if (batch.Count == 0)
                    break;

                var payload = new
                {
                    owner_id = _config.OwnerId,
                    tier = _config.SyncTier,
                    items = batch.Select(ToPayload).ToList(),
                };

                await PostJsonWithRetryAsync(_config.MessagesUrl(), payload, log, ct);
                _state.LastMessageTs = batch.Max(b => b.Ts);
                _state.Save();
                totalMsg += batch.Count;
                log.Report($"  已上传消息 {totalMsg} 条（水位 ts={_state.LastMessageTs}）");

                if (batch.Count < _config.MessageBatchSize)
                    break;
            }

            if (totalMsg == 0)
                log.Report("  无新消息需要上传。");
            else
                log.Report($"✓ 消息同步完成，共 {totalMsg} 条。");

            if (_config.SyncTier >= 1)
                await SyncThumbnailsAsync(log, ct);

            if (_config.SyncTier >= 2)
                await SyncFullMediaAsync(log, ct);

            _config.LastSuccessAt = DateTimeOffset.Now.ToString("O");
            _config.LastError = null;
            _config.Save();
            log.Report($"━━━ 同步完成 {_config.LastSuccessAt} ━━━");
        }
        catch (Exception ex)
        {
            _config.LastError = ex.Message;
            _config.Save();
            log.Report($"✗ 同步失败：{ex.Message}");
            throw;
        }
        finally
        {
            IsRunning = false;
            _gate.Release();
            RaiseChanged();
        }
    }

    private async Task SyncThumbnailsAsync(IProgress<string> log, CancellationToken ct)
    {
        log.Report("→ 上传缩略图（档位2）…");
        var pending = CloudSyncDataReader.ListThumbnailUploadCandidates(_state, 120);

        var done = 0;
        foreach (var item in pending)
        {
            ct.ThrowIfCancellationRequested();
            var thumb = item.ThumbPath;

            var fi = new FileInfo(thumb);
            if (fi.Length > _config.MaxThumbnailBytes)
            {
                log.Report($"  跳过缩略图 {item.MsgId}：超过大小限制");
                continue;
            }

            await UploadMediaAsync(item.MsgId, item.ChatJid, thumb, "thumbnail", log, ct);
            _state.SyncedThumbnailMsgIds.Add(item.MsgId);
            if (done % 10 == 0)
                _state.Save();
            done++;
        }
        _state.Save();
        log.Report($"✓ 缩略图上传 {done} 个。");
    }

    private async Task SyncFullMediaAsync(IProgress<string> log, CancellationToken ct)
    {
        log.Report("→ 上传原文件媒体（档位3）…");
        var pending = CloudSyncDataReader.FetchMediaPending(2, _state, 300)
            .Where(x => !_state.SyncedFullMediaMsgIds.Contains(x.MsgId))
            .Take(50)
            .ToList();

        var done = 0;
        foreach (var item in pending)
        {
            ct.ThrowIfCancellationRequested();
            var path = CloudSyncDataReader.ResolveMediaPath(item.LocalPath);
            if (path is null)
                continue;

            var fi = new FileInfo(path);
            if (fi.Length > _config.MaxMediaFileBytes)
            {
                log.Report($"  跳过媒体 {item.MsgId}：{fi.Length} 字节超过限制");
                continue;
            }

            await UploadMediaAsync(item.MsgId, item.ChatJid, path, "full", log, ct);
            _state.SyncedFullMediaMsgIds.Add(item.MsgId);
            _state.SyncedThumbnailMsgIds.Add(item.MsgId);
            if (done % 5 == 0)
                _state.Save();
            done++;
        }
        _state.Save();
        log.Report($"✓ 原文件上传 {done} 个。");
    }

    private async Task UploadMediaAsync(
        string msgId,
        string chatJid,
        string filePath,
        string kind,
        IProgress<string> log,
        CancellationToken ct)
    {
        await WithRetryAsync(async () =>
        {
            using var form = new MultipartFormDataContent();
            form.Add(new StringContent(_config.OwnerId), "owner_id");
            form.Add(new StringContent(msgId), "msg_id");
            form.Add(new StringContent(chatJid), "chat_jid");
            form.Add(new StringContent(kind), "kind");

            await using var fs = File.OpenRead(filePath);
            var streamContent = new StreamContent(fs);
            streamContent.Headers.ContentType = new MediaTypeHeaderValue(GuessMime(filePath));
            form.Add(streamContent, "file", Path.GetFileName(filePath));

            using var req = BuildRequest(HttpMethod.Post, _config.MediaUrl());
            req.Content = form;
            var resp = await _http.SendAsync(req, ct);
            var body = await resp.Content.ReadAsStringAsync(ct);
            if (!resp.IsSuccessStatusCode)
                throw new HttpRequestException($"媒体上传失败 HTTP {(int)resp.StatusCode}: {body}");
            return true;
        }, _config.MaxRetryCount, log, $"媒体 {msgId}");
    }

    private async Task PostJsonWithRetryAsync(string url, object payload, IProgress<string> log, CancellationToken ct)
    {
        await WithRetryAsync(async () =>
        {
            using var req = BuildRequest(HttpMethod.Post, url);
            req.Content = new StringContent(
                JsonSerializer.Serialize(payload),
                Encoding.UTF8,
                "application/json");
            var resp = await _http.SendAsync(req, ct);
            var body = await resp.Content.ReadAsStringAsync(ct);
            if (!resp.IsSuccessStatusCode)
                throw new HttpRequestException($"HTTP {(int)resp.StatusCode}: {body}");
            return true;
        }, _config.MaxRetryCount, log, "消息批次");
    }

    private HttpRequestMessage BuildRequest(HttpMethod method, string url)
    {
        var req = new HttpRequestMessage(method, url);
        req.Headers.Authorization = new AuthenticationHeaderValue("Bearer", _config.SyncToken);
        req.Headers.TryAddWithoutValidation("X-Api-Key", _config.SyncToken);
        return req;
    }

    private static async Task WithRetryAsync(
        Func<Task<bool>> action,
        int max,
        IProgress<string> log,
        string label)
    {
        Exception? last = null;
        for (var i = 1; i <= max; i++)
        {
            try
            {
                await action();
                return;
            }
            catch (Exception ex)
            {
                last = ex;
                log.Report($"  {label} 第 {i}/{max} 次失败：{ex.Message}");
                if (i < max)
                    await Task.Delay(TimeSpan.FromSeconds(Math.Pow(2, i)), CancellationToken.None);
            }
        }
        throw last ?? new InvalidOperationException(label + " failed");
    }

    private static object ToPayload(CloudMessageRow r) => new
    {
        msg_id = r.MsgId,
        chat_jid = r.ChatJid,
        chat_name = r.ChatName,
        sender_name = r.SenderName,
        sender_jid = r.SenderJid,
        ts = r.Ts,
        text = r.Text,
        display_text = r.DisplayText,
        media_type = r.MediaType,
        local_path = r.LocalPath,
        filename = r.Filename,
        revoked = r.Revoked,
        deleted_for_me = r.DeletedForMe,
    };

    private static string GuessMime(string path)
    {
        var ext = Path.GetExtension(path).ToLowerInvariant();
        return ext switch
        {
            ".jpg" or ".jpeg" => "image/jpeg",
            ".png" => "image/png",
            ".webp" => "image/webp",
            ".mp4" => "video/mp4",
            ".pdf" => "application/pdf",
            ".ogg" => "audio/ogg",
            _ => "application/octet-stream",
        };
    }

    public string BuildConfigSummary()
    {
        var sb = new StringBuilder();
        sb.AppendLine("【赤瞳灵讯 · 耀耀工厂云端同步】");
        sb.AppendLine($"API: {_config.ApiBaseUrl}");
        sb.AppendLine($"OwnerId: {_config.OwnerId}");
        sb.AppendLine($"档位: {CloudSyncConfig.TierLabel(_config.SyncTier)}");
        sb.AppendLine($"健康检查: {_config.HealthUrl()}");
        sb.AppendLine($"消息接口: POST {_config.MessagesUrl()}");
        sb.AppendLine($"媒体接口: POST {_config.MediaUrl()} (multipart)");
        sb.AppendLine($"Authorization: Bearer <SyncToken>");
        sb.AppendLine($"水位: last_message_ts={_state.LastMessageTs}");
        return sb.ToString();
    }

    private void Log(string line) => LogLine?.Invoke(line);
    private void RaiseChanged() => StateChanged?.Invoke();

    public void Dispose()
    {
        _autoTimer?.Dispose();
        _http.Dispose();
        _gate.Dispose();
    }
}
