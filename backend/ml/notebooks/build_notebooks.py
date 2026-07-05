"""Generate the three Phase-02 notebooks from source cell lists (reproducible).

Run from backend/:  python -m ml.notebooks.build_notebooks
Then execute + clear outputs before committing (see the plan's verification steps).

01_eda        -> genuine four-dataset raw exploration (self-contained code).
02_cleaning   -> narrates the ml.ingest pooling + spec-enrichment pipeline + viz.
03_modeling   -> narrates ml.train / ml.predict on the pooled data (Gate evidence).

The notebooks live in subfolders; each first cell walks up to put `backend/` on
sys.path so `ml`/`app` import regardless of the working directory.
"""
from pathlib import Path

import nbformat as nbf

HERE = Path(__file__).resolve().parent
SUBDIR = {"01_eda": "01_data_exploration",
          "02_cleaning": "02_data_preprocessing",
          "03_modeling": "03_data_modelling"}

PATH_SHIM = (
    "import sys, pathlib\n"
    "for _c in [pathlib.Path.cwd(), *pathlib.Path.cwd().parents]:\n"
    "    if (_c / 'app').exists() and (_c / 'ml').exists():\n"
    "        sys.path.insert(0, str(_c)); break\n"
)


def _nb(cells):
    nb = nbf.v4.new_notebook()
    nb.cells = [
        nbf.v4.new_markdown_cell(src) if kind == "md" else nbf.v4.new_code_cell(src)
        for kind, src in cells
    ]
    nb.metadata["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
    return nb


# --------------------------------------------------------------------------- #
# 01 · EDA — four datasets, filtered to Mercedes                              #
# --------------------------------------------------------------------------- #
EDA = [
    ("md", "# 01 · EDA — four datasets (Mercedes-only)\n\n"
           "Goal: filter `merc.csv` (UK/GBP), `germany_dataset.csv` (EUR), "
           "`vehicles_craigslist.csv` (US/USD) and `cars-spec-dataset.csv` (spec enrichment) "
           "to Mercedes-Benz, profile each, and document the preprocessing each needs before "
           "they are pooled into one RM training set. **None of these are Malaysian prices** — "
           "they are foreign price levels FX-converted to RM, tagged with `source_market`."),
    ("code", PATH_SHIM +
             "import pandas as pd, numpy as np, matplotlib.pyplot as plt, seaborn as sns\n"
             "from ml import ingest\n"
             "sns.set_theme(); pd.set_option('display.max_columns', 60)"),

    ("md", "## merc.csv — UK (GBP)\nAlready all Mercedes; clean, no nulls; `model` has leading "
           "spaces + numeric-only classes (180/200/220/230); mileage is in **miles**."),
    ("code", "merc = pd.read_csv(ingest.MERC_CSV); merc['model'] = merc['model'].str.strip()\n"
             "print(merc.shape); display(merc.head())\n"
             "print(merc.isna().sum().to_dict())\n"
             "display(merc[['transmission','fuelType']].melt().groupby(['variable','value']).size())"),
    ("code", "fig, ax = plt.subplots(1,2, figsize=(11,4))\n"
             "merc['price'].plot.hist(bins=50, ax=ax[0], title='merc price (GBP)')\n"
             "merc['mileage'].plot.hist(bins=50, ax=ax[1], title='merc mileage (miles)'); plt.tight_layout()"),

    ("md", "## germany_dataset.csv — Germany (EUR)\nMulti-brand -> filter `brand`. Specific model "
           "names ('Mercedes-Benz E 220') carry a displacement-hinting badge; `fuel_type` has "
           "**leaked garbage** (dates/mileage strings); no engine-size column; mileage already km."),
    ("code", "ger = pd.read_csv(ingest.GERMANY_CSV)\n"
             "mger = ger[ger['brand'].str.lower().str.contains('mercedes', na=False)]\n"
             "print('mercedes rows:', mger.shape)\n"
             "display(mger[['model','year','price_in_euro','transmission_type','fuel_type','mileage_in_km']].head())\n"
             "print('fuel_type (dirty):', mger['fuel_type'].value_counts().head(8).to_dict())"),

    ("md", "## vehicles_craigslist.csv — US (USD)\nMulti-brand -> filter `manufacturer`. Free-text "
           "lowercase model ('e320 cdi', 'ml350', 'benz'); price has 0 -> 3-billion outliers; "
           "odometer in **miles**; many nulls; no engine-size column."),
    ("code", "cl = pd.read_csv(ingest.CRAIGSLIST_CSV, low_memory=False)\n"
             "mcl = cl[cl['manufacturer'].str.lower().str.contains('mercedes', na=False)]\n"
             "print('mercedes rows:', mcl.shape)\n"
             "display(mcl[['model','year','price','odometer','transmission','fuel']].head())\n"
             "print('price describe:', mcl['price'].describe()[['min','50%','max']].to_dict())"),

    ("md", "## cars-spec-dataset.csv — spec enrichment source\nFilter `Company`. ~2.4k Mercedes "
           "variants keyed by `Serie` (German) + `Production years`. Strong coverage of the specs "
           "we enrich with (parsing handled in `ml.ingest.clean_spec`)."),
    ("code", "specs = ingest.clean_spec()\n"
             "print('parsed Mercedes spec variants:', specs.shape)\n"
             "cover = {c: f'{specs[c].notna().mean()*100:.0f}%' for c in ingest.ENRICH_NUM + ingest.ENRICH_CAT}\n"
             "print('enriched-field coverage:', cover)\n"
             "display(specs.head())"),

    ("md", "## Class-mapping feasibility (enrichment ceiling)\n`ingest.canon_class` maps each "
           "source's model string to a canonical class. A row can only be spec-enriched if its "
           "class exists in the spec table."),
    ("code", "sc = set(specs['model_class'])\n"
             "def cov(name, s):\n"
             "    c = s.map(ingest.canon_class)\n"
             "    print(f'{name:11s} parsed a class: {c.notna().mean()*100:5.1f}% | '\n"
             "          f'class in spec: {c.isin(sc).mean()*100:5.1f}%')\n"
             "cov('merc', merc['model']); cov('germany', mger['model']); cov('craigslist', mcl['model'])"),

    ("md", "## Preprocessing contract (per dataset)\n"
           "- **merc (uk):** strip model -> `canon_class`; miles->km; GBP->RM (`fx_gbp_to_rm`); "
           "real `engineSize` kept; `source_market='uk'`. Drop numeric-only classes (unmapped).\n"
           "- **germany:** filter brand; `canon_class`; km as-is; EUR->RM (`fx_eur_to_rm`); "
           "normalise dirty `fuel_type`/`transmission`; badge -> engine hint; enrich engine_size.\n"
           "- **craigslist (us):** filter manufacturer; `canon_class`; miles->km; USD->RM "
           "(`fx_usd_to_rm`); drop price/odometer outliers; enrich engine_size.\n"
           "- **cars-spec:** filter Company; parse displacement/torque/top-speed/accel/boot/gears/"
           "aspiration/brakes; build class x year lookup.\n\n"
           "Shared pool filters: `1990 <= year <= 2026`, `price_rm in [3k, 2M]`, `mileage <= 500k km`, "
           "drop dupes. Then `battery_soh` / `trans_adapt_offset` are engineered (unchanged). "
           "All of this is implemented + tested in `ml.ingest`; `02_cleaning.ipynb` runs it.\n\n"
           "> **Training-pool decision:** craigslist (US) is *explored here but excluded from the "
           "training pool* — its listings are the noisiest (validation MAPE ~49% vs UK 10% / "
           "germany 24%). `ml.ingest.build_pool` trains on UK + germany only."),
]

# --------------------------------------------------------------------------- #
# 02 · Cleaning + enrichment + simulated OBD-II features                      #
# --------------------------------------------------------------------------- #
CLEANING = [
    ("md", "# 02 · Cleaning + spec enrichment + simulated OBD-II features\n\n"
           "Runs the pooling + enrichment contract from `ml.ingest` and the engineered features "
           "from `ml.features` (both tested). Order: clean cars-spec -> harmonise the three price "
           "datasets -> pool -> enrich -> engineer -> write `data/interim/merc_engineered.csv`."),
    ("code", PATH_SHIM +
             "import pandas as pd, numpy as np, matplotlib.pyplot as plt, seaborn as sns\n"
             "from ml import ingest\nsns.set_theme()"),

    ("md", "### Step 1 — cars-spec lookup (cleaned first)"),
    ("code", "specs = ingest.clean_spec(); print('spec variants:', specs.shape); specs.head()"),

    ("md", "### Step 2 — harmonise + pool the three price datasets\nEach source -> common schema, "
           "FX->RM, `source_market`. `clean_pool` drops nulls/outliers/dupes and adds `age`."),
    ("code", "pool = ingest.build_pool()\n"
             "print('pooled rows:', len(pool), '| by market:', pool['source_market'].value_counts().to_dict())\n"
             "pool.head()"),

    ("md", "### Step 3 — enrich every row with specs (class x year x nearest displacement)\n"
           "`engine_size` is backfilled from the matched spec; `match_level` records join quality."),
    ("code", "enr = ingest.enrich(pool, specs)\n"
             "print('match-level:', enr['match_level'].value_counts().to_dict())\n"
             "print('engine_size null after backfill:', int(enr['engine_size'].isna().sum()))\n"
             "enr[['model_class','variant','source_market','age','mileage','engine_size',"
             "'torque_nm','top_speed_kmh','price_rm']].head()"),

    ("md", "### Step 4 — engineer the simulated OBD-II features + write the CSV"),
    ("code", "df = ingest.build_engineered_csv()   # pool + enrich + engineer + write\n"
             "print('final:', df.shape); df.head()"),

    ("md", "### `battery_soh` — deterministic base curves (from `ml.features`)\n"
           "Time-dominant for petrol/diesel; non-linear in mileage for hybrids (mileage now in km)."),
    ("code", "from ml.features import battery_soh_base, SOH_FLOOR\n"
             "ages = np.arange(0, 21)\n"
             "for ft in ['Petrol','Diesel','Hybrid']:\n"
             "    plt.plot(ages, [battery_soh_base(ft, a, 100_000) for a in ages], marker='.', label=ft)\n"
             "plt.axhline(SOH_FLOOR, color='gray', ls='--'); plt.legend()\n"
             "plt.xlabel('age'); plt.ylabel('battery_soh_base (%)'); plt.title('@100,000 km'); plt.show()"),
    ("code", "fig, ax = plt.subplots(1,2, figsize=(11,4))\n"
             "df['battery_soh'].plot.hist(bins=40, ax=ax[0], title='battery_soh (%)')\n"
             "sns.scatterplot(data=df.sample(min(3000,len(df)), random_state=0), x='mileage', y='battery_soh',\n"
             "                hue='fuel_type', s=8, ax=ax[1]); ax[1].set_title('SoH vs mileage'); plt.tight_layout()"),

    ("md", "### `trans_adapt_offset` — Manual is exactly 0; automatics strictly negative, scale with mileage"),
    ("code", "print(df.groupby('transmission')['trans_adapt_offset'].agg(['mean','min','max']))\n"
             "auto = df[df['transmission'] != 'Manual'].sample(min(3000,len(df)), random_state=0)\n"
             "sns.scatterplot(data=auto, x='mileage', y='trans_adapt_offset', s=8)\n"
             "plt.title('offset vs mileage (non-manual)'); plt.show()"),

    ("md", "### Enrichment quality by source\nUK rows are displacement-refined (real engine size); "
           "germany/US use badge hint -> nearest real variant, else class-year representative."),
    ("code", "display(df.groupby(['source_market','match_level']).size().unstack(fill_value=0))\n"
             "print('price_rm by market (median):', df.groupby('source_market')['price_rm'].median().to_dict())"),
    ("md", "Engineered dataset written to `data/interim/merc_engineered.csv` — the pooled model trains on this."),
]

# --------------------------------------------------------------------------- #
# 03 · Modeling — RF vs LR, interval, depreciation                            #
# --------------------------------------------------------------------------- #
MODELING = [
    ("md", "# 03 · Modeling — RF vs LR, interval, depreciation\n\n"
           "Builds the pipeline, runs `GroupKFold(groups=model_class)`, and produces the Gate "
           "evidence on the **pooled** dataset. Logic lives in `ml.train` / `ml.predict`."),
    ("code", PATH_SHIM +
             "import pandas as pd, numpy as np, matplotlib.pyplot as plt, seaborn as sns\n"
             "from ml import ingest, train, metrics\nfrom ml.predict import Predictor\nsns.set_theme()\n"
             "df = ingest.build_engineered_csv(); df.shape"),
    ("code", "print('FEATURES:', train.FEATURES)\nprint('GROUP:', train.GROUP, '| TARGET:', train.TARGET)"),
    ("code", "for i, (tr, va) in enumerate(train.iter_group_folds(df, n_splits=5)):\n"
             "    vc = set(df.iloc[va]['model_class'])\n"
             "    print(f'fold {i}: train={len(tr)} val={len(va)} val_classes={sorted(vc)}')"),

    ("md", "### RF vs Ridge baseline (aggregate over GroupKFold folds)\n"
           "`GroupKFold(groups=model_class)` is the **primary, pessimistic cold-start** view: "
           "whole classes are held out, so this scores extrapolation to *unseen* classes. The "
           "linear baseline is **Ridge** (plain LinearRegression is numerically unstable here)."),
    ("code", "meta = train.main(df=df)  # writes artifacts + returns metrics\n"
             "rf = meta['models']['random_forest']['aggregate']; rg = meta['models']['ridge']['aggregate']\n"
             "pd.DataFrame({'RandomForest': {k: v['mean'] for k,v in rf.items()},\n"
             "              'Ridge': {k: v['mean'] for k,v in rg.items()}})"),
    ("code", "print('interval:', meta['interval'])\nprint('rows by market:', meta['source_markets'])"),

    ("md", "### Feature importances — is the model using the engineered + enriched signals?"),
    ("code", "import joblib\n"
             "pipe = joblib.load(train.ARTIFACTS_DIR / 'model.joblib')\n"
             "prep, rf2 = pipe.named_steps['prep'], pipe.named_steps['model']\n"
             "imp = pd.Series(rf2.feature_importances_, index=prep.get_feature_names_out()).sort_values(ascending=False)\n"
             "imp.head(20).plot.barh(figsize=(6,6)); plt.gca().invert_yaxis()\n"
             "plt.title('RF feature importances (top 20)'); plt.tight_layout(); imp.head(20)"),

    ("md", "### Sanity prediction + per-tree interval\nProfile market defaults to `uk` "
           "(prediction reads as UK-price-level in RM unless a market is supplied)."),
    ("code", "pred = Predictor()\n"
             "profile = {'model_class':'C Class','year':2018,'age':8,'mileage':90000,\n"
             "           'transmission':'Automatic','fuel_type':'Petrol','engine_size':2.0,'source_market':'uk'}\n"
             "print(pred.predict(profile))\n"
             "trees = pred._per_tree(pred._row(profile))\n"
             "plt.hist(trees, bins=30)\n"
             "for pct,c in [(train.INTERVAL_LOW_PCT,'red'),(50,'black'),(train.INTERVAL_HIGH_PCT,'red')]:\n"
             "    plt.axvline(np.percentile(trees, pct), color=c, ls='--')\n"
             "plt.title('per-tree predictions'); plt.xlabel('price_rm'); plt.show()"),

    ("md", "### Depreciation curve"),
    ("code", "curve = pd.DataFrame(pred.depreciation(profile, years=6))\n"
             "sns.lineplot(data=curve, x='year', y='retained_pct', marker='o'); plt.title('retained value'); curve"),

    ("md", "**Gate:** review the RF-vs-LR table, the empirical interval coverage, feature "
           "importances, and these sanity predictions before Phase 03 wires the artifact into the "
           "dashboard. Remember the honest caveat: prices are pooled foreign levels in RM, not "
           "Malaysian market prices."),
]

if __name__ == "__main__":
    for name, cells in [("01_eda", EDA), ("02_cleaning", CLEANING), ("03_modeling", MODELING)]:
        dst = HERE / SUBDIR[name] / f"{name}.ipynb"
        dst.parent.mkdir(parents=True, exist_ok=True)
        nbf.write(_nb(cells), dst)
        print("wrote", dst.relative_to(HERE))
