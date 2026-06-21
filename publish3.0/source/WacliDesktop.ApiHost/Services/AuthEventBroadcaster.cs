using System.Collections.Concurrent;
using System.Text.Json;
using System.Threading.Channels;

namespace WacliDesktop.ApiHost.Services;

public sealed class AuthEventBroadcaster
{
    private readonly ConcurrentDictionary<Guid, Channel<AuthEvent>> _subscribers = new();

    public ChannelReader<AuthEvent> Subscribe(out Guid id)
    {
        id = Guid.NewGuid();
        var channel = Channel.CreateUnbounded<AuthEvent>(new UnboundedChannelOptions
        {
            SingleReader = true,
            SingleWriter = false,
        });
        _subscribers[id] = channel;
        return channel.Reader;
    }

    public void Unsubscribe(Guid id) => _subscribers.TryRemove(id, out _);

    public void Publish(string type, object data)
    {
        var evt = new AuthEvent(type, DateTimeOffset.Now, data);
        foreach (var pair in _subscribers)
        {
            pair.Value.Writer.TryWrite(evt);
        }
    }

    public static string FormatSse(AuthEvent evt)
    {
        var json = JsonSerializer.Serialize(new
        {
            type = evt.Type,
            time = evt.Time,
            data = evt.Data,
        });
        return $"event: {evt.Type}\ndata: {json}\n\n";
    }
}

public readonly record struct AuthEvent(string Type, DateTimeOffset Time, object Data);
