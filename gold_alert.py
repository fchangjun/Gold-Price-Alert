#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


DEFAULT_SOURCE_URL = "https://api.gold-api.com/price/XAU"
DEFAULT_STATE_FILE = ".gold_alert_state.json"
DEFAULT_CONFIG_FILE = "config.json"
DEFAULT_FX_SOURCE_URL = "https://stooq.com/q/l/?s=usdcny&i=1"
DEFAULT_BEEP_SOUND = "Ping"
TROY_OUNCE_TO_GRAMS = 31.1034768


@dataclass
class Settings:
    target: float
    target_unit: str
    direction: str
    interval: int
    name: str
    source_url: str
    state_file: Path
    once: bool
    ignore_hit_cache: bool
    bark_key: str | None
    bark_server: str
    bark_group: str
    bark_sound: str | None
    bark_url: str | None
    notify_mode: str
    beep: bool
    beep_sound: str
    use_live_fx: bool
    usd_cny_rate: float | None
    fx_provider: str
    fx_source_url: str
    fx_refresh_interval: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Monitor the international gold price (XAU/USD) and notify when a target is reached."
    )
    parser.add_argument(
        "--config",
        default=None,
        help=f"Path to a JSON config file. Default: ./{DEFAULT_CONFIG_FILE} when present.",
    )
    parser.add_argument("--target", type=float, help="Alert target price.")
    parser.add_argument(
        "--target-unit",
        choices=["usd_oz", "cny_g"],
        default=None,
        help="Target price unit. usd_oz for USD/oz, cny_g for RMB/g. Default: usd_oz",
    )
    parser.add_argument(
        "--direction",
        choices=["above", "below"],
        help="Trigger when price is above or below the target.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=None,
        help="Polling interval in seconds. Default: 60",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Notification title. Default: Gold Price Alert",
    )
    parser.add_argument(
        "--source-url",
        default=None,
        help=f"Price source URL. Default: {DEFAULT_SOURCE_URL}",
    )
    parser.add_argument(
        "--state-file",
        default=None,
        help=f"State file path. Default: {DEFAULT_STATE_FILE}",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Check once and exit.",
    )
    parser.add_argument(
        "--ignore-hit-cache",
        action="store_true",
        help="Ignore the cached hit state and alert every time the condition is met.",
    )
    parser.add_argument("--bark-key", default=None, help="Bark device key.")
    parser.add_argument(
        "--bark-server",
        default=None,
        help="Bark server base URL. Default: https://api.day.app",
    )
    parser.add_argument("--bark-group", default=None, help="Bark notification group. Default: gold-alert")
    parser.add_argument("--bark-sound", default=None, help="Optional Bark sound name.")
    parser.add_argument("--bark-url", default=None, help="Optional URL opened when tapping Bark notification.")
    parser.add_argument(
        "--notify-mode",
        choices=["notification", "dialog", "both"],
        default=None,
        help="Local Mac reminder mode. Default: notification",
    )
    parser.add_argument(
        "--beep",
        action="store_true",
        help="Play a macOS alert sound when an alert is triggered.",
    )
    parser.add_argument(
        "--beep-sound",
        default=None,
        help=f"macOS sound name in /System/Library/Sounds. Default: {DEFAULT_BEEP_SOUND}",
    )
    parser.add_argument(
        "--usd-cny-rate",
        type=float,
        default=None,
        help="Fallback manual USD/CNY rate used when live FX lookup fails.",
    )
    parser.add_argument(
        "--disable-live-fx",
        action="store_true",
        help="Disable live USD/CNY lookup and always use the configured manual rate.",
    )
    parser.add_argument(
        "--fx-source-url",
        default=None,
        help=f"Live FX API URL. Default: {DEFAULT_FX_SOURCE_URL}",
    )
    parser.add_argument(
        "--fx-provider",
        choices=["stooq", "frankfurter"],
        default=None,
        help="Live FX provider parser. Default: stooq",
    )
    parser.add_argument(
        "--fx-refresh-interval",
        type=int,
        default=None,
        help="Refresh interval for live FX rates in seconds. Default: 21600",
    )
    return parser.parse_args()


