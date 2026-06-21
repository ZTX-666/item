namespace WacliDesktop.Services;

/// <summary>
/// Quick-launch presets for ConsoleView, aligned with https://wacli.sh/ command groups.
/// Read-only / safe defaults where possible; mutating commands are marked in the label.
/// </summary>
public static class WacliQuickCommands
{
    public sealed record Entry(string Label, string Args);

    public sealed record Group(string Title, IReadOnlyList<Entry> Commands);

    public static IReadOnlyList<Group> All { get; } =
    [
        new("Start", [
            new("doctor", "doctor"),
            new("version", "version"),
            new("docs", "docs"),
            new("help", "help"),
        ]),
        new("Auth & Sync", [
            new("auth status", "auth status"),
            new("sync --help", "sync --help"),
            new("history coverage", "--read-only history coverage"),
            new("history fill (dry)", "--read-only history fill --dry-run"),
            new("history backfill --help", "history backfill --help"),
        ]),
        new("Messages", [
            new("messages list", "--read-only --json messages list --limit 20"),
            new("messages search", "--read-only messages search --query hello --limit 10"),
            new("messages starred", "--read-only messages starred --limit 20"),
            new("messages export --help", "messages export --help"),
            new("messages show --help", "messages show --help"),
            new("messages context --help", "messages context --help"),
        ]),
        new("Chats", [
            new("chats list", "--read-only --json chats list --limit 20"),
            new("chats show --help", "chats show --help"),
            new("chats archive --help", "chats archive --help"),
            new("chats pin --help", "chats pin --help"),
            new("chats mute --help", "chats mute --help"),
            new("chats mark-read --help", "chats mark-read --help"),
            new("chats cleanup --help", "chats cleanup --help"),
        ]),
        new("Contacts", [
            new("contacts search", "--read-only contacts search --query a --limit 20"),
            new("contacts show --help", "contacts show --help"),
            new("contacts refresh", "contacts refresh"),
            new("contacts alias --help", "contacts alias --help"),
            new("contacts tags --help", "contacts tags --help"),
            new("contacts import-system --help", "contacts import-system --help"),
        ]),
        new("Groups", [
            new("groups list", "--read-only --json groups list --limit 20"),
            new("groups info --help", "groups info --help"),
            new("groups refresh", "groups refresh"),
            new("groups participants --help", "groups participants --help"),
            new("groups invite --help", "groups invite --help"),
            new("groups join --help", "groups join --help"),
            new("groups rename --help", "groups rename --help"),
            new("groups prune --help", "groups prune --help"),
        ]),
        new("Media & Send", [
            new("media download --help", "media download --help"),
            new("send text --help", "send text --help"),
            new("send file --help", "send file --help"),
            new("send image --help", "send image --help"),
            new("send reaction --help", "send reaction --help"),
            new("send forward --help", "send forward --help"),
        ]),
        new("Channels & Calls", [
            new("channels list", "channels list"),
            new("channels info --help", "channels info --help"),
            new("channels join --help", "channels join --help"),
            new("calls list", "--read-only calls list --limit 20"),
        ]),
        new("Polls & Presence", [
            new("polls list", "--read-only polls list --limit 20"),
            new("poll show --help", "poll show --help"),
            new("poll vote --help", "poll vote --help"),
            new("presence typing --help", "presence typing --help"),
            new("presence paused --help", "presence paused --help"),
        ]),
        new("Store & Accounts", [
            new("store stats", "--read-only store stats"),
            new("store cleanup --help", "store cleanup --help"),
            new("accounts list", "accounts list"),
            new("accounts show --help", "accounts show --help"),
            new("accounts add --help", "accounts add --help"),
        ]),
        new("Profile", [
            new("profile set-picture --help", "profile set-picture --help"),
        ]),
        new("Auth (write)", [
            new("auth logout", "auth logout"),
        ]),
    ];
}
