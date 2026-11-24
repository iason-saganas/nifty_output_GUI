# NIFTy optimization GUI

A live browser view of the terminal output of `nifty.re.optimize_kl`.
NIFTy prints hundreds of solver lines in seconds; this tool captures them and
sorts them into the three processes of each global KL iteration:

| Pane (position)              | Process                                   | Solver                |
|------------------------------|-------------------------------------------|-----------------------|
| Linear sampling (left, top)  | MGVI samples                              | CG per sample pair    |
| Nonlinear sampling (left, bottom) | geoVI sample updates (only if enabled) | Newton-CG per sample |
| KL minimization (right)      | minimization of the KL                    | Newton-CG, with an inner CG per step |

Lines are classified by structure, not by solver names, so any `name=` /
`cg_name=` you pass to `optimize_kl` works. Click **raw log** to see the role
assigned to each line.

**Requirements:** Python ≥ 3.8 (standard library only) and a browser.

Try it out on a saved log file: 

``python nifty_gui_01.py --open -- python replay_log.py path/to/run.log --delay 0.0``

where path/to/run.log is a file containing stuff like this: 

``OPTIMIZE_KL: Starting 0001
device memory before sampling (iteration 1): allocated 0.8, peak 1.3 GB per device
SL: Iteration 0 E:+1.2688e+08 ΔE:inf AbsDelta:1.0000e-06
SL: Iteration 1 E:+2.6008e+07 ΔE:1.0087e+08 AbsDelta:1.0000e-06
SL: Iteration 2 E:+1.2956e+07 ΔE:1.3052e+07 AbsDelta:1.0000e-06
SL: Iteration 3 E:+3.7353e+06 ΔE:9.2208e+06 AbsDelta:1.0000e-06
...``


## Files

| File | Purpose |
|------|---------|
| `nifty_gui_00.py`   | Captures output, echoes it to the terminal, serves the page at `http://localhost:8000` |
| `nifty_gui_00.html` | The page: parser and display (re-read on every refresh, so edits need no restart) |
| `replay_log.py`  | Replays a saved log slowly, for testing without running NIFTy |

---

## 1. Test with a saved log

```bash
python nifty_gui_01.py --open -- python replay_log.py path/to/run.log --delay 0.0
```

`--delay` is the number of seconds between lines.

To inspect a finished log without the live replay, open `nifty_gui_00.html` directly
in the browser and drag the log file onto the page.

## 2. Run a real inference (Python script)

```bash
python nifty_gui_01.py --open -- python my_inference.py --any --script --args
```

`nifty_gui_00.py` starts your script, forces unbuffered output, captures stdout and
stderr, and still prints everything to your terminal. The page stays up after the
run ends until you press Ctrl-C.

Alternatively, pipe the output in. You need `-u` (otherwise Python buffers piped
output and the page updates in big jumps) and `2>&1` (NIFTy logs go to stderr):

```bash
python -u my_inference.py 2>&1 | tee run.log | python nifty_gui_00.py --open
```

`tee run.log` keeps a copy of the log for later replay.

## 3. Run a real inference (Jupyter notebook)

A notebook's output can't be piped, so let the notebook write NIFTy's log to a
file and have the GUI follow that file.

In the notebook, before calling `optimize_kl`:

```python
import logging
fh = logging.FileHandler("run.log", mode="w")
fh.setFormatter(logging.Formatter("%(message)s"))
logging.getLogger("NIFTy.re").addHandler(fh)
```

In a terminal:

```bash
tail -n +1 -F run.log | python nifty_gui_00.py --open
```

If `run.log` stays empty, NIFTy's logger has a different name in your version.
Check with:

```python
import logging
print([n for n in logging.root.manager.loggerDict if "nifty" in n.lower()])
```

Then use that name in `getLogger(...)`. If all else fails, convert the notebook
to a script (`jupyter nbconvert --to script notebook.ipynb`) and use section 2.

## 4. Running on a remote machine / cluster

Start the GUI on the remote machine as above (it binds to localhost only), then
forward the port from your laptop:

```bash
ssh -L 8000:localhost:8000 user@cluster
```

Then open `http://localhost:8000` locally.

## Options

```
--port 8000      port to serve on
--host 127.0.0.1 bind address (use 0.0.0.0 to expose on the network; be careful)
--open           open a browser tab automatically
```

## Reading the display

- **✓** convergence criterion met (`ΔE < AbsDelta`, `|r| < Resnorm`, or `|↘| < xtol`)
- **●** currently running
- **■** stopped without meeting a displayed criterion (often `maxiter` reached)
- **?** after a title: classification still provisional (only during the first
  global iteration, until the structure is clear)
- An orange **→** value below 1 means the line search shortened the Newton step,
  i.e. the quadratic approximation was poor. A red **↺ reset** means it fell back to
  steepest descent.

The tabs in the header switch between global KL iterations; **follow latest**
tracks the current one.

## Versions

Each version is a standalone pair of files; run whichever you want.

| Version | Files | What it shows |
|---------|-------|---------------|
| 00 | `nifty_gui_00.py`, `nifty_gui_00.html` | Classified text view: lines sorted into linear sampling / nonlinear sampling / KL panes |
| 01 | `nifty_gui_01.py`, `nifty_gui_01.html` | *(planned)* live convergence plots per process |

`replay_log.py` works with every version.