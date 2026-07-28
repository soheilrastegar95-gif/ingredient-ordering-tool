"""
db.py — database connection + core calculation logic.
Backed by Postgres (Supabase). Every ingredient, dish, and sale now belongs
to a "location" so one deployment can serve multiple restaurants/branches.

Connection string is read from (in order):
  1. Streamlit secrets (st.secrets["DATABASE_URL"])
  2. Environment variable DATABASE_URL (for local scripts like test_run.py)
"""
import os
from datetime import date as date_type, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor


def _get_database_url() -> str:
    try:
        import streamlit as st
        if "DATABASE_URL" in st.secrets:
            return st.secrets["DATABASE_URL"]
    except Exception:
        pass
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL not found. Add it to .streamlit/secrets.toml (local) "
            "or the app's Secrets settings (Streamlit Cloud)."
        )
    return url


def get_connection():
    return psycopg2.connect(_get_database_url(), cursor_factory=RealDictCursor)


def init_db():
    """No-op — tables are created once via schema_postgres.sql / migration scripts."""
    pass


def _to_date(d):
    if isinstance(d, date_type):
        return d
    return date_type.fromisoformat(d)


# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------

def list_locations() -> list[dict]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM locations ORDER BY name")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_location(name: str) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO locations (name) VALUES (%s) RETURNING id", (name,))
    new_id = cur.fetchone()["id"]
    conn.commit()
    conn.close()
    return new_id


def update_location(location_id: int, name: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE locations SET name = %s WHERE id = %s", (name, location_id))
    conn.commit()
    conn.close()


def delete_location(location_id: int):
    """Deletes the location and all its ingredients/dishes/sales (cascade)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM locations WHERE id = %s", (location_id,))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Sales / usage calculation
# ---------------------------------------------------------------------------

def record_sales(location_id: int, date: str, sales: dict[str, int]):
    """sales = {"Margherita Pizza": 12, "Caesar Salad": 5, ...}"""
    the_date = _to_date(date)
    conn = get_connection()
    cur = conn.cursor()
    for dish_name, qty_sold in sales.items():
        cur.execute(
            "SELECT id FROM dishes WHERE name = %s AND location_id = %s",
            (dish_name, location_id),
        )
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"Unknown dish: '{dish_name}'. Add it in setup first.")
        cur.execute(
            "INSERT INTO sales_entries (date, dish_id, qty_sold, location_id) VALUES (%s, %s, %s, %s)",
            (the_date, row["id"], qty_sold, location_id),
        )
    conn.commit()
    conn.close()


def calculate_usage_for_date(location_id: int, date: str) -> dict[str, float]:
    the_date = _to_date(date)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT i.name AS ingredient_name,
               SUM(se.qty_sold * ri.qty_per_dish) AS qty_used
        FROM sales_entries se
        JOIN recipe_items ri ON ri.dish_id = se.dish_id
        JOIN ingredients i ON i.id = ri.ingredient_id
        WHERE se.date = %s AND se.location_id = %s
        GROUP BY i.name
        """,
        (the_date, location_id),
    )
    rows = cur.fetchall()
    conn.close()
    return {row["ingredient_name"]: float(row["qty_used"]) for row in rows}


def apply_usage_to_stock(location_id: int, usage: dict[str, float]):
    conn = get_connection()
    cur = conn.cursor()
    for ingredient_name, qty_used in usage.items():
        cur.execute(
            "UPDATE ingredients SET current_stock = current_stock - %s WHERE name = %s AND location_id = %s",
            (qty_used, ingredient_name, location_id),
        )
    conn.commit()
    conn.close()


def receive_delivery(location_id: int, deliveries: dict[str, float]):
    conn = get_connection()
    cur = conn.cursor()
    for ingredient_name, qty_received in deliveries.items():
        cur.execute(
            "UPDATE ingredients SET current_stock = current_stock + %s WHERE name = %s AND location_id = %s",
            (qty_received, ingredient_name, location_id),
        )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Ingredients
# ---------------------------------------------------------------------------

def add_ingredient(location_id: int, name: str, unit: str, current_stock: float = 0,
                    reorder_threshold: float = 0, par_level: float = 0,
                    supplier: str = ""):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO ingredients (name, unit, current_stock, reorder_threshold, par_level, supplier, location_id)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (name, unit, current_stock, reorder_threshold, par_level, supplier, location_id),
    )
    conn.commit()
    conn.close()


def update_ingredient(ingredient_id: int, **fields):
    if not fields:
        return
    conn = get_connection()
    cur = conn.cursor()
    set_clause = ", ".join(f"{k} = %s" for k in fields)
    cur.execute(
        f"UPDATE ingredients SET {set_clause} WHERE id = %s",
        (*fields.values(), ingredient_id),
    )
    conn.commit()
    conn.close()