def load_config(path: str | None) -> dict[str, Any]:
    if not path:
        default_path = Path.cwd() / DEFAULT_CONFIG_FILE
        if not default_path.exists():
            return {}
        config_path = default_path
    else:
        config_path = Path(path).expanduser()

    with config_path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    if not isinstance(data, dict):
        raise ValueError("Config file must contain a JSON object.")
    return data


def pick_value(cli_value: Any, config: dict[str, Any], key: str, default: Any = None) -> Any:
    return cli_value if cli_value is not None else config.get(key, default)


def build_settings(args: argparse.Namespace, config: dict[str, Any]) -> Settings:
    target = pick_value(args.target, config, "target")
    target_unit = pick_value(args.target_unit, config, "target_unit", "usd_oz")
    direction = pick_value(args.direction, config, "direction")
    interval = pick_value(args.interval, config, "interval", 60)
    name = pick_value(args.name, config, "name", "Gold Price Alert")
    source_url = pick_value(args.source_url, config, "source_url", DEFAULT_SOURCE_URL)
    state_file = Path(pick_value(args.state_file, config, "state_file", DEFAULT_STATE_FILE)).expanduser()
    once = args.once or bool(config.get("once", False))
    ignore_hit_cache = args.ignore_hit_cache or bool(config.get("ignore_hit_cache", False))
    bark_key = pick_value(args.bark_key, config, "bark_key")
    bark_server = pick_value(args.bark_server, config, "bark_server", "https://api.day.app")
    bark_group = pick_value(args.bark_group, config, "bark_group", "gold-alert")
    bark_sound = pick_value(args.bark_sound, config, "bark_sound")
    bark_url = pick_value(args.bark_url, config, "bark_url")
    notify_mode = pick_value(args.notify_mode, config, "notify_mode", "notification")
    beep = args.beep or bool(config.get("beep", False))
    beep_sound = pick_value(args.beep_sound, config, "beep_sound", DEFAULT_BEEP_SOUND)
    usd_cny_rate = pick_value(args.usd_cny_rate, config, "usd_cny_rate")
    use_live_fx = False if args.disable_live_fx else bool(config.get("use_live_fx", True))
    fx_source_url = pick_value(args.fx_source_url, config, "fx_source_url", DEFAULT_FX_SOURCE_URL)
    fx_provider = pick_value(args.fx_provider, config, "fx_provider", "stooq")
    fx_refresh_interval = pick_value(args.fx_refresh_interval, config, "fx_refresh_interval", 21600)

    if target is None:
        raise ValueError("Missing target price. Pass --target or set target in the config.")
    if target_unit not in {"usd_oz", "cny_g"}:
        raise ValueError("target_unit must be usd_oz or cny_g.")
    if direction not in {"above", "below"}:
        raise ValueError("Missing or invalid direction. Use --direction above|below.")
    if interval <= 0:
        raise ValueError("Interval must be a positive integer.")
    if notify_mode not in {"notification", "dialog", "both"}:
        raise ValueError("notify_mode must be notification, dialog, or both.")
    if usd_cny_rate is not None and float(usd_cny_rate) <= 0:
        raise ValueError("usd_cny_rate must be a positive number.")
    if fx_provider not in {"stooq", "frankfurter"}:
        raise ValueError("fx_provider must be stooq or frankfurter.")
    if int(fx_refresh_interval) <= 0:
        raise ValueError("fx_refresh_interval must be a positive integer.")

    return Settings(
        target=float(target),
        target_unit=str(target_unit),
        direction=direction,
        interval=int(interval),
        name=str(name),
        source_url=str(source_url),
        state_file=state_file,
        once=once,
        ignore_hit_cache=ignore_hit_cache,
        bark_key=str(bark_key) if bark_key else None,
        bark_server=str(bark_server).rstrip("/"),
        bark_group=str(bark_group),
        bark_sound=str(bark_sound) if bark_sound else None,
        bark_url=str(bark_url) if bark_url else None,
        notify_mode=str(notify_mode),
        beep=beep,
        beep_sound=str(beep_sound),
        use_live_fx=use_live_fx,
        usd_cny_rate=float(usd_cny_rate) if usd_cny_rate is not None else None,
        fx_provider=str(fx_provider),
        fx_source_url=str(fx_source_url),
        fx_refresh_interval=int(fx_refresh_interval),
    )


