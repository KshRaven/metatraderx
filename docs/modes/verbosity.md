# Verbosity

`verbose` controls the notices printed to stderr while [offline mode](offline.md) is on. It accepts a bool or an int.

| Value | Output |
| --- | --- |
| `0` or `False` | none (default) |
| `1` or `True` | a notice from `initialize`, `login` and `shutdown` |
| `2` | also a line for every call: answered from the cache, not in the cache, or unavailable offline |

```python
import metatraderx as mtx

mt = mtx.MetaTrader(offline=True, verbose=2)
```

| Where | How |
| --- | --- |
| Constructor | `verbose=True` or `verbose=2` |
| Default instance | `mtx.configure(verbose=1)` |
| Environment | `MTX_VERBOSE=1` (`true`, `yes`, `on` and `2` are accepted) |
| Saved setting | `mtx config verbose 1` |
| Command line | `mtx -v ...` |

Notices are prefixed with `[mtx] offline mode:`. Online, `verbose` prints nothing; errors are reported through
`last_error()` or, with `strict=True`, as [exceptions](../python/errors.md).
