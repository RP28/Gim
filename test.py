"""Minimal application entry point.

Pass no arguments for the create/resume screen:
    python test.py

Programmatic sources are also accepted:
    gim.run(("orders", orders_df), ("customers", customers_df))
"""

import gim

if __name__ == "__main__":
    raise SystemExit(gim.run())