def fetch_price(source_url: str) -> tuple[float, str]:
    request = Request(
        source_url,
        headers={
            "User-Agent": "gold-alert/1.0",
            "Accept": "application/json",
        },
    )
    with urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))

    price = payload.get("price")
    updated_at = payload.get("updatedAt") or datetime.now(timezone.utc).isoformat()
    if price is None:
        raise ValueError(f"Unexpected response payload: {payload}")
    return float(price), str(updated_at)


def fetch_usd_cny_rate_from_frankfurter(source_url: str) -> tuple[float, str]:
    request = Request(
        source_url,
        headers={
            "User-Agent": "gold-alert/1.0",
            "Accept": "application/json",
        },
    )
    with urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))

    rates = payload.get("rates")
    if not isinstance(rates, dict) or rates.get("CNY") is None:
        raise ValueError(f"Unexpected FX payload: {payload}")

    rate = float(rates["CNY"])
    effective_date = payload.get("date") or datetime.now(timezone.utc).date().isoformat()
    return rate, str(effective_date)


def fetch_usd_cny_rate_from_stooq(source_url: str) -> tuple[float, str]:
    request = Request(
        source_url,
        headers={
            "User-Agent": "gold-alert/1.0",
            "Accept": "text/plain",
        },
    )
    with urlopen(request, timeout=15) as response:
        payload = response.read().decode("utf-8").strip()

    parts = [part.strip() for part in payload.split(",")]
    if len(parts) < 7 or parts[0].upper() != "USDCNY":
        raise ValueError(f"Unexpected FX payload: {payload}")

    date_text = parts[1]
    time_text = parts[2]
    last_text = parts[6]
    if date_text == "N/D" or time_text == "N/D" or last_text == "N/D":
        raise ValueError(f"Incomplete FX payload: {payload}")

    rate = float(last_text)
    timestamp = f"{date_text[:4]}-{date_text[4:6]}-{date_text[6:8]} {time_text[:2]}:{time_text[2:4]}:{time_text[4:6]}"
    return rate, timestamp


def should_alert(price: float, settings: Settings, usd_cny_rate: float | None) -> bool:
    comparable_price = get_comparable_price(price, settings, usd_cny_rate)
    if comparable_price is None:
        return False
    if settings.direction == "above":
        return comparable_price >= settings.target
    return comparable_price <= settings.target


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"condition_met": False}

    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError):
        pass

    return {"condition_met": False}


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=2)


def run_osascript(script: str) -> None:
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or "unknown osascript error"
        raise OSError(stderr)


def send_macos_notification(settings: Settings, title: str, message: str) -> None:
    escaped_title = escape_applescript(title)
    escaped_message = escape_applescript(message)

    if settings.notify_mode in {"notification", "both"}:
        run_osascript(
            f'display notification "{escaped_message}" with title "{escaped_title}"'
        )

    if settings.notify_mode in {"dialog", "both"}:
        run_osascript(
            f'display dialog "{escaped_message}" with title "{escaped_title}" buttons {{"OK"}} default button "OK"'
        )

    if settings.beep:
        play_macos_sound(settings.beep_sound)


def play_macos_sound(sound_name: str) -> None:
    sound_path = Path("/System/Library/Sounds") / f"{sound_name}.aiff"
    if sound_path.exists():
        subprocess.run(["afplay", str(sound_path)], check=False)
        return
    # Fall back to the terminal bell if the configured sound does not exist.
    print("\a", end="", flush=True)


