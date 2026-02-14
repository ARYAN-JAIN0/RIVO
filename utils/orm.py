"""ORM conversion helpers."""

from __future__ import annotations

import pandas as pd


def orm_to_df(objects, id_column_name: str | None = None) -> pd.DataFrame:
    """Convert ORM rows to DataFrame with optional id column renaming."""
    if not objects:
        return pd.DataFrame()

    rows = []
    for obj in objects:
        rows.append({k: v for k, v in obj.__dict__.items() if not k.startswith("_")})
    df = pd.DataFrame(rows)
    if id_column_name and "id" in df.columns:
        df = df.rename(columns={"id": id_column_name})
    return df

