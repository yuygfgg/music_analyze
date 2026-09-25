import argparse

from music_analyze import analyze, db, fetch, ncm, plot


def _client():
    client = ncm.NcmClient()
    client.ensure_server()
    return client


def cmd_login(args):
    client = _client()
    if args.cookie:
        profile = client.import_cookie(args.cookie)
        print(f"cookie 导入成功，已登录：{profile.get('nickname', '')} (uid={profile.get('userId')})")
        return
    if args.force:
        client.logout()
        print("已清除原登录状态")
    profile = client.account()
    if not profile:
        profile = client.login_qr()
    if not profile:
        return
    print(f"已登录：{profile.get('nickname', '')} (uid={profile.get('userId')})")
    vip = client.vip_info() or {}
    level = vip.get("redVipLevel") or vip.get("vipLevel")
    if level:
        print(f"VIP 已生效（等级 {level}），VIP 歌曲可获取完整音频")
    else:
        print("未检测到 VIP；VIP/付费歌曲只能取到试听片段，可用 analyze --allow-trial 分析片段")


def cmd_logout(args):
    client = _client()
    client.logout()
    print("已退出登录（服务端 session 作废，本地 cookie 已删除）")


def cmd_fetch(args):
    client = _client()
    client.ensure_login()
    conn = db.connect()
    fetch.fetch_library(client, conn, uid=args.uid)


def cmd_analyze(args):
    client = _client()
    if not client.account():
        print("提示：未登录，VIP/试听歌曲会被跳过")
    analyze.run(
        limit=args.limit,
        retry_errors=args.retry_errors,
        device=args.device,
        keep_audio=args.keep_audio,
        aggressive=args.aggressive,
        allow_trial=args.allow_trial,
    )


def cmd_plot(args):
    plot.run(raw=args.raw, by_year=args.by_year)


def cmd_status(args):
    conn = db.connect()
    db.init_db(conn)
    rows = conn.execute("SELECT status, COUNT(*) AS c FROM tracks GROUP BY status").fetchall()
    print("曲库统计:", {r["status"]: r["c"] for r in rows} or "空")
    analyzed = conn.execute(
        "SELECT COUNT(*) AS c FROM tracks WHERE status='analyzed' AND bpm_final IS NOT NULL"
    ).fetchone()["c"]
    print(f"可绘图: {analyzed} 首")


def cmd_all(args):
    client = _client()
    client.ensure_login()
    conn = db.connect()
    fetch.fetch_library(client, conn, uid=args.uid)
    analyze.run(
        limit=args.limit,
        retry_errors=args.retry_errors,
        device=args.device,
        keep_audio=args.keep_audio,
        aggressive=args.aggressive,
        allow_trial=args.allow_trial,
    )
    plot.run(raw=args.raw, by_year=args.by_year)


def build_parser():
    parser = argparse.ArgumentParser(description="网易云收藏 BPM x Energy 分析")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("login", help="二维码登录并保存 cookie")
    p.add_argument("--force", action="store_true", help="清除当前登录并强制重新扫码（切换账号）")
    p.add_argument("--cookie", default=None, help="直接导入浏览器 cookie（MUSIC_U=...; __csrf=...），跳过扫码")
    p.set_defaults(func=cmd_login)

    p = sub.add_parser("logout", help="退出登录并删除本地 cookie")
    p.set_defaults(func=cmd_logout)

    p = sub.add_parser("fetch", help="拉取收藏歌曲元数据")
    p.add_argument("--uid", type=int, default=None, help="用户 uid，默认当前登录账号")
    p.set_defaults(func=cmd_fetch)

    p = sub.add_parser("analyze", help="下载音频并分析 BPM/Energy")
    p.add_argument("--limit", type=int, default=None, help="只分析前 N 首")
    p.add_argument("--device", choices=["auto", "cpu", "mps"], default="auto")
    p.add_argument("--retry-errors", action="store_true", help="重试之前失败的曲目")
    p.add_argument("--keep-audio", action="store_true", help="保留下载的音频文件")
    p.add_argument("--aggressive", action="store_true", help="低 BPM 一律尝试翻倍（消歧更激进）")
    p.add_argument("--allow-trial", action="store_true", help="缺失完整音频时分析试听片段并标记")
    p.set_defaults(func=cmd_analyze)

    p = sub.add_parser("plot", help="绘制固定坐标分布图并导出 CSV")
    p.add_argument("--raw", action="store_true", help="使用未消歧的原始 BPM")
    p.add_argument("--by-year", action="store_true", help="按发行年份着色")
    p.set_defaults(func=cmd_plot)

    p = sub.add_parser("status", help="查看曲库统计")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("all", help="登录 + 采集 + 分析 + 绘图")
    p.add_argument("--uid", type=int, default=None)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--device", choices=["auto", "cpu", "mps"], default="auto")
    p.add_argument("--retry-errors", action="store_true")
    p.add_argument("--keep-audio", action="store_true")
    p.add_argument("--aggressive", action="store_true")
    p.add_argument("--allow-trial", action="store_true")
    p.add_argument("--raw", action="store_true")
    p.add_argument("--by-year", action="store_true")
    p.set_defaults(func=cmd_all)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
