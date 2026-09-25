import atexit
import json
import os
import random
import subprocess
import time

import requests

from . import config


class NcmError(RuntimeError):
    pass


class NcmClient:
    def __init__(self, base=None):
        self.base = (base or config.API_BASE).rstrip("/")
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers["User-Agent"] = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        )
        self.cookie = ""
        self._proc = None
        self._log = None
        self._load_cookie()

    def _load_cookie(self):
        path = config.COOKIE_PATH
        if not path.exists():
            return
        try:
            self.cookie = json.loads(path.read_text(encoding="utf-8")).get("cookie", "")
        except (json.JSONDecodeError, OSError):
            self.cookie = ""

    def _save_cookie(self):
        config.COOKIE_PATH.parent.mkdir(parents=True, exist_ok=True)
        config.COOKIE_PATH.write_text(
            json.dumps(
                {
                    "cookie": self.cookie,
                    "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def ensure_server(self, wait=30):
        if self._healthy():
            return
        entry = config.API_ENTRY
        if not entry.exists():
            raise NcmError(
                f"未找到 API 服务，请先执行: cd {config.API_DIR} && npm install @neteasecloudmusicapienhanced/api"
            )
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._log = open(config.API_LOG, "a", encoding="utf-8")
        env = dict(
            os.environ,
            PORT=str(config.API_PORT),
            ENABLE_RANDOM_CN_IP="true" if config.ENABLE_RANDOM_CN_IP else "false",
        )
        self._proc = subprocess.Popen(
            ["node", str(entry)],
            cwd=str(config.API_DIR),
            stdout=self._log,
            stderr=self._log,
            env=env,
        )
        atexit.register(self.stop_server)
        deadline = time.time() + wait
        while time.time() < deadline:
            if self._healthy():
                return
            if self._proc.poll() is not None:
                raise NcmError(f"API 服务启动失败，详见 {config.API_LOG}")
            time.sleep(0.5)
        raise NcmError("API 服务启动超时")

    def _healthy(self):
        try:
            resp = self.session.get(self.base + "/login/status", timeout=2)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def stop_server(self):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()

    def request(self, path, params=None, timeout=30):
        params = dict(params or {})
        if self.cookie:
            params.setdefault("cookie", self.cookie)
        last_error = None
        for attempt in range(config.MAX_RETRIES):
            try:
                resp = self.session.get(self.base + path, params=params, timeout=timeout)
                data = resp.json()
                if resp.status_code == 200 and isinstance(data, dict):
                    return self._unwrap(data)
                last_error = NcmError(f"HTTP {resp.status_code}: {str(data)[:200]}")
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
            time.sleep(min(8.0, 0.6 * (2**attempt)) + random.random() * 0.4)
        raise NcmError(f"请求失败 {path}: {last_error}")

    @staticmethod
    def _unwrap(data):
        body = data.get("body")
        if isinstance(body, dict) and body:
            return body
        return data

    def account(self):
        resp = self.request("/user/account")
        inner = resp.get("data")
        if isinstance(inner, dict) and ("account" in inner or "profile" in inner):
            resp = inner
        profile = resp.get("profile")
        if isinstance(profile, dict) and profile.get("userId"):
            return profile
        account = resp.get("account")
        if isinstance(account, dict) and account.get("id") and not account.get("anonimousUser"):
            return {"userId": account.get("id"), "nickname": account.get("userName", "")}
        return None

    def vip_info(self):
        if not self.cookie:
            return None
        try:
            data = self.request("/vip/info")
        except NcmError:
            return None
        for _ in range(2):
            if isinstance(data, dict) and isinstance(data.get("data"), dict):
                data = data["data"]
        return data if isinstance(data, dict) else None

    def ensure_login(self):
        self.ensure_server()
        if self.account():
            return
        print("未登录或登录状态已失效，开始二维码登录")
        self.login_qr()

    def logout(self):
        if self.cookie:
            try:
                self.request("/logout")
            except NcmError:
                pass
        self.cookie = ""
        if config.COOKIE_PATH.exists():
            config.COOKIE_PATH.unlink()

    def import_cookie(self, cookie):
        self.ensure_server()
        self.cookie = cookie.strip()
        try:
            profile = self.account()
        except NcmError:
            profile = None
        if not profile:
            self.cookie = ""
            raise NcmError("cookie 无效或已过期")
        self._save_cookie()
        return profile

    def login_qr(self, timeout=180):
        self.ensure_server()
        deadline = time.time() + timeout
        key = None
        last_code = None
        login_extra = {"randomCNIP": "true"} if config.ENABLE_RANDOM_CN_IP else {}
        while time.time() < deadline:
            if not key:
                resp = self.request("/login/qr/key", login_extra)
                key = (resp.get("data") or {}).get("unikey")
                if not key:
                    raise NcmError("获取二维码 key 失败")
                resp = self.request(
                    "/login/qr/create",
                    {"key": key, "qrimg": "true", **login_extra},
                )
                qrurl = (resp.get("data") or {}).get("qrurl")
                if not qrurl:
                    raise NcmError("获取二维码失败")
                self._show_qr(qrurl)
                print("请使用网易云音乐 App 扫码登录（180 秒内有效）")
            resp = self.request("/login/qr/check", {"key": key, **login_extra})
            code = int(resp.get("code") or 0)
            if code == 800:
                print("二维码已过期，正在刷新...")
                key = None
                continue
            if code == 801:
                time.sleep(1.5)
                continue
            if code == 802:
                if last_code != 802:
                    print("已扫码，请在手机上确认登录")
                last_code = 802
                time.sleep(1.5)
                continue
            if code == 803:
                cookie = resp.get("cookie") or ""
                if not cookie:
                    raise NcmError("登录成功但未返回 cookie")
                self.cookie = cookie
                self._save_cookie()
                profile = self.account()
                if not profile:
                    raise NcmError("登录状态校验失败，请重试")
                print(f"登录成功：{profile.get('nickname', '')}")
                return profile
            time.sleep(1.5)
        raise NcmError("二维码登录超时，请重试")

    @staticmethod
    def _show_qr(url):
        try:
            import qrcode

            qr = qrcode.QRCode(border=1)
            qr.add_data(url)
            qr.make(fit=True)
            try:
                qr.print_ascii(invert=True)
            except Exception:
                pass
            try:
                qr.make_image().save(config.QR_PNG_PATH)
                print(f"二维码图片已保存到 {config.QR_PNG_PATH}")
            except Exception:
                print(f"二维码链接: {url}")
        except ImportError:
            print(f"二维码链接: {url}")
