from __future__ import annotations

from dataclasses import dataclass

from utils.orm import orm_to_df


@dataclass
class DummyDeal:
    id: int
    company: str
    stage: str


def test_orm_to_df_renames_id_column():
    items = [DummyDeal(id=10, company="Acme", stage="Qualified")]
    df = orm_to_df(items, id_column_name="deal_id")
    assert "deal_id" in df.columns
    assert "id" not in df.columns
    assert int(df.iloc[0]["deal_id"]) == 10

