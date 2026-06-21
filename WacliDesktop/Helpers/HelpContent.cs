namespace WacliDesktop.Helpers;

public static class HelpContent
{
    public const string Manual = """
        赤瞳灵讯 · 使用手册
        ========================================

        一、软件简介
        赤瞳灵讯基于 wacli，在本机管理 WhatsApp 消息与附件，并提供模块化桌面界面：
        登录配对、数据浏览、SQLite 查询、命令工具、耀耀工厂云端同步。

        运行目录（与程序同目录，可整包拷贝迁移）：
          %RUNTIME_DIR%
          · bin\wacli.exe          wacli 程序
          · environment.json       一键配置后保存的工具路径
          · database-profile.json  数据库映射（默认目录 / 手机号库）
          · src\wacli\             wacli 源码（需编译时）

        数据库默认根目录（publish3.0）：
          C:\Users\<用户名>\ChitongLingxun
          · _unbound\wacli.db                        未绑定手机号时临时库
          · <手机号>Data Base\<手机号>Data Base.db    账号正式库（同号复用）

        二、一键配置环境（推荐）
        点击右下角「配置环境」，软件会分四步自动完成：
          1. 扫描本机是否已安装 Git / Go / gcc / wacli / Python
          2. 已安装的组件直接复用路径，不重复下载
          3. 缺失的组件通过 winget 安装；wacli 优先复制本机已有版本，否则 git 编译到 runtime\bin
          4. 将最终路径写入 environment.json，重启软件即可使用

        三、数据库与多账号
        · 同一 WhatsApp 手机号：始终复用已登记数据库。
        · 不同手机号：自动新建独立库（手机号Data Base）。
        · 数据浏览页支持：导出数据库、加载数据库、默认数据库、刷新。
        · 修改默认数据库目录时：系统会尝试把已登记账号库整体迁移到新目录。
          （迁移失败的账号库会保留原位置继续可用）

        四、主页
        · 状态条（全宽）：左侧登录状态（绿点=已登录，红点=未登录或链接断开）。
        · 若 wacli 链接断开，会显示「链接断开」并及时转红灯。
        · 四个板块各开独立窗口；同一板块再次点击会激活已有窗口。
        · 关闭主页将关闭所有子窗口并停止后台 sync。

        五、登录配对
        方式一 · 二维码：生成二维码 → 手机 WhatsApp 扫码
        方式二 · 手机号：输入 E.164 号码 → 获取配对码 → 手机输入

        六、耀耀工厂（云端同步）
        · 可配置 API 地址、Token、OwnerId、同步档位与自动同步。
        · 云端同步与媒体补下会做目录互斥，避免多开并发写同一库。

        七、常见问题
        Q：提示找不到 wacli？
        A：点击「配置环境」；若本机已有 wacli 会自动复制到 runtime\bin。

        Q：Go 已安装仍报错？
        A：配置环境会扫描 Program Files\Go 等路径；完成后重启软件。

        Q：改了默认数据库目录后，旧账号库不见了？
        A：先看数据浏览页的迁移提示。迁移失败时旧目录不会删除，可继续使用并重试迁移。

        Q：主页显示“链接断开”？
        A：表示账号曾登录但当前连接中断。可在登录配对页刷新状态或重新启动 sync。

        八、开发者
        Sean Xu
        """;
}