def duplicate_ingredient(ingredient_id: int) -> int:
    """Creates a copy of an ingredient with '(copy)' appended to the name (or '(copy 2)', etc. if taken)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM ingredients WHERE id = %s", (ingredient_id,))
    original = cur.fetchone()
    if not original:
        conn.close()
        raise ValueError("Ingredient not found.")

    base_name = f"{original['name']} (copy)"
    new_name = base_name
    n = 2
    while True:
        cur.execute(
            "SELECT 1 FROM ingredients WHERE name = %s AND location_id = %s",
            (new_name, original['location_id']),
        )
        if cur.fetchone() is None:
            break
        new_name = f"{original['name']} (copy {n})"
        n += 1

    cur.execute(
        """INSERT INTO ingredients (name, unit, current_stock, reorder_threshold, par_level, supplier, location_id)
           VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
        (new_name, original['unit'], original['current_stock'], original['reorder_threshold'],
         original['par_level'], original['supplier'], original['location_id']),
    )
    new_id = cur.fetchone()["id"]
    conn.commit()
    conn.close()
    return new_id


def delete_ingredient(ingredient_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM ingredients WHERE id = %s", (ingredient_id,))
    conn.commit()
    conn.close()


def list_ingredients(location_id: int) -> list[dict]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM ingredients WHERE location_id = %s ORDER BY name", (location_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Dishes
# ---------------------------------------------------------------------------

def add_dish(location_id: int, name: str) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO dishes (name, location_id) VALUES (%s, %s) RETURNING id",
        (name, location_id),
    )
    new_id = cur.fetchone()["id"]
    conn.commit()
    conn.close()
    return new_id


def update_dish(dish_id: int, name: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE dishes SET name = %s WHERE id = %s", (name, dish_id))
    conn.commit()
    conn.close()


def delete_dish(dish_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM dishes WHERE id = %s", (dish_id,))
    conn.commit()
    conn.close()


def list_dishes(location_id: int) -> list[dict]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM dishes WHERE location_id = %s ORDER BY name", (location_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def find_ingredient_by_name(location_id: int, name: str) -> dict | None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM ingredients WHERE name = %s AND location_id = %s",
        (name, location_id),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def find_dish_by_name(location_id: int, name: str) -> dict | None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM dishes WHERE name = %s AND location_id = %s",
        (name, location_id),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Recipes
# ---------------------------------------------------------------------------

def upsert_recipe_item(dish_id: int, ingredient_id: int, qty_per_dish: float):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO recipe_items (dish_id, ingredient_id, qty_per_dish)
           VALUES (%s, %s, %s)
           ON CONFLICT (dish_id, ingredient_id) DO UPDATE SET qty_per_dish = EXCLUDED.qty_per_dish""",
        (dish_id, ingredient_id, qty_per_dish),
    )
    conn.commit()
    conn.close()


def remove_recipe_item(dish_id: int, ingredient_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM recipe_items WHERE dish_id = %s AND ingredient_id = %s",
        (dish_id, ingredient_id),
    )
    conn.commit()
    conn.close()


def set_recipe(dish_id: int, ingredient_qty_pairs: list[tuple[int, float]]):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM recipe_items WHERE dish_id = %s", (dish_id,))
    cur.executemany(
        "INSERT INTO recipe_items (dish_id, ingredient_id, qty_per_dish) VALUES (%s, %s, %s)",
        [(dish_id, ing_id, qty) for ing_id, qty in ingredient_qty_pairs],
    )
    conn.commit()
    conn.close()


def get_recipe_for_dish(dish_id: int) -> list[dict]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """SELECT ri.ingredient_id, i.name AS ingredient_name, i.unit, ri.qty_per_dish
           FROM recipe_items ri JOIN ingredients i ON i.id = ri.ingredient_id
           WHERE ri.dish_id = %s""",
        (dish_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Order report
# ---------------------------------------------------------------------------

def get_dish_sales_for_date(location_id: int, date: str) -> dict[str, int]:
    """Returns {dish_name: qty_sold} for a specific date, used in the daily email report."""
    the_date = _to_date(date)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT d.name AS dish, SUM(se.qty_sold) AS qty_sold
        FROM sales_entries se
        JOIN dishes d ON d.id = se.dish_id
        WHERE se.location_id = %s AND se.date = %s
        GROUP BY d.name
        """,
        (location_id, the_date),
    )
    rows = cur.fetchall()
    conn.close()
    return {row["dish"]: int(row["qty_sold"]) for row in rows}


def _build_ingredients_csv(location_id: int) -> str:
    """Current ingredients as CSV text — same columns as the export/import format."""
    import csv, io
    rows = list_ingredients(location_id)
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["name", "unit", "current_stock", "reorder_threshold", "par_level", "supplier"])
    for r in rows:
        writer.writerow([
            r["name"], r["unit"], r["current_stock"],
            r["reorder_threshold"], r["par_level"], r["supplier"] or "",
        ])
    return buf.getvalue()