def send_bark_notification(settings: Settings, title: str, body: str) -> None:
    if not settings.bark_key:
        return

    path = "/".join(
        [
            quote(settings.bark_key, safe=""),
            quote(title, safe=""),
            quote(body, safe=""),
        ]
    )
    params: dict[str, str] = {"group": settings.bark_group}
    if settings.bark_sound:
        params["sound"] = settings.bark_sound
    if settings.bark_url:
        params["url"] = settings.bark_url

    request_url = f"{settings.bark_server}/{path}?{urlencode(params)}"
    request = Request(
        request_url,
        headers={
            "User-Agent": "gold-alert/1.0",
            "Accept": "application/json",
        },
    )
    with urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))

    if payload.get("code") != 200:
        raise ValueError(f"Bark push failed: {payload}")


def escape_applescript(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def convert_to_cny_per_gram(price_usd_per_oz: float, usd_cny_rate: float) -> float:
    return price_usd_per_oz * usd_cny_rate / TROY_OUNCE_TO_GRAMS


def get_comparable_price(price_usd_per_oz: float, settings: Settings, usd_cny_rate: float | None) -> float | None:
    if settings.target_unit == "usd_oz":
        return price_usd_per_oz
    if usd_cny_rate is None:
        return None
    return convert_to_cny_per_gram(price_usd_per_oz, usd_cny_rate)


def resolve_fx_rate(
    settings: Settings,
    cached_rate: float | None,
    cached_date: str | None,
    last_refresh_monotonic: float | None,
) -> tuple[float | None, str | None, str, float | None]:
    if not settings.use_live_fx:
        return settings.usd_cny_rate, None, "manual", last_refresh_monotonic

    now_monotonic = time.monotonic()
    if (
        cached_rate is not None
        and last_refresh_monotonic is not None
        and now_monotonic - last_refresh_monotonic < settings.fx_refresh_interval
    ):
        return cached_rate, cached_date, "live-cached", last_refresh_monotonic

    try:
        if settings.fx_provider == "stooq":
            live_rate, effective_date = fetch_usd_cny_rate_from_stooq(settings.fx_source_url)
        else:
            live_rate, effective_date = fetch_usd_cny_rate_from_frankfurter(settings.fx_source_url)
        return live_rate, effective_date, "live", now_monotonic
    except (URLError, TimeoutError, ValueError, OSError) as exc:
        now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{now_text}] 汇率查询失败: {exc}", file=sys.stderr, flush=True)
        if cached_rate is not None:
            return cached_rate, cached_date, "live-cached", last_refresh_monotonic
        if settings.usd_cny_rate is not None:
            return settings.usd_cny_rate, None, "manual-fallback", last_refresh_monotonic
        return None, None, "unavailable", last_refresh_monotonic


def format_price_suffix(price: float, usd_cny_rate: float | None, fx_label: str) -> str:
    if usd_cny_rate is None:
        return ""
    cny_per_gram = convert_to_cny_per_gram(price, usd_cny_rate)
    return f" | 约 {cny_per_gram:.2f} RMB/g (USD/CNY {usd_cny_rate:.4f}, {fx_label})"


def format_target(settings: Settings) -> str:
    if settings.target_unit == "cny_g":
        return f"{settings.target:.2f} RMB/g"
    return f"{settings.target:.2f} USD/oz"


def format_target_suffix(settings: Settings, usd_cny_rate: float | None) -> str:
    if settings.target_unit != "usd_oz" or usd_cny_rate is None:
        return ""
    target_cny_per_gram = convert_to_cny_per_gram(settings.target, usd_cny_rate)
    return f" (约 {target_cny_per_gram:.2f} RMB/g)"


def format_log(
    now_text: str,
    price: float,
    settings: Settings,
    matched: bool,
    usd_cny_rate: float | None,
    fx_label: str,
) -> str:
    status = "命中阈值" if matched else "未命中"
    comparator = ">=" if settings.direction == "above" else "<="
    comparable_price = get_comparable_price(price, settings, usd_cny_rate)
    current_target_unit_text = ""
    if comparable_price is not None and settings.target_unit == "cny_g":
        current_target_unit_text = f" | 当前折算: {comparable_price:.2f} RMB/g"
    return (
        f"[{now_text}] 当前金价: {price:.2f} USD/oz | "
        f"目标: {comparator} {format_target(settings)}{format_target_suffix(settings, usd_cny_rate)}"
        f"{current_target_unit_text}"
        f"{format_price_suffix(price, usd_cny_rate, fx_label)} | {status}"
    )


