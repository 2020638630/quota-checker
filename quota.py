#!/usr/bin/env python3
"""quota.py — DeepSeek 剩余余额 + 自定义余额接口 便携查询（纯标准库，零依赖）

用法:
  python quota.py --init            # 生成 quotas.json 模板，填入 API key
  python quota.py                   # 查询所有已配置的提供商
  python quota.py --json            # 机器可读输出（给状态栏/其他工具用）

也支持环境变量兜底: DEEPSEEK_API_KEY
key 保存时经 Windows DPAPI 加密（enc:v1: 前缀），仅本机当前用户可解密。

需要接别家（OpenAI/Kimi/硅基流动/TokenHub/阿里云/火山等）时用 quotas.json 的
custom 通道，或参考 README「现成开源项目」一节。
"""

import base64
import ctypes
import json
import os
import sys
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor

CONFIG_NAME = "quotas.json"
TIMEOUT = 8
ENC_PREFIX = "enc:v1:"

# ---------- Windows DPAPI：key 在本机当前用户下加解密，密文拷走即废 ----------
_HAVE_DPAPI = sys.platform == "win32"
if _HAVE_DPAPI:
    import ctypes.wintypes as _wt

    class _DataBlob(ctypes.Structure):
        _fields_ = [("cbData", _wt.DWORD),
                    ("pbData", ctypes.POINTER(ctypes.c_char))]

    _CRYPT32 = ctypes.windll.crypt32
    _KERNEL32 = ctypes.windll.kernel32
    _UI_FORBIDDEN = 0x00000001


def _make_blob(data: bytes):
    buf = ctypes.create_string_buffer(data, len(data))
    return _DataBlob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))


def dpapi_encrypt(plaintext: str) -> str:
    in_blob = _make_blob(plaintext.encode("utf-8"))
    out_blob = _DataBlob()
    if not _CRYPT32.CryptProtectData(ctypes.byref(in_blob), "quota-checker",
                                     None, None, None, _UI_FORBIDDEN,
                                     ctypes.byref(out_blob)):
        raise OSError(f"CryptProtectData failed: {ctypes.GetLastError()}")
    try:
        raw = ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        _KERNEL32.LocalFree(out_blob.pbData)
    return ENC_PREFIX + base64.b64encode(raw).decode("ascii")


def dpapi_decrypt(token: str) -> str:
    raw = base64.b64decode(token[len(ENC_PREFIX):])
    in_blob = _make_blob(raw)
    out_blob = _DataBlob()
    if not _CRYPT32.CryptUnprotectData(ctypes.byref(in_blob), None, None, None,
                                       None, _UI_FORBIDDEN, ctypes.byref(out_blob)):
        raise OSError(f"CryptUnprotectData failed: {ctypes.GetLastError()}")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData).decode("utf-8")
    finally:
        _KERNEL32.LocalFree(out_blob.pbData)


TEMPLATE = {
    "deepseek": "",      # https://platform.deepseek.com/api_keys
    # custom: 任意返回 JSON 的余额接口。key 会替换 headers 里的 {key} 占位符；
    # "path" 是点号路径，从返回 JSON 中取要显示的字段（可多个）。
    "custom": [
        # {"name": "kimi", "url": "https://api.moonshot.cn/v1/users/me",
        #  "headers": {"Authorization": "Bearer {key}"},
        #  "path": "data.balance"}
    ],
}

ENV_FALLBACK = {
    "deepseek": "DEEPSEEK_API_KEY",
}


