# macOS

macOS works the same way as [Linux](linux.md): the terminal is a Wine build, and a Windows Python with the
`MetaTrader5` package runs in its prefix. macOS is supported but is not the main target and is tested less.

## Setup

```
pip install metatraderx
mtx install                # downloads the .dmg and copies the app to /Applications
mtx setup
mtx terminal list
mtx terminal select 0
mtx doctor
```

The Wine bundled with the MetaTrader app, CrossOver and Homebrew installs are found. Set `MTX_WINE` when Wine is
somewhere else.

## Not set up

Until `mtx setup` has run, `initialize()` returns `False` with a `SetupWarning` and does not fall back to cached data; see
[Linux](linux.md#setup).

## Display

[`mtx display`](../display.md) needs Xpra (`brew install --cask xpra`, offered automatically). `--tunnel` needs
`cloudflared` (`brew install cloudflared`).

If the setup fails, run `mtx doctor` and see [Troubleshooting](../troubleshooting.md).