def run(settings: Settings) -> int:
    cached_fx_rate: float | None = None
    cached_fx_date: str | None = None
    last_fx_refresh_monotonic: float | None = None

    while True:
        try:
            price, updated_at = fetch_price(settings.source_url)
            usd_cny_rate, fx_date, fx_source, last_fx_refresh_monotonic = resolve_fx_rate(
                settings,
                cached_fx_rate,
                cached_fx_date,
                last_fx_refresh_monotonic,
            )
            if usd_cny_rate is not None:
                cached_fx_rate = usd_cny_rate
                cached_fx_date = fx_date
            state = load_state(settings.state_file)
            matched = should_alert(price, settings, usd_cny_rate)
            now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            fx_label = {
                "live": f"实时 {fx_date}" if fx_date else "实时",
                "live-cached": f"缓存 {fx_date}" if fx_date else "缓存",
                "manual": "手动",
                "manual-fallback": "手动兜底",
                "unavailable": "不可用",
            }.get(fx_source, fx_source)

            print(format_log(now_text, price, settings, matched, usd_cny_rate, fx_label), flush=True)

            should_send_alert = matched and (
                settings.ignore_hit_cache or not state.get("condition_met", False)
            )

            if should_send_alert:
                cny_text = ""
                if usd_cny_rate is not None:
                    cny_per_gram = convert_to_cny_per_gram(price, usd_cny_rate)
                    cny_text = f" 约合 {cny_per_gram:.2f} RMB/g。"
                current_unit_text = ""
                comparable_price = get_comparable_price(price, settings, usd_cny_rate)
                if comparable_price is not None and settings.target_unit == "cny_g":
                    current_unit_text = f" 当前折算价 {comparable_price:.2f} RMB/g。"
                message = (
                    f"当前金价 {price:.2f} USD/oz，"
                    f"已{'高于' if settings.direction == 'above' else '低于'}目标 {format_target(settings)}。"
                    f"{current_unit_text}{cny_text}\n"
                    f"数据时间: {updated_at}"
                )
                try:
                    send_macos_notification(settings, settings.name, message)
                except OSError as exc:
                    print(f"[{now_text}] Mac 通知失败: {exc}", file=sys.stderr, flush=True)
                if settings.bark_key:
                    try:
                        send_bark_notification(settings, settings.name, message)
                    except (URLError, TimeoutError, ValueError, OSError) as exc:
                        print(f"[{now_text}] Bark 推送失败: {exc}", file=sys.stderr, flush=True)
                print(f"[{now_text}] 已发送提醒", flush=True)

            save_state(
                settings.state_file,
                {
                    "condition_met": matched,
                    "last_price": price,
                    "last_cny_per_gram": (
                        convert_to_cny_per_gram(price, usd_cny_rate)
                        if usd_cny_rate is not None
                        else None
                    ),
                    "last_usd_cny_rate": usd_cny_rate,
                    "last_fx_date": fx_date,
                    "last_fx_source": fx_source,
                    "last_checked_at": now_text,
                    "last_source_updated_at": updated_at,
                },
            )
        except (URLError, TimeoutError, ValueError, OSError) as exc:
            now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{now_text}] 拉取失败: {exc}", file=sys.stderr, flush=True)

        if settings.once:
            return 0

        time.sleep(settings.interval)


def main() -> int:
    args = parse_args()
    try:
        config = load_config(args.config)
        settings = build_settings(args, config)
    except (OSError, ValueError) as exc:
        print(f"配置错误: {exc}", file=sys.stderr)
        return 2

    return run(settings)


if __name__ == "__main__":
    raise SystemExit(main())