# Windows 上 urllib 会走 proxy_bypass_registry → socket.getfqdn 做 DNS 反解，
# 某些网络环境下这一步会挂住数分钟（实测就是它把查询拖到 6 秒以上甚至卡死）。
# 这些接口都是直连的公网地址，显式用空 ProxyHandler 绕开代理探测。
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def http_json(url, key=None, headers=None):
    hdrs = {"User-Agent": "quota-checker/1.0"}
    if key:
        hdrs["Authorization"] = f"Bearer {key}"
    if headers:
        hdrs.update({k: v.replace("{key}", key or "") for k, v in headers.items()})
    req = urllib.request.Request(url, headers=hdrs)
    with _OPENER.open(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def dig(obj, dotted):
    cur = obj
    for part in dotted.split("."):
        if isinstance(cur, list):
            cur = cur[int(part)]
        else:
            cur = cur.get(part)
        if cur is None:
            return None
    return cur


# ---------- 提供商查询：返回 {"lines": [str], "value": float|None, "unit": str, "sub": str|None} ----------

def q_deepseek(key):
    """余额接口字段（实测 2026-09）：total_balance / granted_balance / topped_up_balance。"""
    d = http_json("https://api.deepseek.com/user/balance", key)
    rows, value, unit, sub = [], None, "", None
    extra = {}
    for b in d.get("balance_infos", []):
        unit = b.get("currency", b.get("unit", ""))
        total = b.get("total_balance", "?")
        granted = b.get("granted_balance", "?")
        topped = b.get("topped_up_balance", "?")
        rows.append(f"总余额 {total} {unit}（赠送 {granted} / 充值 {topped}）")
        if value is None:
            try:
                value = float(b.get("total_balance"))
                extra["granted"] = float(b.get("granted_balance") or 0)
                extra["topped_up"] = float(b.get("topped_up_balance") or 0)
            except (TypeError, ValueError):
                pass
            sub = f"充值 {topped} · 赠送 {granted}"
    if not rows:
        rows.append(json.dumps(d, ensure_ascii=False)[:200])
    return {"lines": rows, "value": value, "unit": unit, "sub": sub,
            "is_available": d.get("is_available"), "extra": extra}


def q_custom(item, key):
    d = http_json(item["url"], key, item.get("headers"))
    paths = item.get("path") or []
    if isinstance(paths, str):
        paths = [paths]
    if paths:
        lines = [f"{p.rsplit('.', 1)[-1]}: {dig(d, p)}" for p in paths]
    else:
        lines = [json.dumps(d, ensure_ascii=False)[:200]]
    value = None
    for p in paths:
        v = dig(d, p)
        if isinstance(v, (int, float)):
            value = float(v)
            break
        if isinstance(v, str):
            try:
                value = float(v.replace(",", ""))
                break
            except ValueError:
                pass
    return {"lines": lines, "value": value, "unit": "", "sub": None}


BUILTIN = {
    "deepseek": q_deepseek,
}


# ---------- 配置读写（secret 字段 DPAPI 加密） ----------

def _key_slots(cfg):
    for name in BUILTIN:
        yield cfg, name
    for item in cfg.get("custom", []):
        yield item, "key"


def encrypt_config(cfg):
    if not _HAVE_DPAPI:
        return cfg
    for holder, field in _key_slots(cfg):
        v = holder.get(field) or ""
        if isinstance(v, str) and v and not v.startswith(ENC_PREFIX):
            holder[field] = dpapi_encrypt(v)
    return cfg


def decrypt_config(cfg):
    for holder, field in _key_slots(cfg):
        v = holder.get(field) or ""
        if not isinstance(v, str) or not v.startswith(ENC_PREFIX):
            continue
        if not _HAVE_DPAPI:
            holder[field] = ""  # 非 Windows 上无法解密，视为未配置
            continue
        try:
            holder[field] = dpapi_decrypt(v)
        except OSError:
            holder[field] = ""  # 密文不属于本机用户：按未配置处理，不崩溃
    return cfg


def load_config():
    here = os.path.dirname(os.path.abspath(__file__))
    for path in (os.path.join(here, "data", CONFIG_NAME), os.path.join(os.getcwd(), "data", CONFIG_NAME), os.path.join(os.getcwd(), CONFIG_NAME)):
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return decrypt_config(json.load(f)), path
    return None, None


def save_config(cfg, path):
    """写入磁盘前把明文 key 加密；返回实际写入路径。"""
    import copy
    with open(path, "w", encoding="utf-8") as f:
        json.dump(encrypt_config(copy.deepcopy(cfg)), f, ensure_ascii=False, indent=2)
    return path


# ---------- 调度与输出 ----------

def collect(cfg, only):
    tasks = []  # (name, callable)
    for name, fn in BUILTIN.items():
        if only and name not in only:
            continue
        key = cfg.get(name) or os.environ.get(ENV_FALLBACK.get(name, ""), "")
        tasks.append((name, (lambda f=fn, k=key: f(k)) if key else None))
    for item in cfg.get("custom", []):
        name = item.get("name", "custom")
        if only and name not in only:
            continue
        key = item.get("key") or os.environ.get("QUOTA_CUSTOM_KEY", "")
        tasks.append((name, (lambda i=item, k=key: q_custom(i, k)) if key else None))
    return tasks


def run(tasks, as_json=False):
    results = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(fn): name for name, fn in tasks if fn}
        for name, fn in tasks:
            if fn is None:
                results[name] = {"status": "skipped", "msg": "未配置 key"}
        for fut in futs:
            name = futs[fut]
            try:
                results[name] = {"status": "ok", "lines": fut.result().get("lines", [])}
            except urllib.error.HTTPError as e:
                body = ""
                try:
                    body = e.read().decode("utf-8", "replace")[:120]
                except Exception:
                    pass
                results[name] = {"status": "error", "msg": f"HTTP {e.code} {body}"}
            except Exception as e:
                results[name] = {"status": "error", "msg": f"{type(e).__name__}: {e}"}

    if as_json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    width = max((len(n) for n, _ in tasks), default=8)
    order = [n for n, _ in tasks]
    for name in order:
        r = results[name]
        icon = {"ok": "✅", "error": "❌", "skipped": "⏭️ "}[r["status"]]
        print(f"{icon} {name:<{width}}", end="  ")
        if r["status"] != "ok":
            print(r["msg"])
        else:
            print("｜".join(r["lines"]))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    args = sys.argv[1:]
    here = os.path.dirname(os.path.abspath(__file__))
    cfg_path = os.path.join(here, "data", CONFIG_NAME)

    if "--init" in args:
        if os.path.exists(cfg_path):
            print(f"{cfg_path} 已存在，不覆盖")
            return
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(TEMPLATE, f, ensure_ascii=False, indent=2)
        print(f"已生成模板：{cfg_path}\n填入 API key 后再运行 python quota.py")
        return

    cfg, path = load_config()
    if cfg is None:
        print("未找到 quotas.json，先运行: python quota.py --init")
        return
    args = [a for a in args if not a.startswith("--")]
    run(collect(cfg, args or None), as_json="--json" in sys.argv)


if __name__ == "__main__":
    main()