def _build_recipes_csv(location_id: int) -> str:
    """Current recipes as CSV text — same columns as the export/import format."""
    import csv, io
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["dish", "ingredient", "qty_per_dish"])
    for d in list_dishes(location_id):
        for item in get_recipe_for_dish(d["id"]):
            writer.writerow([d["name"], item["ingredient_name"], item["qty_per_dish"]])
    return buf.getvalue()


def _latest_snapshot_content(location_id: int, snapshot_type: str) -> str | None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT content FROM data_snapshots WHERE location_id = %s AND snapshot_type = %s "
        "ORDER BY created_at DESC LIMIT 1",
        (location_id, snapshot_type),
    )
    row = cur.fetchone()
    conn.close()
    return row["content"] if row else None


def save_snapshots(location_id: int, reason: str):
    """
    Stores the current ingredients and recipes as retrievable versions.
    Skips writing when the content is identical to the most recent snapshot,
    so the version list only contains points where something actually changed.
    """
    conn = get_connection()
    cur = conn.cursor()
    for snapshot_type, content in (
        ("ingredients", _build_ingredients_csv(location_id)),
        ("recipes", _build_recipes_csv(location_id)),
    ):
        if content == _latest_snapshot_content(location_id, snapshot_type):
            continue
        cur.execute(
            "INSERT INTO data_snapshots (location_id, snapshot_type, content, reason) "
            "VALUES (%s, %s, %s, %s)",
            (location_id, snapshot_type, content, reason),
        )
    conn.commit()
    conn.close()


def list_snapshots(location_id: int, snapshot_type: str, limit: int = 50) -> list[dict]:
    """Returns saved versions, most recent first."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, reason, created_at FROM data_snapshots "
        "WHERE location_id = %s AND snapshot_type = %s ORDER BY created_at DESC LIMIT %s",
        (location_id, snapshot_type, limit),
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_snapshot_content(snapshot_id: int) -> str | None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT content FROM data_snapshots WHERE id = %s", (snapshot_id,))
    row = cur.fetchone()
    conn.close()
    return row["content"] if row else None


def log_activity(location_id: int, action: str, details: str = "", snapshot: bool = True):
    """
    Records one entry in the activity log — call this after any change the user makes.
    When snapshot=True (the default), also stores the resulting ingredient and recipe
    lists so that version can be downloaded later. Pass snapshot=False for actions
    that don't change data (exports, sending an email).
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO activity_log (location_id, action, details) VALUES (%s, %s, %s)",
        (location_id, action, details),
    )
    conn.commit()
    conn.close()

    if snapshot:
        label = f"{action}: {details}" if details else action
        save_snapshots(location_id, label)


def get_activity_log(location_id: int, limit: int = 300) -> list[dict]:
    """Returns recent activity log entries, most recent first."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT action, details, created_at FROM activity_log WHERE location_id = %s "
        "ORDER BY created_at DESC LIMIT %s",
        (location_id, limit),
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_order_report(location_id: int) -> list[dict]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT name, unit, current_stock, reorder_threshold, par_level, supplier
        FROM ingredients
        WHERE location_id = %s
        ORDER BY supplier, name
        """,
        (location_id,),
    )
    rows = cur.fetchall()
    conn.close()

    report = []
    for row in rows:
        needs_order = row["current_stock"] < row["reorder_threshold"]
        suggested_qty = max(row["par_level"] - row["current_stock"], 0) if needs_order else 0
        report.append({
            "ingredient": row["name"],
            "unit": row["unit"],
            "current_stock": round(row["current_stock"], 2),
            "reorder_threshold": row["reorder_threshold"],
            "status": "ORDER NOW" if needs_order else "OK",
            "suggested_order_qty": round(suggested_qty, 2),
            "supplier": row["supplier"],
        })
    return report


# ---------------------------------------------------------------------------
# History (for charts)
# ---------------------------------------------------------------------------

def get_usage_history(location_id: int, days: int = 30) -> list[dict]:
    """Daily ingredient usage for the last N days. Returns rows of {date, ingredient, qty_used}."""
    since = date_type.today() - timedelta(days=days)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT se.date, i.name AS ingredient, SUM(se.qty_sold * ri.qty_per_dish) AS qty_used
        FROM sales_entries se
        JOIN recipe_items ri ON ri.dish_id = se.dish_id
        JOIN ingredients i ON i.id = ri.ingredient_id
        WHERE se.location_id = %s AND se.date >= %s
        GROUP BY se.date, i.name
        ORDER BY se.date
        """,
        (location_id, since),
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_sales_history(location_id: int, days: int = 30) -> list[dict]:
    """Daily dish sales for the last N days. Returns rows of {date, dish, qty_sold}."""
    since = date_type.today() - timedelta(days=days)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT se.date, d.name AS dish, SUM(se.qty_sold) AS qty_sold
        FROM sales_entries se
        JOIN dishes d ON d.id = se.dish_id
        WHERE se.location_id = %s AND se.date >= %s
        GROUP BY se.date, d.name
        ORDER BY se.date
        """,
        (location_id, since),
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]
