# GIM — Graphical Insight Mapper

GIM is a dark desktop data-analysis workspace built around a vertical, branching history tree. It combines a native PySide6 application shell with embedded Plotly charts.

## Why this stack

- **PySide6 / Qt 6**: native cross-platform windows, dialogs, splitters, high-DPI support, graphics scenes, Bézier paths, property animations, and QtTest-based UI tests.
- **Plotly**: interactive histogram, KDE, box, violin, scatter, pie, line, frequency, and correlation plots with hover details and zooming.
- **pandas / SciPy**: dataframe operations, replayable transformations, correlation, Mann–Whitney U, t-tests, ANOVA F, and chi-square tests.

## Install and run

Python 3.11–3.13 is recommended.

```bash
python -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python test.py
```

The only public application entry point is:

```python
import gim

gim.run()
```

### Start with data supplied from Python

```python
import pandas as pd
import gim

orders = pd.read_csv("orders.csv", sep=";")
customers = pd.read_csv("customers.csv", encoding="cp1252")

gim.run(
    ("Orders", orders),
    ("Customers", customers),
)
```

`gim.run()` accepts any number of:

- pandas DataFrames;
- CSV paths;
- `(alias, object)` tuples;
- `{alias: object}` mappings;
- lists/tuples containing supported sources;
- objects implementing `to_pandas()`;
- dataframe-interchange objects implementing `__dataframe__()`.

Use `start_event_loop=False` when embedding GIM or writing UI tests.

## Main workflow

1. The first window offers **Create new workspace** or **Resume .gim workspace**.
2. A new workspace prompts for one or more CSV files. Each import receives an alias.
3. Every source appears at the bottom of its history branch.
4. **Transform** uses the compact data language and creates a node directly above the selected node.
5. **Duplicate branch** creates a horizontally offset branch. The operation exists in only one UI location.
6. Shift-click two nodes to open the merge dialog. Choose left, right, or inner join and a key from each dataset.
7. Select any node to bind the plot workspace to that exact data state.
8. Plot-local code modifies only the current chart. The same mechanism is available before statistical tests.
9. Save plots/tests to attach badges to the exact history node and list them in the Saved tab.
10. Save a `.gim` workspace. Reopening it loads originals and replays the history.

## Plot families

- **Distribution**: Histogram, KDE, Histogram + KDE. Histogram hover shows interval, count, and percentage. Bins support automatic selection or a synchronized slider and numeric input.
- **Range & shape**: Box and violin plots. Hover includes Q1, median, Q3, IQR, count, and point value.
- **Scatter**: WebGL-backed points with X, Y, row, and hue details.
- **Pie**: category counts or aggregated numeric values.
- **Line**: line or line-plus-markers, optionally grouped by hue.
- **Frequency**: count or percentage. Flip converts it to a horizontal bar chart.
- **Correlation map**: selected columns with Pearson, Spearman, or Kendall correlation.

## Memory and persistence design

GIM stores each original dataframe once. History nodes store only operation names and JSON-compatible parameters. Derived data is materialized recursively and held in a bounded LRU cache; it is not persisted.

A `.gim` file is a standard ZIP container:

```text
manifest.json
sources/<source-id>.csv
sources/<source-id>.csv
...
```

The manifest includes nodes, parent relationships, branch ranks, replayable operations, selected node, saved plot configurations, local code, and saved statistical results. No pickle payloads or merged snapshots are required.

## Package layout

```text
gim/
  app.py                  application controller and public launch flow
  config/theme.py         single source of truth for the restrained palette
  core/
    dsl.py                safe local transformation language
    importers.py          robust CSV and dataframe-object adapters
    models.py             serialisable history and artifact models
    operations.py         decorator-based replay operation registry
    persistence.py        atomic .gim ZIP save/load
    plotting.py           reusable plot-builder class hierarchy
    stats.py              statistical test engine
    workspace.py          graph, branching, cache, and materialisation
  ui/
    dialogs.py            import, transform, merge, stats, correlation dialogs
    history_view.py       animated nodes and cubic Bézier edges
    main_window.py        workspace orchestration
    plot_panel.py         dynamic plot controls and local operations
    welcome.py            create/resume screen
    widgets.py            reusable token editor and Plotly host
```

## Tests

```bash
pytest
```

The suite covers DSL safety and transformations, branching, merge behavior, cache bounds, original-only persistence, damaged files, unusual CSV delimiters/encodings, all plot families, hover metadata, statistical tests, the public `gim.run()` API, history multi-selection, main-window binding, and synchronized bin controls.

For headless CI, the test configuration uses `QT_QPA_PLATFORM=offscreen` and substitutes a lightweight HTML viewer for Qt WebEngine.

## Extension points

- Register a replayable operation with `@operation(name, label)` in `gim/core/operations.py`.
- Add a chart family by subclassing `PlotBuilder` and using `@register_builder`.
- Add a dataframe source adapter in `normalise_sources()`.
- Add a statistical test in `run_statistical_test()` and expose its display name in `TEST_NAMES`.

See [CHEATSHEET.md](CHEATSHEET.md) for the complete local language reference.
