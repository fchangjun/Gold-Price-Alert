# Gold Price Alert

[English](./README.md) | [简体中文](./README.zh-CN.md)

A lightweight Python tool that monitors the international gold price (`XAU/USD`) and sends alerts when your target is reached.

This project is designed for personal price alerts on macOS and Windows, with optional Bark push notifications for iPhone.

## Features

- Monitor live gold price in `USD/oz`
- Compare target price in either `USD/oz` or `RMB/g`
- Convert live price to `RMB/g` with live `USD/CNY`
- Local alerts on macOS and Windows
- Optional Bark push notifications
- Optional repeated alerts by ignoring hit-cache
- Zero third-party Python dependencies

## Requirements

- macOS or Windows
- Python 3.9+
- Internet access
- Optional: Bark app on iPhone if you want push notifications

## Project Files

- `gold_alert.py`: main script
- `config.json`: local runtime config
- `config.example.json`: example config for sharing or publishing
- `assets/gold-price-alert-demo.png`: screenshot of the alert dialog and terminal output
- `.gold_alert_state.json`: generated at runtime, used for de-duplication

## Screenshot

![Gold Price Alert Screenshot](./assets/gold-price-alert-demo.png)

## Quick Start

### 1. Edit the config

Open `config.json` and change the values you care about.

Minimal example:

```json
{
  "target": 4000,
  "target_unit": "usd_oz",
  "direction": "below",
  "interval": 10,
  "name": "Gold Price Alert",
  "notify_mode": "both",
  "beep": true,
  "beep_sound": "Ping"
}
```

### 2. Run

```bash
python3 gold_alert.py
```

The script automatically reads `./config.json`.

## Installation

No package installation is required.

```bash
git clone <your-repo-url>
cd gold-price-alert
python3 gold_alert.py
```

This repository includes both `config.json` and `config.example.json`. If your `config.json` contains personal keys, clear them before publishing or sharing.

## Auto Start On Boot

### macOS

This project includes:

- `./launchd/com.fchangjun.gold-price-alert.plist.template`
- `./launchd/install_launchd.sh`

### 1. Install the launch agent

```bash
chmod +x ./launchd/install_launchd.sh
./launchd/install_launchd.sh
```

### 2. Start immediately

```bash
launchctl start com.fchangjun.gold-price-alert
```

### 3. Stop

```bash
launchctl stop com.fchangjun.gold-price-alert
```

### 4. Disable auto start

```bash
launchctl unload ~/Library/LaunchAgents/com.fchangjun.gold-price-alert.plist
rm ~/Library/LaunchAgents/com.fchangjun.gold-price-alert.plist
```

### Windows

This project includes `windows/start_gold_price_alert.bat`.

You can create a startup task with Task Scheduler:

1. Open Task Scheduler
2. Create Task
3. Trigger: `At log on`
4. Action: `Start a program`
5. Program/script: point to `windows/start_gold_price_alert.bat`
6. Save

You can also create it from PowerShell:

```powershell
$action = New-ScheduledTaskAction -Execute "C:\path\to\gold-price-alert\windows\start_gold_price_alert.bat"
$trigger = New-ScheduledTaskTrigger -AtLogOn
Register-ScheduledTask -TaskName "GoldPriceAlert" -Action $action -Trigger $trigger -Description "Start Gold Price Alert at logon"
```

## Logs

Logs are written to:

- `logs/gold-price-alert.log`
- `logs/gold-price-alert.error.log`

Watch the main log:

```bash
tail -f ./logs/gold-price-alert.log
```

Watch the error log:

```bash
tail -f ./logs/gold-price-alert.error.log
```

## Change Target Without Restarting

The script now auto-reloads `config.json` when the file changes.

For example:

```json
{
  "target": 4800
}
```

Save the file and the running process will reload the configuration on the next polling cycle.

You will see a log line like:

```text
[2026-03-23 20:10:00] Reloaded config: ./config.json
```

## Usage Guide

### Use `USD/oz` as the target

```json
{
  "target": 4000,
  "target_unit": "usd_oz",
  "direction": "below"
}
```

This means:

- alert when gold price is less than or equal to `4000 USD/oz`

### Use `RMB/g` as the target

```json
{
  "target": 950,
  "target_unit": "cny_g",
  "direction": "above"
}
```

This means:

- convert live gold price to `RMB/g`
- alert when converted price is greater than or equal to `950 RMB/g`

### Run once for testing

```bash
python3 gold_alert.py --once
```

### Ignore hit cache and alert every time

```json
{
  "ignore_hit_cache": true
}
```

Or:

```bash
python3 gold_alert.py --ignore-hit-cache
```

### Use stronger local alerts on macOS

```json
{
  "notify_mode": "both",
  "beep": true,
  "beep_sound": "Ping"
}
```

This means:

- show a notification banner
- show a dialog
- play a terminal bell

### Enable Bark push notifications

```json
{
  "bark_key": "your-device-key",
  "bark_server": "https://api.day.app",
  "bark_group": "gold-alert",
  "bark_sound": "alarm"
}
```

After this, each triggered alert will:

- notify on your Mac
- push to your iPhone through Bark

## Configuration Reference

- `target`: target price
- `target_unit`: `usd_oz` or `cny_g`
- `direction`: `above` or `below`
- `interval`: polling interval in seconds
- `name`: notification title
- `source_url`: gold price API URL
- `state_file`: de-duplication state file path
- `once`: check once and exit
- `ignore_hit_cache`: alert on every hit instead of de-duplicating
- `bark_key`: Bark device key
- `bark_server`: Bark server URL
- `bark_group`: Bark message group
- `bark_sound`: Bark sound name
- `bark_url`: URL opened when tapping a Bark notification
- `notify_mode`: `notification`, `dialog`, or `both`
- `beep`: play a local system sound on alert
- `beep_sound`: sound name, for example `Ping`, `Glass`, `Hero`
- `use_live_fx`: enable live `USD/CNY`
- `usd_cny_rate`: fallback manual exchange rate
- `fx_provider`: live FX provider parser, currently `stooq` or `frankfurter`
- `fx_source_url`: live FX endpoint
- `fx_refresh_interval`: FX refresh interval in seconds

## Example Output

### USD target

```text
[2026-03-23 19:23:26] 当前金价: 4362.40 USD/oz | 目标: <= 4000.00 USD/oz (约 889.43 RMB/g) | 约 970.01 RMB/g (USD/CNY 6.9161, 实时 2026-03-23 11:00:56) | 未命中
```

### RMB target

```text
[2026-03-23 19:21:52] 当前金价: 4371.40 USD/oz | 目标: >= 950.00 RMB/g | 当前折算: 972.02 RMB/g | 约 972.02 RMB/g (USD/CNY 6.9161, 实时 2026-03-23 11:00:56) | 命中阈值
```

## Price and FX Sources

- Gold price default: `https://api.gold-api.com/price/XAU`
- FX default: `https://stooq.com/q/l/?s=usdcny&i=1`

The FX conversion is primarily for convenience. If the live FX lookup fails, the script falls back to `usd_cny_rate` in your config.

## Suggested Open Source Cleanup Before Publishing

- keep `config.example.json` as the public sample config
- clear personal values from `config.json` before publishing if needed
- keep `.gold_alert_state.json` ignored
- optionally add screenshots or GIFs of local alerts

## License

This project is licensed under the MIT License. See `LICENSE`.
