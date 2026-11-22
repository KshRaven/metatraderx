# Tools

## cache

```
mtx cache info
mtx cache clear
mtx cache clear -y
mtx cache clear --method copy_rates_range
```

Shows or clears the [cache](../modes/cache.md). `clear` asks for confirmation unless `-y` is given; `--method` limits it
to one method's entries.

## config

```
mtx config                       # all saved settings and the file location
mtx config cache                 # one setting
mtx config cache 1               # set
mtx config cache ""              # remove
```

Saved settings sit below environment variables and above defaults. The names are listed in
[Settings](../reference/environment.md).

## mt4

```
mtx mt4 install-bridge
```

Copies the bridge expert used for [MetaTrader 4](../platforms/mt4.md) into the terminal's `MQL4/Experts` folder.

## doctor

```
mtx doctor
```

Prints the system, Python, Wine, package version, selected terminal, server, cache and offline settings, and whether
Xpra, `cloudflared` and the `MetaTrader5` package are present. Include its output when reporting a problem.

## serve and display

See [Hosting a server](../server/hosting.md) and [Terminal display](../display.md).
