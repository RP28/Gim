# GIM - Graphical Insight Mapper

GIM is a desktop data-analysis workspace for exploring CSV and pandas-backed datasets through a replayable history graph. It combines a native PySide6 interface, Plotly visualizations, a compact local transformation language, statistical tests, and portable `.gim` workspace files.

## Architecture

- **PySide6 / Qt 6**: cross-platform windows, dialogs, splitters, graphics scenes, animations, and QtTest-compatible UI coverage.
- **Plotly**: interactive distribution, range, scatter, pie, line, frequency, and correlation charts with hover metadata and zooming.
- **pandas / SciPy**: dataframe operations, replayable transformations, correlation, Mann-Whitney U, t-tests, ANOVA F, and chi-square tests.

## Install and run

Python 3.11 or newer is required.

```bash
python -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m gim
```

Primary application entry point:

```python
import gim

gim.run()
```

### Launch with Python data

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

`gim.run()` accepts:

- pandas DataFrames
- CSV paths
- `(alias, object)` tuples
- `{alias: object}` mappings
- lists or tuples containing supported sources
- objects implementing `to_pandas()`
- dataframe-interchange objects implementing `__dataframe__()`

Use `start_event_loop=False` when embedding GIM or writing UI tests.

## Main workflow

1. Create a workspace or resume an existing `.gim` file.
2. Import one or more CSV files. Each source receives an alias and starts its own history branch.
3. Apply **Transform** to create a replayable node above the selected dataset.
4. Use **Duplicate branch** to create an independent branch from the selected node.
5. Shift-click two nodes to merge datasets with a left, right, or inner join.
6. Select any node to bind plots and tests to that exact data state.
7. Use plot-local code to adjust the current chart without changing the workspace history.
8. Save plots, correlations, and statistical tests as artifacts attached to the selected node.
9. Save the workspace. Reopening loads the original sources and replays the recorded operations.

## Plot families

- **Distribution**: histogram, KDE, and combined histogram/KDE views. Histogram hover data includes interval, count, and percentage. Bin controls support automatic selection or synchronized manual input.
- **Range & shape**: box and violin plots with Q1, median, Q3, IQR, count, and point-level hover data.
- **Scatter**: WebGL-backed scatter plots with X, Y, row, and hue details.
- **Pie**: category counts or aggregated numeric values.
- **Line**: line or line-with-marker charts, optionally grouped by hue.
- **Frequency**: count or percentage bar charts, with optional horizontal orientation.
- **Correlation map**: Pearson, Spearman, or Kendall correlation for selected columns.

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
  config/theme.py         application dimensions, palette, and stylesheet
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
    history_view.py       interactive history graph rendering
    main_window.py        workspace orchestration
    plot_panel.py         dynamic plot controls and local operations
    welcome.py            create/resume screen
    widgets.py            reusable token editor and Plotly host
```

## Tests

```bash
pytest
```

The test suite covers DSL safety and transformations, branching, merge behavior, cache bounds, original-only persistence, damaged files, unusual CSV delimiters and encodings, plot families, hover metadata, statistical tests, the public `gim.run()` API, history multi-selection, main-window binding, and synchronized bin controls.

For headless CI, the test configuration uses `QT_QPA_PLATFORM=offscreen` and substitutes a lightweight HTML viewer for Qt WebEngine.

## Extension points

- Register a replayable operation with `@operation(name, label)` in `gim/core/operations.py`.
- Add a chart family by subclassing `PlotBuilder` and using `@register_builder`.
- Add a dataframe source adapter in `normalise_sources()`.
- Add a statistical test in `run_statistical_test()` and expose its display name in `TEST_NAMES`.

See [gim/CHEATSHEET.md](gim/CHEATSHEET.md) for the complete local language reference.
