"""Generate the three Phase-02 notebooks from source cell lists (reproducible).

Run from backend/:  python -m ml.notebooks.build_notebooks
Then execute + clear outputs via the commands in the plan (Task 7).
"""
from pathlib import Path

import nbformat as nbf

HERE = Path(__file__).resolve().parent


def _nb(cells):
    nb = nbf.v4.new_notebook()
    nb.cells = [
        nbf.v4.new_markdown_cell(src) if kind == "md" else nbf.v4.new_code_cell(src)
        for kind, src in cells
    ]
    nb.metadata["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
    return nb


EDA = [
    ("md", "# 01 · EDA — raw `merc.csv`\n\nDistributions, nulls, cardinality, correlations. "
           "Informs the cleaning contract and feature list."),
    ("code", "import sys; sys.path.insert(0, '..' if __import__('pathlib').Path('..').joinpath('app').exists() else '../..')\n"
             "import pandas as pd, matplotlib.pyplot as plt, seaborn as sns\n"
             "from ml import ingest\n"
             "sns.set_theme()\n"
             "raw = ingest.load_raw(); raw.columns = raw.columns.str.strip(); raw.head()"),
    ("code", "raw.info(); raw.describe(include='all').T"),
    ("code", "raw.isna().sum()"),
    ("code", "for c in ['transmission','fuelType']:\n    display(raw[c].value_counts())"),
    ("code", "fig, ax = plt.subplots(1,2, figsize=(11,4))\n"
             "raw['price'].plot.hist(bins=50, ax=ax[0], title='price (GBP)')\n"
             "raw['mileage'].plot.hist(bins=50, ax=ax[1], title='mileage'); plt.tight_layout()"),
    ("code", "num = raw[['year','price','mileage','tax','mpg','engineSize']]\n"
             "sns.heatmap(num.corr(), annot=True, fmt='.2f', cmap='mako'); plt.title('correlations')"),
    ("md", "**Takeaways:** heavy right-skew in price/mileage; a few implausible `year` values "
           "(handled by the cleaning outlier filter); `transmission`/`fuelType` dominated by a few "
           "classes with rare `Other`. These drive the cleaning + feature-engineering choices."),
]

CLEANING = [
    ("md", "# 02 · Cleaning + simulated OBD-II features\n\nApplies the cleaning contract and "
           "synthesises `battery_soh` and `trans_adapt_offset` (see spec). Logic lives in "
           "`ml.ingest` / `ml.features` — this notebook narrates and visualises it."),
    ("code", "import sys; sys.path.insert(0, '..' if __import__('pathlib').Path('..').joinpath('app').exists() else '../..')\n"
             "import pandas as pd, matplotlib.pyplot as plt, seaborn as sns\n"
             "from ml import ingest\nsns.set_theme()\n"
             "raw = ingest.load_raw(); df = ingest.build_engineered_csv()\n"
             "print('raw:', raw.shape, '-> engineered:', df.shape); df.head()"),
    ("md", "### `battery_soh` — Starter Battery State of Health\n"
           "Time-dominant for petrol/diesel; non-linear in mileage for hybrids."),
    ("code", "fig, ax = plt.subplots(1,2, figsize=(11,4))\n"
             "df['battery_soh'].plot.hist(bins=40, ax=ax[0], title='battery_soh (%)')\n"
             "sns.scatterplot(data=df.sample(min(2000,len(df)), random_state=0), x='mileage', y='battery_soh',\n"
             "                hue='fuel_type', s=10, ax=ax[1]); ax[1].set_title('SoH vs mileage'); plt.tight_layout()"),
    ("md", "### `trans_adapt_offset` — Transmission Adaptation Offset\n"
           "Manual is exactly 0 (own branch); automatics are strictly negative and scale with mileage."),
    ("code", "print(df.groupby('transmission')['trans_adapt_offset'].describe()[['mean','min','max']])\n"
             "auto = df[df['transmission'] != 'Manual'].sample(min(2000,len(df)), random_state=0)\n"
             "sns.scatterplot(data=auto, x='mileage', y='trans_adapt_offset', s=10)\n"
             "plt.title('offset vs mileage (non-manual)')"),
    ("md", "Engineered dataset written to `data/merc_engineered.csv` — this is what the model trains on."),
]

MODELING = [
    ("md", "# 03 · Modeling — RF vs LR, interval, depreciation\n\nBuilds the pipeline, runs "
           "`GroupKFold(groups=model)`, and produces the Gate-2 evidence. Logic lives in "
           "`ml.train` / `ml.predict`."),
    ("code", "import sys; sys.path.insert(0, '..' if __import__('pathlib').Path('..').joinpath('app').exists() else '../..')\n"
             "import pandas as pd, matplotlib.pyplot as plt, seaborn as sns\n"
             "from ml import ingest, train\nfrom ml.predict import Predictor\nsns.set_theme()\n"
             "df = ingest.build_engineered_csv(); df.shape"),
    ("code", "meta = train.main(df=df)  # writes artifacts + returns the metrics dict\n"
             "rf = meta['models']['random_forest']['aggregate']; lr = meta['models']['linear_regression']['aggregate']\n"
             "pd.DataFrame({'RandomForest': {k: v['mean'] for k,v in rf.items()},\n"
             "              'LinearRegression': {k: v['mean'] for k,v in lr.items()}})"),
    ("code", "print('interval:', meta['interval'])"),
    ("md", "### Sanity predictions"),
    ("code", "pred = Predictor()\n"
             "profile = {'model':'C Class','year':2018,'age':8,'mileage':60000,'transmission':'Automatic',\n"
             "           'fuel_type':'Petrol','engine_size':2.0,'mpg':45.0,'tax':150.0}\n"
             "print(pred.predict(profile))"),
    ("md", "### Depreciation curve"),
    ("code", "pts = pred.depreciation(profile, years=6)\n"
             "curve = pd.DataFrame(pts)\n"
             "sns.lineplot(data=curve, x='year', y='retained_pct', marker='o'); plt.title('retained value'); curve"),
    ("md", "**Gate 2:** review the RF-vs-LR table, the empirical interval coverage, and these "
           "sanity predictions before Phase 03 wires the artifact into the dashboard."),
]

if __name__ == "__main__":
    for name, cells in [("01_eda", EDA), ("02_cleaning", CLEANING), ("03_modeling", MODELING)]:
        nbf.write(_nb(cells), HERE / f"{name}.ipynb")
        print("wrote", name)
