"""
app.py — Streamlit UI for the ingredient ordering tool.

Run with:
    streamlit run app.py

Pages (pick from the sidebar):
  1. Setup       — add YOUR ingredients, YOUR dishes, and YOUR recipes
                   (includes a CSV bulk-import tab)
  2. Daily Entry — enter today's sales, get usage calculated automatically
  3. Order Report — see what needs ordering right now
  4. History      — charts of ingredient usage and dish sales over time

A single shared password protects the whole app (set in Secrets as
APP_PASSWORD). Everything is scoped to a "location" so one deployment
can serve multiple restaurants/branches — pick or manage locations in
the sidebar.
"""
import streamlit as st
import pandas as pd
import io
from datetime import date
import db
import daily_report

st.set_page_config(page_title="Ingredient Ordering Tool", page_icon="🍽️", layout="wide")


def inject_custom_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500;600&display=swap');

    :root {
        --paper: #FAF8F3;
        --card: #F0ECE1;
        --ink: #2B2B28;
        --ink-soft: #6B6A62;
        --forest: #2F5233;
        --forest-dark: #223D26;
        --clay: #C1440E;
        --clay-bg: #FBEAE1;
        --sage: #6B8F71;
        --sage-bg: #E8EFE8;
        --border: #E0DACB;
    }

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; color: var(--ink); }
    h1, h2, h3 { font-family: 'Fraunces', serif !important; font-weight: 600 !important; color: var(--ink) !important; letter-spacing: -0.01em; }
    h1 { font-size: 2.1rem !important; }

    /* App header */
    .kt-header { display: flex; align-items: baseline; gap: 0.6rem; margin-bottom: 0.1rem; }
    .kt-header .kt-icon { font-size: 1.8rem; }
    .kt-subtitle { font-family: 'Inter', sans-serif; color: var(--ink-soft); font-size: 0.95rem; margin-bottom: 1.4rem; }

    /* Ticket-style bordered containers (st.container(border=True)) */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--card);
        border: 1px solid var(--border) !important;
        border-radius: 6px;
        position: relative;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]::before {
        content: "";
        position: absolute;
        top: 0; left: 14px; right: 14px;
        height: 0;
        border-top: 2px dashed var(--border);
    }

    /* Expanders (dish list) get the same card treatment */
    div[data-testid="stExpander"] {
        background: var(--card);
        border: 1px solid var(--border) !important;
        border-radius: 6px !important;
        margin-bottom: 0.5rem;
    }
    div[data-testid="stExpander"] summary {
        font-family: 'Fraunces', serif; font-weight: 600;
    }

    /* Buttons */
    .stButton button, .stFormSubmitButton button {
        font-family: 'Inter', sans-serif; font-weight: 500;
        border-radius: 5px;
    }
    .stButton button[kind="primary"] { background-color: var(--forest); border-color: var(--forest); }
    .stButton button[kind="primary"]:hover { background-color: var(--forest-dark); border-color: var(--forest-dark); }

    /* Monospace for numeric/quantity display */
    .kt-mono { font-family: 'JetBrains Mono', monospace; }

    /* Status badges */
    .kt-badge {
        display: inline-block; font-family: 'JetBrains Mono', monospace;
        font-size: 0.78rem; font-weight: 600; letter-spacing: 0.02em;
        padding: 3px 9px; border-radius: 4px; white-space: nowrap;
    }
    .kt-badge-order { background: var(--clay-bg); color: var(--clay); }
    .kt-badge-ok { background: var(--sage-bg); color: var(--forest); }

    /* Sidebar location badge */
    .kt-location-badge {
        font-family: 'JetBrains Mono', monospace; font-size: 0.85rem;
        background: var(--card); border: 1px dashed var(--border);
        border-radius: 5px; padding: 6px 10px; margin-bottom: 0.5rem;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] { background: var(--card); border-right: 1px solid var(--border); }

    /* Hide Streamlit default chrome for a cleaner look */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }

    /* Mobile responsiveness */
    @media (max-width: 640px) {
        h1 { font-size: 1.5rem !important; }
        .kt-header .kt-icon { font-size: 1.4rem; }
        .block-container { padding-left: 1rem !important; padding-right: 1rem !important; padding-top: 2rem !important; }
        div[data-testid="stVerticalBlockBorderWrapper"] { padding: 0.5rem !important; }
        .kt-badge { font-size: 0.72rem; padding: 2px 7px; }
    }
    </style>
    """, unsafe_allow_html=True)


def status_badge(status: str) -> str:
    if status == "ORDER NOW":
        return '<span class="kt-badge kt-badge-order">⚠ ORDER NOW</span>'
    return '<span class="kt-badge kt-badge-ok">✓ OK</span>'


# =============================================================================
# PASSWORD PROTECTION
# =============================================================================
def check_password():
    if st.session_state.get("authenticated"):
        return True

    inject_custom_css()
    st.markdown('<div class="kt-header"><span class="kt-icon">🍽️</span><h1>Ingredient Ordering Tool</h1></div>', unsafe_allow_html=True)
    st.markdown('<div class="kt-subtitle">Enter your password to continue</div>', unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        pw = st.text_input("Password", type="password", label_visibility="collapsed", placeholder="Password")
        if st.button("Log in", type="primary", use_container_width=True):
            try:
                correct_pw = st.secrets["APP_PASSWORD"]
            except Exception:
                st.error("APP_PASSWORD is not set in this app's Secrets. Add it, then reload.")
                return False
            if pw == correct_pw:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Incorrect password.")
    return False


if not check_password():
    st.stop()

db.init_db()
inject_custom_css()

st.markdown('<div class="kt-header"><span class="kt-icon">🍽️</span><h1>Ingredient Ordering Tool</h1></div>', unsafe_allow_html=True)


def confirm_delete(item_key: str, item_label: str, delete_fn):
    """Two-step confirm-before-delete control, reused throughout the app."""
    confirm_flag = f"confirm_delete_{item_key}"
    if st.session_state.get(confirm_flag):
        st.warning(f"Delete **{item_label}**? This cannot be undone.")
        cc1, cc2 = st.columns(2)
        if cc1.button("Yes, delete", key=f"yes_{item_key}", type="primary"):
            delete_fn()
            st.session_state[confirm_flag] = False
            st.rerun()
        if cc2.button("Cancel", key=f"cancel_{item_key}"):
            st.session_state[confirm_flag] = False
            st.rerun()
    else:
        if st.button("🗑️ Delete", key=f"del_{item_key}"):
            st.session_state[confirm_flag] = True
            st.rerun()


# =============================================================================
# LOCATION SELECTOR (sidebar) — every page below operates on the selected one
# =============================================================================
st.sidebar.markdown("### 📍 Location")
locations = db.list_locations()

if not locations:
    st.sidebar.warning("No locations yet.")
    new_loc_name = st.sidebar.text_input("Create your first location", value="Main")
    if st.sidebar.button("Create location"):
        if new_loc_name.strip():
            db.add_location(new_loc_name.strip())
            st.rerun()
    st.stop()

location_names = [loc["name"] for loc in locations]
selected_location_name = st.sidebar.selectbox("Active location", location_names, label_visibility="collapsed")
selected_location = next(loc for loc in locations if loc["name"] == selected_location_name)
LOCATION_ID = selected_location["id"]
st.sidebar.markdown(f'<div class="kt-location-badge">📍 {selected_location_name}</div>', unsafe_allow_html=True)

with st.sidebar.expander("Manage locations"):
    st.write("**Add a location**")
    add_col1, add_col2 = st.columns([3, 1])
    new_name = add_col1.text_input("Name", key="new_loc_name", label_visibility="collapsed")
    if add_col2.button("Add", key="add_loc_btn"):
        if new_name.strip():
            db.add_location(new_name.strip())
            st.rerun()

    st.write("**Rename or delete current location**")
    rename_val = st.text_input("Rename", value=selected_location["name"], key="rename_loc")
    if st.button("💾 Save name", key="save_loc_name"):
        if rename_val.strip():
            db.update_location(LOCATION_ID, rename_val.strip())
            st.rerun()
    if len(locations) > 1:
        confirm_delete(
            f"loc_{LOCATION_ID}", selected_location["name"],
            lambda: db.delete_location(LOCATION_ID),
        )
    else:
        st.caption("Can't delete your only location.")

page = st.sidebar.radio("Go to", ["1. Setup", "2. Daily Entry", "3. Order Report", "4. History", "5. Activity Log"])

# =============================================================================
# PAGE 1 — SETUP: add your own ingredients, dishes, recipes, or bulk import
# =============================================================================
if page == "1. Setup":
    tab_ing, tab_dish, tab_prep, tab_import = st.tabs(
        ["Ingredients", "Dishes", "Prep Items", "Import / Export CSV"]
    )

    # --- Ingredients tab ---
    with tab_ing:
        st.subheader("Add an ingredient")
        with st.form("add_ingredient_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            name = c1.text_input("Name (e.g. Mozzarella)")
            unit = c2.selectbox("Unit", ["kg", "g", "l", "ml", "pcs"])
            supplier = c3.text_input("Supplier (optional)")
            c4, c5, c6 = st.columns(3)
            current_stock = c4.number_input("Current stock", min_value=0.0, step=0.1)
            reorder_threshold = c5.number_input("Reorder threshold (order below this)", min_value=0.0, step=0.1)
            par_level = c6.number_input("Par level (order back up to this)", min_value=0.0, step=0.1)
            submitted = st.form_submit_button("Add ingredient")
            if submitted:
                if not name:
                    st.error("Name is required.")
                else:
                    db.add_ingredient(LOCATION_ID, name, unit, current_stock, reorder_threshold, par_level, supplier)
                    db.log_activity(LOCATION_ID, "Added ingredient", f"{name} ({unit})")
                    st.success(f"Added '{name}'")
                    st.rerun()

        st.subheader("Your ingredients")
        ingredients = db.list_ingredients(LOCATION_ID)
        units_list = ["kg", "g", "l", "ml", "pcs"]
        if not ingredients:
            st.info("No ingredients yet — add your first one above, or use the Import tab.")
        else:
            if "selected_ingredients" not in st.session_state:
                st.session_state.selected_ingredients = set()

            # Bulk action bar
            selected_count = len(st.session_state.selected_ingredients)
            bar1, bar2, bar3, bar4 = st.columns([2, 1, 1, 1])
            bar1.markdown(f"**{selected_count} selected**" if selected_count else "&nbsp;", unsafe_allow_html=True)
            if bar2.button("Select all", key="select_all_ing"):
                st.session_state.selected_ingredients = {ing['id'] for ing in ingredients}
                st.rerun()
            if bar3.button("Clear", key="clear_sel_ing", disabled=selected_count == 0):
                st.session_state.selected_ingredients = set()
                st.rerun()
            duplicate_clicked = bar4.button("⧉ Duplicate", key="dup_sel_ing", disabled=selected_count == 0)

            if duplicate_clicked:
                dup_names = [ing['name'] for ing in ingredients if ing['id'] in st.session_state.selected_ingredients]
                for ing_id in st.session_state.selected_ingredients:
                    db.duplicate_ingredient(ing_id)
                db.log_activity(LOCATION_ID, f"Duplicated {selected_count} ingredient(s)", ", ".join(dup_names))
                st.session_state.selected_ingredients = set()
                st.success(f"Duplicated {selected_count} ingredient(s).")
                st.rerun()

            if selected_count > 0:
                def _bulk_delete_ingredients():
                    del_names = [ing['name'] for ing in ingredients if ing['id'] in st.session_state.selected_ingredients]
                    for ing_id in list(st.session_state.selected_ingredients):
                        db.delete_ingredient(ing_id)
                    db.log_activity(LOCATION_ID, f"Deleted {len(del_names)} ingredient(s)", ", ".join(del_names))
                    st.session_state.selected_ingredients = set()

                confirm_delete(
                    "bulk_ingredients", f"{selected_count} selected ingredient(s)",
                    _bulk_delete_ingredients,
                )

            for ing in ingredients:
                with st.container(border=True):
                    csel, c1, c6 = st.columns([0.4, 4.6, 1])
                    is_selected = csel.checkbox(
                        "select", value=ing['id'] in st.session_state.selected_ingredients,
                        key=f"selcb_{ing['id']}", label_visibility="collapsed",
                    )
                    if is_selected:
                        st.session_state.selected_ingredients.add(ing['id'])
                    else:
                        st.session_state.selected_ingredients.discard(ing['id'])
                    with c1:
                        st.markdown(f"**{ing['name']}**", unsafe_allow_html=True)
                        st.markdown(
                            f'<span class="kt-mono">{ing["current_stock"]} {ing["unit"]}</span> '
                            f'<span style="color:var(--ink-soft); font-size:0.85rem;">on hand · reorder below {ing["reorder_threshold"]} · par {ing["par_level"]}</span>',
                            unsafe_allow_html=True,
                        )
                        if ing['supplier']:
                            st.caption(f"Supplier: {ing['supplier']}")
                with c6.popover("⋯"):
                    st.write(f"**Edit {ing['name']}**")
                    e1, e2 = st.columns(2)
                    edit_name = e1.text_input("Name", value=ing['name'], key=f"ename_{ing['id']}")
                    edit_unit = e2.selectbox(
                        "Unit", units_list,
                        index=units_list.index(ing['unit']) if ing['unit'] in units_list else 0,
                        key=f"eunit_{ing['id']}",
                    )
                    e3, e4, e5 = st.columns(3)
                    edit_stock = e3.number_input("Current stock", min_value=0.0, step=0.1,
                                                  value=float(ing['current_stock']), key=f"estock_{ing['id']}")
                    edit_threshold = e4.number_input("Reorder threshold", min_value=0.0, step=0.1,
                                                       value=float(ing['reorder_threshold']), key=f"ethresh_{ing['id']}")
                    edit_par = e5.number_input("Par level", min_value=0.0, step=0.1,
                                                value=float(ing['par_level']), key=f"epar_{ing['id']}")
                    edit_supplier = st.text_input("Supplier", value=ing['supplier'] or "", key=f"esup_{ing['id']}")

                    if st.button("💾 Save changes", key=f"esave_{ing['id']}"):
                        db.update_ingredient(
                            ing['id'], name=edit_name, unit=edit_unit,
                            current_stock=edit_stock, reorder_threshold=edit_threshold,
                            par_level=edit_par, supplier=edit_supplier,
                        )
                        db.log_activity(LOCATION_ID, "Edited ingredient", f"{ing['name']} → {edit_name}")
                        st.success("Saved")
                        st.rerun()

                    st.divider()
                    confirm_delete(
                        f"ing_{ing['id']}", ing['name'],
                        lambda ing_id=ing['id'], ing_name=ing['name']: (
                            db.delete_ingredient(ing_id),
                            db.log_activity(LOCATION_ID, "Deleted ingredient", ing_name),
                        ),
                    )

    # --- Dishes tab: add dishes, and manage each dish's ingredient list inline ---
    with tab_dish:
        st.subheader("Add a dish")
        with st.form("add_dish_form", clear_on_submit=True):
            dish_name = st.text_input("Dish name (e.g. Margherita Pizza)")
            submitted = st.form_submit_button("Add dish")
            if submitted:
                if not dish_name:
                    st.error("Name is required.")
                else:
                    db.add_dish(LOCATION_ID, dish_name)
                    db.log_activity(LOCATION_ID, "Added dish", dish_name)
                    st.success(f"Added '{dish_name}'")
                    st.rerun()

        st.subheader("Your dishes")
        dishes = db.list_dishes(LOCATION_ID)
        all_ingredients = db.list_ingredients(LOCATION_ID)

        if not dishes:
            st.info("No dishes yet — add your first one above, or use the Import tab.")
        elif not all_ingredients:
            st.warning("Add some ingredients on the Ingredients tab first, then come back here to build each dish's menu.")
        else:
            for d in dishes:
                recipe_items = db.get_recipe_for_dish(d['id'])
                item_count = len(recipe_items)
                label = f"🍽️ {d['name']}  ({item_count} ingredient{'s' if item_count != 1 else ''})"

                with st.expander(label):
                    # Rename this dish
                    rn1, rn2 = st.columns([4, 1])
                    edit_dish_name = rn1.text_input(
                        "Dish name", value=d['name'], key=f"ename_dish_{d['id']}",
                        label_visibility="collapsed",
                    )
                    if rn2.button("💾 Save name", key=f"savename_{d['id']}"):
                        if edit_dish_name.strip():
                            db.update_dish(d['id'], edit_dish_name.strip())
                            db.log_activity(LOCATION_ID, "Renamed dish", f"{d['name']} → {edit_dish_name.strip()}")
                            st.success("Renamed")
                            st.rerun()
                        else:
                            st.error("Name can't be empty.")

                    st.divider()

                    # Current ingredients in this dish's recipe — each row editable/removable
                    if recipe_items:
                        st.caption("Current recipe:")
                        for item in recipe_items:
                            rc1, rc2, rc3, rc4 = st.columns([3, 1, 1, 1])
                            rc1.write(item['ingredient_name'])
                            rc2.write(f"{item['qty_per_dish']} {item['unit']}")
                            rc3.write("")
                            with rc4.popover("⋯"):
                                st.write(f"**Edit {item['ingredient_name']}**")
                                new_qty = st.number_input(
                                    f"Amount per serving ({item['unit']})", min_value=0.0,
                                    value=float(item['qty_per_dish']), step=0.01,
                                    key=f"eqty_{d['id']}_{item['ingredient_id']}",
                                )
                                if st.button("💾 Save changes", key=f"esaverec_{d['id']}_{item['ingredient_id']}"):
                                    db.upsert_recipe_item(d['id'], item['ingredient_id'], new_qty)
                                    db.log_activity(LOCATION_ID, "Edited recipe", f"{d['name']}: {item['ingredient_name']} → {new_qty} {item['unit']}")
                                    st.success("Saved")
                                    st.rerun()

                                st.divider()
                                confirm_delete(
                                    f"recipe_{d['id']}_{item['ingredient_id']}", item['ingredient_name'],
                                    lambda did=d['id'], iid=item['ingredient_id'], dname=d['name'], iname=item['ingredient_name']: (
                                        db.remove_recipe_item(did, iid),
                                        db.log_activity(LOCATION_ID, "Removed ingredient from recipe", f"{dname}: {iname}"),
                                    ),
                                )
                    else:
                        st.caption("No ingredients added to this dish yet.")

                    # Add a new ingredient to this dish
                    st.write("**Add ingredient to this dish:**")
                    already_used_ids = {item['ingredient_id'] for item in recipe_items}
                    available = [i for i in all_ingredients if i['id'] not in already_used_ids]

                    if not available:
                        st.caption("All existing ingredients are already in this recipe.")
                    else:
                        ac1, ac2, ac3 = st.columns([3, 2, 1])
                        pick_name = ac1.selectbox(
                            "Ingredient", [i['name'] for i in available],
                            key=f"pick_{d['id']}", label_visibility="collapsed",
                        )
                        pick = next(i for i in available if i['name'] == pick_name)
                        add_qty = ac2.number_input(
                            f"Amount per serving ({pick['unit']})", min_value=0.0, step=0.01,
                            key=f"addqty_{d['id']}",
                        )
                        if ac3.button("Add", key=f"addbtn_{d['id']}"):
                            if add_qty > 0:
                                db.upsert_recipe_item(d['id'], pick['id'], add_qty)
                                db.log_activity(LOCATION_ID, "Added ingredient to recipe", f"{d['name']}: {pick_name} ({add_qty} {pick['unit']})")
                                st.rerun()
                            else:
                                st.error("Enter an amount greater than 0.")

                    st.divider()
                    confirm_delete(
                        f"dish_{d['id']}", d['name'],
                        lambda did=d['id'], dname=d['name']: (
                            db.delete_dish(did),
                            db.log_activity(LOCATION_ID, "Deleted dish", dname),
                        ),
                    )

    # --- Prep Items tab: ingredients you make in-house from other ingredients ---
    with tab_prep:
        st.subheader("Prep items")
        st.caption("A prep item is something you make rather than buy — pizza sauce, dough, dressing. "
                   "It has its own recipe, but behaves like a normal ingredient inside a dish "
                   "(e.g. 100g of sauce per pizza).")

        all_ings = db.list_ingredients(LOCATION_ID)
        if not all_ings:
            st.warning("Add some ingredients first on the Ingredients tab.")
        else:
            prep_items = [i for i in all_ings if i.get("is_prep")]
            non_prep = [i for i in all_ings if not i.get("is_prep")]

            with st.expander("➕ Turn an ingredient into a prep item"):
                if not non_prep:
                    st.caption("Every ingredient is already a prep item.")
                else:
                    p1, p2, p3 = st.columns([2, 1, 1])
                    new_prep_name = p1.selectbox("Ingredient", [i["name"] for i in non_prep], key="new_prep_pick")
                    new_prep = next(i for i in non_prep if i["name"] == new_prep_name)
                    batch_yield = p2.number_input(
                        f"One batch makes ({new_prep['unit']})", min_value=0.0, step=1.0, key="new_prep_yield",
                    )
                    mode_label = p3.selectbox(
                        "Stock tracking", ["Track batches", "Use raw components"], key="new_prep_mode",
                    )
                    if st.button("Make it a prep item", key="make_prep_btn"):
                        if batch_yield <= 0:
                            st.error("Batch yield must be greater than 0.")
                        else:
                            mode = "stock" if mode_label == "Track batches" else "explode"
                            db.set_prep_settings(new_prep["id"], True, batch_yield, mode)
                            db.log_activity(LOCATION_ID, "Created prep item",
                                            f"{new_prep_name} (batch = {batch_yield} {new_prep['unit']}, {mode})")
                            st.rerun()
                    st.caption("**Track batches** — you make sauce ahead of time and want to know how much "
                               "sauce is in the fridge. **Use raw components** — no separate sauce stock; "
                               "selling a pizza deducts tomatoes, oil and garlic directly.")

            if not prep_items:
                st.info("No prep items yet — use the section above to create your first one.")
            else:
                for prep in prep_items:
                    components = db.get_prep_recipe(prep["id"])
                    mode_txt = "tracked as stock" if prep["consumption_mode"] == "stock" else "uses raw components"
                    label = (f"🧪 {prep['name']} — 1 batch = {prep['batch_yield_qty']} {prep['unit']} "
                             f"({len(components)} component{'s' if len(components) != 1 else ''}, {mode_txt})")

                    with st.expander(label):
                        s1, s2, s3 = st.columns([1, 1, 1])
                        edit_yield = s1.number_input(
                            f"One batch makes ({prep['unit']})", min_value=0.0, step=1.0,
                            value=float(prep["batch_yield_qty"]), key=f"pyield_{prep['id']}",
                        )
                        edit_mode_label = s2.selectbox(
                            "Stock tracking", ["Track batches", "Use raw components"],
                            index=0 if prep["consumption_mode"] == "stock" else 1,
                            key=f"pmode_{prep['id']}",
                        )
                        if s3.button("💾 Save settings", key=f"psave_{prep['id']}"):
                            mode = "stock" if edit_mode_label == "Track batches" else "explode"
                            db.set_prep_settings(prep["id"], True, edit_yield, mode)
                            db.log_activity(LOCATION_ID, "Edited prep item settings",
                                            f"{prep['name']}: batch = {edit_yield} {prep['unit']}, {mode}")
                            st.rerun()

                        st.divider()
                        st.write(f"**What goes into one batch ({prep['batch_yield_qty']} {prep['unit']}):**")
                        if components:
                            for comp in components:
                                cc1, cc2, cc3 = st.columns([3, 1, 1])
                                cc1.write(comp["component_name"])
                                cc2.write(f"{comp['qty_per_batch']} {comp['unit']}")
                                with cc3.popover("⋯"):
                                    new_cqty = st.number_input(
                                        f"Amount per batch ({comp['unit']})", min_value=0.0, step=0.1,
                                        value=float(comp["qty_per_batch"]),
                                        key=f"pcq_{prep['id']}_{comp['component_ingredient_id']}",
                                    )
                                    if st.button("💾 Save", key=f"pcsave_{prep['id']}_{comp['component_ingredient_id']}"):
                                        db.upsert_prep_component(prep["id"], comp["component_ingredient_id"], new_cqty)
                                        db.log_activity(LOCATION_ID, "Edited prep recipe",
                                                        f"{prep['name']}: {comp['component_name']} → {new_cqty} {comp['unit']}")
                                        st.rerun()
                                    st.divider()
                                    confirm_delete(
                                        f"prepcomp_{prep['id']}_{comp['component_ingredient_id']}",
                                        comp["component_name"],
                                        lambda pid=prep["id"], cid=comp["component_ingredient_id"],
                                               pname=prep["name"], cname=comp["component_name"]: (
                                            db.remove_prep_component(pid, cid),
                                            db.log_activity(LOCATION_ID, "Removed component from prep item",
                                                            f"{pname}: {cname}"),
                                        ),
                                    )
                        else:
                            st.caption("No components yet — add the first one below.")

                        used_ids = {c["component_ingredient_id"] for c in components}
                        available_comps = [i for i in all_ings
                                            if i["id"] not in used_ids and i["id"] != prep["id"]]
                        if available_comps:
                            ac1, ac2, ac3 = st.columns([3, 2, 1])
                            comp_name = ac1.selectbox(
                                "Component", [i["name"] for i in available_comps],
                                key=f"pcpick_{prep['id']}", label_visibility="collapsed",
                            )
                            comp = next(i for i in available_comps if i["name"] == comp_name)
                            comp_qty = ac2.number_input(
                                f"Amount per batch ({comp['unit']})", min_value=0.0, step=0.1,
                                key=f"pcaddqty_{prep['id']}",
                            )
                            if ac3.button("Add", key=f"pcadd_{prep['id']}"):
                                if comp_qty <= 0:
                                    st.error("Enter an amount greater than 0.")
                                else:
                                    try:
                                        db.upsert_prep_component(prep["id"], comp["id"], comp_qty)
                                        db.log_activity(LOCATION_ID, "Added component to prep item",
                                                        f"{prep['name']}: {comp_name} ({comp_qty} {comp['unit']})")
                                        st.rerun()
                                    except ValueError as e:
                                        st.error(str(e))

                        if prep["consumption_mode"] == "stock" and components:
                            st.divider()
                            st.write("**Made a batch?**")
                            b1, b2 = st.columns([2, 1])
                            n_batches = b1.number_input(
                                "How many batches", min_value=0.0, step=0.5, value=1.0,
                                key=f"pbatch_{prep['id']}",
                            )
                            if b2.button("Record production", key=f"pprod_{prep['id']}", type="primary"):
                                if n_batches <= 0:
                                    st.error("Enter a number greater than 0.")
                                else:
                                    db.produce_batch(LOCATION_ID, prep["id"], n_batches)
                                    db.log_activity(
                                        LOCATION_ID, "Produced prep batch",
                                        f"{prep['name']}: {n_batches} batch(es) "
                                        f"= {n_batches * float(prep['batch_yield_qty'])} {prep['unit']}",
                                    )
                                    st.success("Components deducted, stock added.")
                                    st.rerun()
                            st.caption("This deducts the components from stock and adds the finished "
                                       "quantity to this item's stock.")

                        st.divider()
                        if st.button("Convert back to a normal ingredient", key=f"punprep_{prep['id']}"):
                            db.set_prep_settings(prep["id"], False, 0, "stock")
                            db.log_activity(LOCATION_ID, "Converted prep item to normal ingredient", prep["name"])
                            st.rerun()

    # --- Import tab: bulk-add ingredients and recipes via CSV ---
    with tab_import:
        st.subheader("Export current data")
        st.caption("Download your current ingredients (with current stock levels) and recipes. "
                   "After a delivery, edit the stock numbers in this file and re-upload it below — "
                   "matching ingredients get updated in place, nothing gets duplicated.")

        exp_col1, exp_col2 = st.columns(2)
        with exp_col1:
            export_ingredients = db.list_ingredients(LOCATION_ID)
            if export_ingredients:
                export_ing_df = pd.DataFrame([{
                    "name": i["name"], "unit": i["unit"], "current_stock": i["current_stock"],
                    "reorder_threshold": i["reorder_threshold"], "par_level": i["par_level"],
                    "supplier": i["supplier"] or "",
                } for i in export_ingredients])
                st.download_button(
                    "⬇️ Export ingredients", export_ing_df.to_csv(index=False),
                    file_name="ingredients_export.csv", key="export_ing_btn",
                    on_click=lambda: db.log_activity(LOCATION_ID, "Exported ingredients CSV", f"{len(export_ingredients)} ingredient(s)", snapshot=False),
                )
            else:
                st.caption("No ingredients yet to export.")

        with exp_col2:
            export_dishes = db.list_dishes(LOCATION_ID)
            recipe_rows = []
            for d in export_dishes:
                for item in db.get_recipe_for_dish(d["id"]):
                    recipe_rows.append({
                        "dish": d["name"], "ingredient": item["ingredient_name"],
                        "qty_per_dish": item["qty_per_dish"],
                    })
            if recipe_rows:
                export_recipe_df = pd.DataFrame(recipe_rows)
                st.download_button(
                    "⬇️ Export recipes", export_recipe_df.to_csv(index=False),
                    file_name="recipes_export.csv", key="export_recipe_btn",
                    on_click=lambda: db.log_activity(LOCATION_ID, "Exported recipes CSV", f"{len(recipe_rows)} recipe line(s)", snapshot=False),
                )
            else:
                st.caption("No recipes yet to export.")

        st.divider()
        st.subheader("Import / update ingredients")
        st.caption("CSV columns: name, unit, current_stock, reorder_threshold, par_level, supplier "
                   "(current_stock/reorder_threshold/par_level/supplier are optional, default to 0/empty). "
                   "If an ingredient name already exists, its values are updated — nothing is duplicated.")

        sample_ing_csv = "name,unit,current_stock,reorder_threshold,par_level,supplier\nMozzarella,kg,5,3,10,Metro\nTomato Sauce,l,8,4,15,Metro\n"
        st.download_button("Download template", sample_ing_csv, file_name="ingredients_template.csv")

        ing_file = st.file_uploader("Upload ingredients CSV", type="csv", key="ing_csv")
        if ing_file is not None:
            try:
                df = pd.read_csv(ing_file)
                df.columns = [c.strip().lower() for c in df.columns]
                if "name" not in df.columns or "unit" not in df.columns:
                    st.error("CSV must have at least 'name' and 'unit' columns.")
                else:
                    if st.button("Import ingredients"):
                        added, updated = 0, 0
                        for _, row in df.iterrows():
                            name = str(row["name"]).strip()
                            if not name or pd.isna(row["name"]):
                                continue
                            unit = str(row.get("unit", "pcs")).strip()
                            current_stock = float(row.get("current_stock", 0) or 0)
                            reorder_threshold = float(row.get("reorder_threshold", 0) or 0)
                            par_level = float(row.get("par_level", 0) or 0)
                            supplier = str(row.get("supplier", "") or "")

                            existing = db.find_ingredient_by_name(LOCATION_ID, name)
                            if existing:
                                db.update_ingredient(
                                    existing["id"], unit=unit, current_stock=current_stock,
                                    reorder_threshold=reorder_threshold, par_level=par_level,
                                    supplier=supplier,
                                )
                                updated += 1
                            else:
                                db.add_ingredient(
                                    LOCATION_ID, name, unit, current_stock,
                                    reorder_threshold, par_level, supplier,
                                )
                                added += 1
                        st.success(f"Added {added} new ingredient(s), updated {updated} existing one(s).")
                        db.log_activity(
                            LOCATION_ID, "Uploaded ingredients CSV",
                            f"{ing_file.name}: added {added}, updated {updated}",
                        )
                        st.rerun()
            except Exception as e:
                st.error(f"Couldn't read that CSV: {e}")

        st.divider()
        st.subheader("Bulk import recipes")
        st.caption("CSV columns: dish, ingredient, qty_per_dish. Dishes are created automatically if new. "
                   "Ingredients must already exist (add them above first).")

        sample_recipe_csv = "dish,ingredient,qty_per_dish\nMargherita Pizza,Mozzarella,0.15\nMargherita Pizza,Tomato Sauce,0.10\n"
        st.download_button("Download template", sample_recipe_csv, file_name="recipes_template.csv")

        recipe_file = st.file_uploader("Upload recipes CSV", type="csv", key="recipe_csv")
        if recipe_file is not None:
            try:
                df = pd.read_csv(recipe_file)
                df.columns = [c.strip().lower() for c in df.columns]
                required = {"dish", "ingredient", "qty_per_dish"}
                if not required.issubset(set(df.columns)):
                    st.error(f"CSV must have columns: {', '.join(required)}")
                else:
                    if st.button("Import recipes"):
                        added, errors = 0, []
                        for _, row in df.iterrows():
                            dish_name = str(row["dish"]).strip()
                            ing_name = str(row["ingredient"]).strip()
                            qty = row["qty_per_dish"]
                            if not dish_name or not ing_name or pd.isna(qty):
                                continue
                            dish = db.find_dish_by_name(LOCATION_ID, dish_name)
                            if not dish:
                                dish_id = db.add_dish(LOCATION_ID, dish_name)
                            else:
                                dish_id = dish["id"]
                            ing = db.find_ingredient_by_name(LOCATION_ID, ing_name)
                            if not ing:
                                errors.append(f"Ingredient '{ing_name}' not found (row for {dish_name}) — skipped.")
                                continue
                            db.upsert_recipe_item(dish_id, ing["id"], float(qty))
                            added += 1
                        st.success(f"Imported {added} recipe line(s).")
                        db.log_activity(LOCATION_ID, "Uploaded recipes CSV", f"{recipe_file.name}: {added} line(s)")
                        if errors:
                            st.warning("\n".join(errors))
                        st.rerun()
            except Exception as e:
                st.error(f"Couldn't read that CSV: {e}")

# =============================================================================
# PAGE 2 — DAILY ENTRY: enter today's sales
# =============================================================================
elif page == "2. Daily Entry":
    st.markdown('<h2 style="margin-bottom:0.2rem;">Daily entry</h2>', unsafe_allow_html=True)
    dishes = db.list_dishes(LOCATION_ID)

    if not dishes:
        st.warning("Add dishes first on the Setup page.")
    else:
        tab_manual, tab_receipt = st.tabs(["Manual Entry", "Upload CSV"])

        with tab_manual:
            entry_date = st.date_input("Date", value=date.today(), key="manual_date")
            st.write("How many of each dish did you sell?")

            sales = {}
            for d in dishes:
                qty = st.number_input(d['name'], min_value=0, step=1, key=f"sales_{d['id']}")
                if qty > 0:
                    sales[d['name']] = qty

            if st.button("Submit sales and update stock", type="primary"):
                if not sales:
                    st.warning("Enter at least one dish quantity above 0.")
                else:
                    date_str = entry_date.isoformat()
                    db.record_sales(LOCATION_ID, date_str, sales)
                    usage = db.calculate_usage_for_date(LOCATION_ID, date_str)
                    db.apply_usage_to_stock(LOCATION_ID, usage)
                    db.log_activity(
                        LOCATION_ID, "Recorded sales (manual)",
                        f"{date_str}: " + ", ".join(f"{k}×{v}" for k, v in sales.items()),
                    )
                    st.success("Sales recorded and stock updated!")
                    st.write("**Ingredients used today:**")
                    for ing_name, qty in usage.items():
                        st.write(f"- {ing_name}: {qty:.2f}")
                    st.info("Check the Order Report page to see what needs ordering.")

        with tab_receipt:
            st.caption("Upload a CSV of today's sales. Columns: **dish, qty_sold** "
                       "(optionally add a **date** column to upload multiple days at once).")
            sample_sales_csv = "dish,qty_sold\nMargherita Pizza,22\nCaesar Salad,9\n"
            st.download_button("Download template", sample_sales_csv, file_name="daily_sales_template.csv", key="sales_template_dl")

            receipt_date = st.date_input("Date (used if CSV has no 'date' column)", value=date.today(), key="receipt_date")
            sales_csv_file = st.file_uploader("Sales CSV", type="csv", key="sales_csv_upload")

            if sales_csv_file is not None:
                try:
                    df = pd.read_csv(sales_csv_file)
                    df.columns = [c.strip().lower() for c in df.columns]
                    if "dish" not in df.columns or "qty_sold" not in df.columns:
                        st.error("CSV must have 'dish' and 'qty_sold' columns.")
                    else:
                        if "date" not in df.columns:
                            df["date"] = receipt_date.isoformat()
                        st.write("**Review before saving** — edit any cell that looks wrong:")
                        edited_df = st.data_editor(df, num_rows="dynamic", key="sales_editor", use_container_width=True)

                        known_dish_names = {d['name'] for d in dishes}
                        unknown = sorted(set(edited_df["dish"].astype(str)) - known_dish_names)
                        if unknown:
                            st.warning(f"These dishes don't exist yet, so their rows will be skipped: {unknown}. "
                                       f"Add them on the Setup page first if needed.")

                        if st.button("✅ Confirm and record sales", type="primary", key="confirm_sales_csv_btn"):
                            by_date = {}
                            for _, row in edited_df.iterrows():
                                dish_name = str(row["dish"]).strip()
                                if dish_name not in known_dish_names:
                                    continue
                                qty = row["qty_sold"]
                                if pd.isna(qty) or qty <= 0:
                                    continue
                                row_date = str(row["date"]).strip()
                                by_date.setdefault(row_date, {})[dish_name] = by_date.setdefault(row_date, {}).get(dish_name, 0) + int(qty)

                            if not by_date:
                                st.warning("No valid rows to record.")
                            else:
                                for row_date, day_sales in by_date.items():
                                    db.record_sales(LOCATION_ID, row_date, day_sales)
                                    usage = db.calculate_usage_for_date(LOCATION_ID, row_date)
                                    db.apply_usage_to_stock(LOCATION_ID, usage)
                                db.log_activity(
                                    LOCATION_ID, "Uploaded sales CSV",
                                    f"{sales_csv_file.name}: {len(by_date)} date(s)",
                                )
                                st.success(f"Recorded sales for {len(by_date)} date(s) and updated stock!")
                                st.rerun()
                except Exception as e:
                    st.error(f"Couldn't read that CSV: {e}")

# =============================================================================
# PAGE 3 — ORDER REPORT
# =============================================================================
elif page == "3. Order Report":
    st.markdown('<h2 style="margin-bottom:0.2rem;">Order report</h2>', unsafe_allow_html=True)
    report = db.get_order_report(LOCATION_ID)

    if not report:
        st.info("No ingredients set up yet.")
    else:
        needs_order = [r for r in report if r['status'] == "ORDER NOW"]
        ok = [r for r in report if r['status'] == "OK"]

        if needs_order:
            st.markdown(f'<p class="kt-subtitle">⚠️ <b>{len(needs_order)}</b> ingredient(s) need ordering</p>', unsafe_allow_html=True)
            for r in needs_order:
                with st.container(border=True):
                    c1, c2 = st.columns([3, 2])
                    with c1:
                        st.markdown(f"**{r['ingredient']}** &nbsp; {status_badge(r['status'])}", unsafe_allow_html=True)
                        st.markdown(f'<span class="kt-mono" style="color:var(--ink-soft); font-size:0.85rem;">on hand: {r["current_stock"]} {r["unit"]}</span>', unsafe_allow_html=True)
                    with c2:
                        st.markdown(f'<span class="kt-mono" style="font-size:1.1rem; color:var(--clay);">order {r["suggested_order_qty"]} {r["unit"]}</span>', unsafe_allow_html=True)
                        st.caption(r["supplier"] or "No supplier set")
        else:
            st.success("Everything is stocked!")

        with st.expander(f"OK — {len(ok)} ingredient(s), no action needed"):
            for r in ok:
                with st.container(border=True):
                    c1, c2 = st.columns([3, 2])
                    with c1:
                        st.markdown(f"**{r['ingredient']}** &nbsp; {status_badge(r['status'])}", unsafe_allow_html=True)
                    with c2:
                        st.markdown(f'<span class="kt-mono">{r["current_stock"]} {r["unit"]}</span>', unsafe_allow_html=True)
                        st.caption(r["supplier"] or "No supplier set")

        st.markdown('<h3 style="margin-top:1.5rem;">Receive a delivery</h3>', unsafe_allow_html=True)
        ingredients = db.list_ingredients(LOCATION_ID)
        if ingredients:
            tab_manual_receive, tab_manifest = st.tabs(["Manual", "Upload CSV"])

            with tab_manual_receive:
                st.caption("Use this after a delivery arrives, or to correct stock after a physical count.")
                with st.container(border=True):
                    c1, c2 = st.columns(2)
                    ing_name = c1.selectbox("Ingredient", [i['name'] for i in ingredients])
                    adjust_qty = c2.number_input("Quantity received (or negative to subtract)", step=0.1)
                    if st.button("Apply adjustment", type="primary"):
                        db.receive_delivery(LOCATION_ID, {ing_name: adjust_qty})
                        db.log_activity(LOCATION_ID, "Manual stock adjustment", f"{ing_name}: {adjust_qty:+}")
                        st.success(f"Updated stock for {ing_name}")
                        st.rerun()

            with tab_manifest:
                st.caption("Upload a CSV of your supplier's delivery. Columns: **ingredient, qty_received**.")
                sample_manifest_csv = "ingredient,qty_received\nMozzarella,10\nTomato Sauce,20\n"
                st.download_button("Download template", sample_manifest_csv, file_name="order_manifest_template.csv", key="manifest_template_dl")

                manifest_csv_file = st.file_uploader("Order manifest CSV", type="csv", key="manifest_csv_upload")

                if manifest_csv_file is not None:
                    try:
                        df = pd.read_csv(manifest_csv_file)
                        df.columns = [c.strip().lower() for c in df.columns]
                        if "ingredient" not in df.columns or "qty_received" not in df.columns:
                            st.error("CSV must have 'ingredient' and 'qty_received' columns.")
                        else:
                            st.write("**Review before adding to stock** — edit any cell that looks wrong:")
                            edited_df = st.data_editor(df, num_rows="dynamic", key="manifest_editor", use_container_width=True)

                            known_ing_names = {i['name'] for i in ingredients}
                            unknown = sorted(set(edited_df["ingredient"].astype(str)) - known_ing_names)
                            if unknown:
                                st.warning(f"These ingredients don't exist yet, so their rows will be skipped: {unknown}. "
                                           f"Add them on the Setup page first if needed.")

                            if st.button("✅ Confirm and add to stock", type="primary", key="confirm_manifest_csv_btn"):
                                deliveries = {}
                                for _, row in edited_df.iterrows():
                                    ing_name_row = str(row["ingredient"]).strip()
                                    if ing_name_row not in known_ing_names:
                                        continue
                                    qty = row["qty_received"]
                                    if pd.isna(qty) or qty <= 0:
                                        continue
                                    deliveries[ing_name_row] = deliveries.get(ing_name_row, 0) + float(qty)

                                if not deliveries:
                                    st.warning("No valid rows to add.")
                                else:
                                    db.receive_delivery(LOCATION_ID, deliveries)
                                    db.log_activity(
                                        LOCATION_ID, "Uploaded order manifest CSV",
                                        f"{manifest_csv_file.name}: {len(deliveries)} item(s)",
                                    )
                                    st.success(f"Added {len(deliveries)} item(s) to stock!")
                                    st.rerun()
                    except Exception as e:
                        st.error(f"Couldn't read that CSV: {e}")

        st.markdown('<h3 style="margin-top:1.5rem;">📧 Email report</h3>', unsafe_allow_html=True)
        with st.container(border=True):
            st.caption("Sends today's sales, ingredient usage, and order list to the report email address "
                       "set in this app's Secrets (REPORT_EMAIL_TO, RESEND_API_KEY).")
            if st.button("📧 Send report now", key="send_report_now_btn"):
                try:
                    to_addr = st.secrets["REPORT_EMAIL_TO"]
                    resend_api_key = st.secrets["RESEND_API_KEY"]
                    subject, text_body, html_body = daily_report.build_report(LOCATION_ID, selected_location_name)
                    daily_report.send_email(subject, text_body, html_body, to_addr, resend_api_key)
                    db.log_activity(LOCATION_ID, "Sent email report", f"to {to_addr}", snapshot=False)
                    st.success(f"Report sent to {to_addr}!")
                except KeyError:
                    st.error("Email isn't set up yet. Add REPORT_EMAIL_TO and RESEND_API_KEY "
                             "in this app's Secrets (Settings → Secrets in Streamlit Cloud).")
                except Exception as e:
                    st.error(f"Couldn't send the email: {e}")

# =============================================================================
# PAGE 4 — HISTORY: charts of usage and sales over time
# =============================================================================
elif page == "4. History":
    st.subheader("History")
    days = st.slider("Show last N days", min_value=7, max_value=180, value=30)

    usage_rows = db.get_usage_history(LOCATION_ID, days)
    sales_rows = db.get_sales_history(LOCATION_ID, days)

    if not usage_rows and not sales_rows:
        st.info("No sales recorded yet — enter some on the Daily Entry page first.")
    else:
        st.write("**Ingredient usage over time**")
        if usage_rows:
            usage_df = pd.DataFrame(usage_rows)
            all_ingredients = sorted(usage_df["ingredient"].unique())
            picked = st.multiselect("Ingredients to show", all_ingredients, default=all_ingredients[:5])
            if picked:
                filtered = usage_df[usage_df["ingredient"].isin(picked)]
                pivot = filtered.pivot_table(index="date", columns="ingredient", values="qty_used", fill_value=0)
                st.line_chart(pivot)
            else:
                st.caption("Pick at least one ingredient above to see its usage trend.")
        else:
            st.caption("No ingredient usage recorded in this period.")

        st.write("**Dish sales over time**")
        if sales_rows:
            sales_df = pd.DataFrame(sales_rows)
            all_dishes = sorted(sales_df["dish"].unique())
            picked_dishes = st.multiselect("Dishes to show", all_dishes, default=all_dishes[:5])
            if picked_dishes:
                filtered = sales_df[sales_df["dish"].isin(picked_dishes)]
                pivot = filtered.pivot_table(index="date", columns="dish", values="qty_sold", fill_value=0)
                st.bar_chart(pivot)
            else:
                st.caption("Pick at least one dish above to see its sales trend.")
        else:
            st.caption("No dish sales recorded in this period.")

# =============================================================================
# PAGE 5 — ACTIVITY LOG: every change made in the app, most recent first
# =============================================================================
elif page == "5. Activity Log":
    st.markdown('<h2 style="margin-bottom:0.2rem;">Activity log</h2>', unsafe_allow_html=True)
    st.caption(f"Every change made for {selected_location_name} — ingredients, recipes, sales, deliveries, "
               f"CSV uploads/downloads, and email reports.")

    tab_log, tab_versions = st.tabs(["Log", "Download past versions"])

    with tab_versions:
        st.caption("Every change saves a version of your ingredient and recipe lists. "
                   "Pick any point in time below to download exactly how the list looked then.")

        vtype = st.radio("Which list?", ["ingredients", "recipes"], horizontal=True, key="version_type")
        snapshots = db.list_snapshots(LOCATION_ID, vtype, limit=100)

        if not snapshots:
            st.info("No saved versions yet — they start being recorded from your next change onward.")
        else:
            def _version_label(idx: int, snap: dict) -> str:
                when = snap["created_at"].strftime("%Y-%m-%d %H:%M")
                if idx == 0:
                    position = "Current"
                elif idx == 1:
                    position = "Previous"
                else:
                    position = f"{idx} changes ago"
                return f"{position} — {when} — {snap['reason'] or 'change'}"

            options = {_version_label(i, s): s["id"] for i, s in enumerate(snapshots)}
            picked_label = st.selectbox("Version", list(options.keys()), key="version_pick")
            picked_id = options[picked_label]
            content = db.get_snapshot_content(picked_id)

            if content:
                try:
                    preview_df = pd.read_csv(io.StringIO(content))
                    st.caption(f"{len(preview_df)} row(s) in this version")
                    st.dataframe(preview_df, use_container_width=True, height=300)
                except Exception:
                    st.text(content[:2000])

                picked_snap = next(s for s in snapshots if s["id"] == picked_id)
                stamp = picked_snap["created_at"].strftime("%Y%m%d_%H%M")
                st.download_button(
                    f"⬇️ Download this {vtype} version",
                    content,
                    file_name=f"{vtype}_{stamp}.csv",
                    key="download_version_btn",
                )
                st.caption("This file uses the same format as the importer — you can re-upload it "
                           "on the Setup page to roll back to this version.")

    with tab_log:
        limit = st.slider("Show last N entries", min_value=25, max_value=500, value=100, step=25)
        log_entries = db.get_activity_log(LOCATION_ID, limit=limit)

        if not log_entries:
            st.info("No activity recorded yet — actions you take around the app will show up here.")
        else:
            action_types = sorted({e["action"] for e in log_entries})
            picked_actions = st.multiselect("Filter by action type", action_types, default=[])
            filtered_entries = [e for e in log_entries if not picked_actions or e["action"] in picked_actions]

            st.caption(f"Showing {len(filtered_entries)} of {len(log_entries)} entries")

            for entry in filtered_entries:
                with st.container(border=True):
                    c1, c2 = st.columns([1, 3])
                    with c1:
                        st.markdown(
                            f'<span class="kt-mono" style="font-size:0.8rem; color:var(--ink-soft);">'
                            f'{entry["created_at"].strftime("%Y-%m-%d %H:%M")}</span>',
                            unsafe_allow_html=True,
                        )
                    with c2:
                        st.markdown(f"**{entry['action']}**", unsafe_allow_html=True)
                        if entry["details"]:
                            st.caption(entry["details"])

            log_df = pd.DataFrame(filtered_entries)
            if not log_df.empty:
                st.download_button(
                    "⬇️ Export activity log as CSV", log_df.to_csv(index=False),
                    file_name="activity_log_export.csv",
                )
