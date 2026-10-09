"""Shared setup for the defensive dives article.

Level definitions, chart styling, cached BigQuery pulls, and the
aggregations behind every table and chart in `defensive_dives.qmd`.
The logic mirrors `notebooks/defensive_notebook.ipynb`; the fielding and
framing data share one schema here so both halves reuse the same functions:

    player_code, player_name, year, level, level_num, level_label,
    opportunities, total_sfg_frv, sfg_frv_per_100, percentile,
    first_game, last_game  (+ position for fielding)

`percentile` ranks a row against same-year, same-level peers (and same
position, for fielding).
"""
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

PROJECT_ID = "sfgiants-viewer"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
QUERY_DIR = PROJECT_ROOT / "queries"
CACHE_DIR = Path(__file__).resolve().parent / "data"

# Source-defined levels, in developmental order (matches sport_code). ROK DSL
# and Complex League are kept separate: distinct competitive/tracking
# environments, not the same step.
LEVEL_ORDER = ["rok_dsl", "rok_oth", "afx", "afa", "aax", "aaa", "mlb"]
LEVEL_NUM = {lvl: i + 1 for i, lvl in enumerate(LEVEL_ORDER)}
LEVEL_LABELS = {
    "rok_dsl": "ROK DSL", "rok_oth": "Complex League", "afx": "Low-A",
    "afa": "High-A", "aax": "Double-A", "aaa": "Triple-A", "mlb": "MLB",
}
LEVEL_LABEL_ORDER = [LEVEL_LABELS[l] for l in LEVEL_ORDER]
POSITION_LABELS = {
    "catcher": "C", "first_baseman": "1B", "second_baseman": "2B",
    "third_baseman": "3B", "shortstop": "SS", "left_fielder": "LF",
    "center_fielder": "CF", "right_fielder": "RF",
}
# Traditional defensive spectrum, hardest to easiest.
SPECTRUM_ORDER = ["shortstop", "center_fielder", "second_baseman", "third_baseman",
                  "right_fielder", "left_fielder", "first_baseman"]
SPECTRUM_RANK = {pos: len(SPECTRUM_ORDER) - i for i, pos in enumerate(SPECTRUM_ORDER)}  # higher = harder
POSITION_LABEL_ORDER = [POSITION_LABELS[p] for p in SPECTRUM_ORDER]

FIELDING_MIN_OPPORTUNITIES = 100  # defensive opportunities per player-season-level-position
FRAMING_MIN_OPPORTUNITIES = 500   # called pitches per catcher-season-level
MINOR_HISTORY_DEBUT_CUTOFF = 2022  # PBP starts in 2021; earlier debuts have censored histories

# Orange ramp for charts where levels sit in ladder order with their names on
# the axis (spread by level, carry-over bars): dark (rookie ball) -> bright (MLB).
LEVEL_RAMP = {
    "ROK DSL": "#7a2704", "Complex League": "#a63603", "Low-A": "#d94801",
    "High-A": "#f16913", "Double-A": "#fd8d3c", "Triple-A": "#fdae6b", "MLB": "#fd5a1e",
}

# Distinct color per level for the paths-to-MLB charts, where any two levels can
# sit next to each other (categorical palette slots 1-7 in fixed order, which
# keeps them apart for color-blind readers too); each level also gets its own
# marker shape there.
LEVEL_COLORS = {
    "ROK DSL": "#2a78d6", "Complex League": "#eb6834", "Low-A": "#1baf7a",
    "High-A": "#eda100", "Double-A": "#e87ba4", "Triple-A": "#008300", "MLB": "#4a3aa7",
}
LEVEL_MARKERS = {
    "ROK DSL": "o", "Complex League": "s", "Low-A": "^", "High-A": "D",
    "Double-A": "v", "Triple-A": "P", "MLB": "*",
}
GROUP_COLORS = ["#a63603", "#d94801", "#fd8d3c", "#fdae6b", "#fd5a1e"]
AGE_COLORS = ["#c6dbef", "#9ecae1", "#6baed6", "#4292c6", "#2171b5", "#08519c", "#08306b"]
# Every chart is drawn at this width so text is the same size on the page.
FIG_W = 9
INK = "#111111"
MUTED = "#737b87"
GRID = "#e3e5e8"
ACCENT = "#fd5a1e"
REFERENCE = "#a6acb4"


# ---------------------------------------------------------------- styling

def apply_style():
    plt.rcParams.update({
        "font.family": ["Segoe UI", "DejaVu Sans"],
        "axes.edgecolor": GRID,
        "axes.labelcolor": "#242424",
        "axes.titlecolor": INK,
        "text.color": INK,
        "xtick.color": "#59616c",
        "ytick.color": "#59616c",
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "axes.axisbelow": True,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "figure.dpi": 110,
    })


def style_ax(ax, title=None, subtitle=None, xlabel=None, ylabel=None):
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.grid(axis="x", visible=False)
    if title:
        ax.set_title(title, fontsize=12, fontweight="bold", loc="left", pad=(18 if subtitle else 8))
    if subtitle:
        ax.text(0, 1.02, subtitle, transform=ax.transAxes, fontsize=8.5,
                color=MUTED, ha="left", va="bottom")
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=10, fontweight="bold")
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=10, fontweight="bold")


def styled_boxplot(ax, data, labels, colors, alpha=0.85):
    bp = ax.boxplot(
        data, tick_labels=labels, patch_artist=True, widths=0.55,
        medianprops=dict(color=INK, linewidth=1.6),
        whiskerprops=dict(color="#59616c", linewidth=1),
        capprops=dict(color="#59616c", linewidth=1),
        flierprops=dict(marker="o", markersize=2.5, markerfacecolor=REFERENCE,
                        markeredgecolor="none", alpha=0.35),
    )
    for patch, median, color in zip(bp["boxes"], bp["medians"], colors):
        patch.set_facecolor(color)
        patch.set_edgecolor(INK)
        patch.set_linewidth(0.8)
        patch.set_alpha(alpha)
        if _is_dark(color):
            median.set_color("white")
    return bp


def _is_dark(hex_color):
    r, g, b = (int(hex_color.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b < 0.35


def transition_labels(models):
    return [f"{f}\n→ {t}" for f, t in zip(models["from"], models["to"])]


def pct(x, digits=0):
    return f"{x:.{digits}%}"


def num(x, digits=2):
    return f"{x:,.{digits}f}"


# ------------------------------------------------------------ data access

def cached_query(name, sql, refresh=False):
    """Run `sql` in BigQuery once and reuse the parquet snapshot afterwards.

    Pass refresh=True (`quarto render ... -P refresh:true`) to re-pull.
    """
    path = CACHE_DIR / f"{name}.parquet"
    if path.exists() and not refresh:
        return pd.read_parquet(path)
    from google.cloud import bigquery

    df = bigquery.Client(project=PROJECT_ID).query(sql).to_dataframe()
    for col in df.columns:
        if str(df[col].dtype) in ("dbdate", "dbtime"):
            df[col] = pd.to_datetime(df[col].astype(str))
    CACHE_DIR.mkdir(exist_ok=True)
    df.to_parquet(path, index=False)
    return df


def snapshot_date(name):
    """Date the cached parquet for `name` was pulled."""
    path = CACHE_DIR / f"{name}.parquet"
    return pd.Timestamp(path.stat().st_mtime, unit="s").date()


def load_fielding_plays(refresh=False):
    """One row per modeled fielding play; sfg_rv > 0 favors the fielder."""
    sql = (QUERY_DIR / "play_by_play.sql").read_text(encoding="utf-8")
    df = cached_query("fielding_plays", sql, refresh)
    dfc = df.rename(columns={"sport_code": "level"}).copy()
    dfc["sfg_rv"] = -dfc["runs_plus_minus"]
    dfc = dfc.dropna(subset=["sfg_rv", "game_pk", "player_code", "year", "level", "position"])
    dfc["game_date"] = pd.to_datetime(dfc["game_date"])
    return dfc


def load_birth_dates(refresh=False):
    sql = """
    SELECT player_code, birth_date
    FROM `sfgiants-viewer.scout_replica_scouting.tblPlayer_Pro`
    WHERE birth_date IS NOT NULL
    """
    births = cached_query("birth_dates", sql, refresh)
    births["birth_date"] = pd.to_datetime(births["birth_date"])
    if births["birth_date"].dt.tz is not None:
        births["birth_date"] = births["birth_date"].dt.tz_localize(None)
    return births


def load_framing_level_agg(refresh=False):
    """Catcher-season-level framing roll-up (aggregated in BigQuery)."""
    sql = (QUERY_DIR / "framing_level_agg.sql").read_text(encoding="utf-8")
    df = cached_query("framing_level_agg", sql, refresh)
    return df.rename(columns={"catcher_sfg_id": "player_code", "catcher_name": "player_name"})


# ------------------------------------------------------------ aggregation

def _add_rates(agg):
    agg["sfg_frv_per_100"] = 100 * agg["total_sfg_frv"] / agg["opportunities"]
    agg["level_num"] = agg["level"].map(LEVEL_NUM)
    agg["level_label"] = agg["level"].map(LEVEL_LABELS)
    return agg


def qualify_fielding(dfc):
    """Player-season-level-position rows; returns (all rows, qualified rows)."""
    agg = (
        dfc.groupby(["player_code", "player_name", "year", "level", "position"], as_index=False)
        .agg(
            opportunities=("sfg_rv", "size"),
            games=("game_pk", "nunique"),
            first_game=("game_date", "min"),
            last_game=("game_date", "max"),
            total_sfg_frv=("sfg_rv", "sum"),
        )
    )
    agg = _add_rates(agg)
    agg["position_label"] = agg["position"].map(POSITION_LABELS)
    qualified = agg[agg["opportunities"] >= FIELDING_MIN_OPPORTUNITIES].copy()
    qualified["percentile"] = (
        qualified.groupby(["year", "level", "position"])["sfg_frv_per_100"].rank(pct=True)
    )
    return agg, qualified


def qualify_framing(level_agg):
    """Catcher-season-level rows; returns (all rows, qualified rows)."""
    agg = level_agg.dropna(subset=["level", "player_code", "year"]).copy()
    agg["first_game"] = pd.to_datetime(agg["first_game"])
    agg["last_game"] = pd.to_datetime(agg["last_game"])
    agg = _add_rates(agg)
    qualified = agg[agg["opportunities"] >= FRAMING_MIN_OPPORTUNITIES].copy()
    qualified["percentile"] = qualified.groupby(["year", "level"])["sfg_frv_per_100"].rank(pct=True)
    return agg, qualified


def level_distribution(qualified):
    dist = (
        qualified.groupby(["level", "level_label", "level_num"])
        .agg(
            observations=("sfg_frv_per_100", "size"),
            players=("player_code", "nunique"),
            median_opportunities=("opportunities", "median"),
            p10=("sfg_frv_per_100", lambda s: s.quantile(0.10)),
            p50=("sfg_frv_per_100", "median"),
            p90=("sfg_frv_per_100", lambda s: s.quantile(0.90)),
        )
        .reset_index()
        .sort_values("level_num")
        .reset_index(drop=True)
    )
    dist["spread_80"] = dist["p90"] - dist["p10"]
    return dist


def clipped_by_level(qualified):
    """FRV/100 per level (ladder order), clipped to the central 98% for plotting."""
    p01, p99 = qualified["sfg_frv_per_100"].quantile([0.01, 0.99])
    return [qualified.loc[qualified["level"] == l, "sfg_frv_per_100"].clip(p01, p99)
            for l in LEVEL_ORDER]


def adjacent_transitions(qualified, group_cols, direction="up"):
    """Consecutive qualified stints one level apart, in the order they happened.

    Stints (season-level rows) are ordered by their first and last game dates,
    not by season and level, so a demotion within a season isn't mistaken for a
    promotion. direction="up" keeps moves to the next level up (promotions),
    "down" moves to the next level down (demotions); a stint's next stint is
    the one that started next.

    Also carries a within-year/level z-score of FRV/100 so slopes can be
    compared with the narrowing-spread effect removed.
    """
    q = qualified.copy()
    peer_cols = ["year", "level"] + (["position"] if "position" in group_cols else [])
    q["z_frv"] = q.groupby(peer_cols)["sfg_frv_per_100"].transform(lambda s: (s - s.mean()) / s.std())
    q = q.sort_values(group_cols + ["first_game", "last_game"])
    grp = q.groupby(group_cols)
    for col, new in [("year", "next_year"), ("level", "next_level"), ("level_num", "next_level_num"),
                     ("sfg_frv_per_100", "next_frv_per_100"), ("percentile", "next_percentile"),
                     ("z_frv", "next_z"), ("first_game", "next_first_game")]:
        q[new] = grp[col].shift(-1)
    step = 1 if direction == "up" else -1
    trans = q[
        (q["next_level_num"] == q["level_num"] + step)
        & q["percentile"].notna()
        & q["next_percentile"].notna()
    ].copy()
    trans["from"] = trans["level"].map(LEVEL_LABELS)
    trans["to"] = trans["next_level"].map(LEVEL_LABELS)
    return trans


def _fit(data, xcol, ycol, min_n):
    data = data.dropna(subset=[xcol, ycol])  # z-scores are NaN for single-row peer groups
    if len(data) < min_n or data[xcol].std() == 0:
        return pd.Series({"transitions": len(data), "intercept": np.nan, "slope": np.nan, "r_squared": np.nan})
    x, y = data[xcol].to_numpy(), data[ycol].to_numpy()
    slope, intercept = np.polyfit(x, y, 1)
    r = np.corrcoef(x, y)[0, 1]
    return pd.Series({"transitions": len(data), "intercept": intercept, "slope": slope, "r_squared": r ** 2})


def transition_models(trans, min_n):
    """Per adjacent step: raw FRV/100 fit and within-level z-score fit."""
    keys = ["from", "to", "level_num"]
    raw = trans.groupby(keys).apply(
        lambda d: _fit(d, "sfg_frv_per_100", "next_frv_per_100", min_n), include_groups=False)
    z = trans.groupby(keys).apply(lambda d: _fit(d, "z_frv", "next_z", min_n), include_groups=False)
    models = raw.join(z[["slope", "r_squared"]], rsuffix="_z").reset_index().sort_values("level_num")
    return models.rename(columns={"slope_z": "z_slope", "r_squared_z": "z_r_squared"}).reset_index(drop=True)


PERCENTILE_GROUPS = ["Bottom 20%", "20-40%", "40-60%", "60-80%", "Top 20%"]


def persistence_table(trans):
    groups = pd.cut(trans["percentile"], bins=[-0.01, 0.20, 0.40, 0.60, 0.80, 1.01],
                    labels=PERCENTILE_GROUPS)
    return trans.assign(starting_group=groups).groupby("starting_group", observed=True).agg(
        transitions=("next_percentile", "size"),
        average_next_percentile=("next_percentile", "mean"),
        finished_above_average=("next_percentile", lambda s: (s > 0.5).mean()),
        finished_in_top_20=("next_percentile", lambda s: (s > 0.8).mean()),
    ).reset_index()


def first_mlb_appearance(rows, date_col):
    mlb = rows[rows["level"] == "mlb"]
    return (
        mlb.groupby("player_code")
        .agg(first_mlb_game=(date_col, "min"), first_mlb_year=("year", "min"))
        .reset_index()
    )


def mlb_cohort(qualified, first_mlb, percentile_within=None):
    """Current-season MLB players with an eligible pre-debut minor history.

    Eligible = qualified at 2+ distinct minor levels, all before their first
    MLB game, and debuting after MINOR_HISTORY_DEBUT_CUTOFF.
    Returns (current_year, cohort, minor_rows).
    """
    current_year = int(qualified.loc[qualified["level"] == "mlb", "year"].max())
    current = (
        qualified[(qualified["year"] == current_year) & (qualified["level"] == "mlb")]
        .sort_values("opportunities", ascending=False)
        .drop_duplicates("player_code")
        .copy()
    )
    ranker = current.groupby(percentile_within) if percentile_within else current
    current["current_mlb_percentile"] = ranker["sfg_frv_per_100"].rank(pct=True)

    minors = qualified[qualified["level"] != "mlb"].merge(first_mlb, on="player_code", how="inner")
    minors = minors[
        (minors["first_mlb_year"] > MINOR_HISTORY_DEBUT_CUTOFF)
        & (minors["last_game"] < minors["first_mlb_game"])
    ]
    minors = minors[minors.groupby("player_code")["level"].transform("nunique") >= 2]
    minors = minors.sort_values(["player_code", "year", "level_num"])

    summary = minors.groupby("player_code").agg(
        first_mlb_game=("first_mlb_game", "first"),
        minor_levels=("level_label", lambda s: ", ".join(pd.unique(s))),
        total_minor_frv=("total_sfg_frv", "sum"),
        total_minor_opportunities=("opportunities", "sum"),
        average_minor_percentile=("percentile", "mean"),
    ).reset_index()
    summary["weighted_minor_frv_per_100"] = (
        100 * summary["total_minor_frv"] / summary["total_minor_opportunities"]
    )
    cohort = current.merge(summary, on="player_code", how="inner")
    return current_year, cohort, minors


def add_age(qualified, births):
    """Baseball age (as of July 1st of the season) plus age relative to peers."""
    out = qualified.merge(births, on="player_code", how="left")
    out["age"] = (pd.to_datetime(out["year"].astype(str) + "-07-01") - out["birth_date"]).dt.days / 365.25
    out = out.dropna(subset=["age"])
    out["age_bucket"] = pd.cut(out["age"], bins=[0, 19, 21, 23, 25, 27, 29, 100],
                               labels=["<=19", "20-21", "22-23", "24-25", "26-27", "28-29", "30+"])
    out["age_vs_peers"] = out["age"] - out.groupby(["year", "level", "position"])["age"].transform("median")
    out["age_peer_group"] = pd.cut(
        out["age_vs_peers"], bins=[-100, -1.0, 1.0, 100],
        labels=["Younger than peers (1+ yr)", "About the same age", "Older than peers (1+ yr)"],
    )
    return out


def age_profile(aged, min_rows=30, n_boot=300, seed=0):
    """Average FRV/100 at each age, all levels pooled (runs / chances, so larger
    samples count more). Ages need `min_rows` player-season rows. The band is a
    95% bootstrap over players."""
    d = aged.assign(age_int=np.floor(aged["age"]).astype(int))
    counts = d["age_int"].value_counts()
    ages = np.array(sorted(counts[counts >= min_rows].index))
    d = d[d["age_int"].isin(ages)].reset_index(drop=True)
    idx = np.searchsorted(ages, d["age_int"].to_numpy())
    frv, opp = d["total_sfg_frv"].to_numpy(), d["opportunities"].to_numpy()

    def rates(rows):
        return 100 * (np.bincount(idx[rows], weights=frv[rows], minlength=len(ages))
                      / np.bincount(idx[rows], weights=opp[rows], minlength=len(ages)))

    rng = np.random.default_rng(seed)
    by_player = list(d.groupby("player_code").indices.values())
    boots = np.array([rates(np.concatenate([by_player[i] for i in rng.integers(0, len(by_player), len(by_player))]))
                      for _ in range(n_boot)])
    lo, hi = np.nanpercentile(boots, [2.5, 97.5], axis=0)
    return pd.DataFrame({"age": ages, "rows": [int(counts[a]) for a in ages],
                         "players": d.groupby("age_int")["player_code"].nunique().reindex(ages).to_numpy(),
                         "rate": rates(np.arange(len(d))), "lo": lo, "hi": hi})


def aging_curve(aged, min_pairs=40, n_boot=300, seed=0, measure="percentile"):
    """How a fielder's rank among peers (percentile) changes over one season, by age.

    measure="z" runs the same model on FRV/100 as a z-score within season,
    level and position (centered at 0 instead of 0.5), as a robustness check.

    Pairs = same player and position in consecutive seasons, at any levels, so
    players who move up are kept. Players seen in consecutive seasons tend to
    have been above average the first year and drift back toward the middle
    whatever their age, and a promotion itself costs some rank, so fit
        next_percentile = alpha[age] + beta * (percentile - 0.5)
                          + g_up * moved_up + g_down * moved_down
    weighted by the harmonic mean of the two seasons' opportunities.
    alpha[age] - 0.5 is the expected one-season change for a player who starts
    at the median and stays at the same level. Ages need `min_pairs` pairs.
    Bands are 95% bootstrap intervals over players.
    Returns (by_age table, pairs, coefficients dict).
    """
    d = aged.sort_values(["player_code", "position", "year"]).copy()
    if measure == "z":
        d["standing"] = d.groupby(["year", "level", "position"])["sfg_frv_per_100"].transform(
            lambda s: (s - s.mean()) / s.std())
        center = 0.0
    else:
        d["standing"] = d["percentile"]
        center = 0.5
    grp = d.groupby(["player_code", "position"])
    for col, new_col in [("year", "next_year"), ("standing", "next_pctile"),
                         ("opportunities", "next_opp"), ("level_num", "next_level_num")]:
        d[new_col] = grp[col].shift(-1)
    pairs = d[d["next_year"] == d["year"] + 1].dropna(subset=["standing", "next_pctile"]).copy()
    pairs["age_int"] = np.floor(pairs["age"]).astype(int)
    pairs["w"] = 2 / (1 / pairs["opportunities"] + 1 / pairs["next_opp"])
    counts = pairs["age_int"].value_counts()
    ages = np.array(sorted(counts[counts >= min_pairs].index))
    pairs = pairs[pairs["age_int"].isin(ages)].reset_index(drop=True)

    age_idx = np.searchsorted(ages, pairs["age_int"].to_numpy())
    X = np.zeros((len(pairs), len(ages) + 3))
    X[np.arange(len(pairs)), age_idx] = 1
    X[:, -3] = pairs["standing"].to_numpy() - center
    X[:, -2] = (pairs["next_level_num"] > pairs["level_num"]).to_numpy(float)
    X[:, -1] = (pairs["next_level_num"] < pairs["level_num"]).to_numpy(float)
    y = pairs["next_pctile"].to_numpy()
    sw = np.sqrt(pairs["w"].to_numpy())

    def fit(rows):
        coef, *_ = np.linalg.lstsq(X[rows] * sw[rows, None], y[rows] * sw[rows], rcond=None)
        return coef

    coef = fit(np.arange(len(pairs)))
    rng = np.random.default_rng(seed)
    by_player = list(pairs.groupby("player_code").indices.values())
    if n_boot:
        boots = np.array([fit(np.concatenate([by_player[i] for i in rng.integers(0, len(by_player), len(by_player))]))
                          for _ in range(n_boot)])
        lo, hi = np.percentile(boots[:, : len(ages)] - center, [2.5, 97.5], axis=0)
    else:
        lo = hi = np.full(len(ages), np.nan)
    by_age = pd.DataFrame({"age": ages, "pairs": [int(counts[a]) for a in ages],
                           "change": coef[: len(ages)] - center, "lo": lo, "hi": hi})
    effects = {"carry": float(coef[-3]), "moved_up": float(coef[-2]), "moved_down": float(coef[-1])}
    return by_age, pairs, effects


def promotion_outcomes(qualified, all_rows, last_start_year):
    """For qualified minor-league seasons up to `last_start_year`: did the player
    later play (any position) at a higher level, and in MLB? "Later" means a stint
    at that level that started after this one did, so a player sent down
    mid-season isn't counted as moving up because of where they started the year.

    Seasons that start after a player's MLB debut are dropped, so veterans back in
    the minors don't count as "reaching" MLB.
    """
    seen = all_rows[["player_code", "level_num", "first_game"]].drop_duplicates()
    first_mlb_game = seen[seen["level_num"] == LEVEL_NUM["mlb"]].groupby("player_code")["first_game"].min()
    base = qualified[(qualified["level"] != "mlb") & (qualified["year"] <= last_start_year)].copy()
    debuted_before = base["player_code"].map(first_mlb_game).lt(base["first_game"]).fillna(False).astype(bool)
    base = base[~debuted_before]
    base["row_id"] = np.arange(len(base))
    m = base[["row_id", "player_code", "first_game", "level_num"]].merge(seen, on="player_code", suffixes=("", "_seen"))
    later = m[m["first_game_seen"] > m["first_game"]]
    base["moved_up"] = base["row_id"].isin(later.loc[later["level_num_seen"] > later["level_num"], "row_id"])
    base["reached_mlb"] = base["row_id"].isin(later.loc[later["level_num_seen"] == LEVEL_NUM["mlb"], "row_id"])
    base["starting_group"] = pd.cut(base["percentile"], bins=[-0.01, 0.20, 0.40, 0.60, 0.80, 1.01],
                                    labels=PERCENTILE_GROUPS)
    summary = base.groupby("starting_group", observed=True).agg(
        seasons=("moved_up", "size"), moved_up=("moved_up", "mean"), reached_mlb=("reached_mlb", "mean"),
    ).reset_index()
    return base, summary


def level_records(rows, keys, min_opportunities):
    """Each player's combined record at each level (all seasons pooled), with
    the date they first played there."""
    rec = rows.groupby(keys + ["level", "level_num"], as_index=False).agg(
        opportunities=("opportunities", "sum"), total_sfg_frv=("total_sfg_frv", "sum"),
        first_game=("first_game", "min"))
    rec["rate"] = 100 * rec["total_sfg_frv"] / rec["opportunities"]
    return rec[rec["opportunities"] >= min_opportunities]


def translation_table(records, keys, min_players):
    """Fit rate at a higher level on rate at a lower level, for every pair of levels.

    Uses players with a qualifying record at both levels (same position for
    fielders) whose first game at the higher level came after their first game
    at the lower one, i.e. who were promoted rather than sent down.
    Pairs with fewer than `min_players` players get no fit.
    """
    m = records.merge(records, on=keys, suffixes=("_a", "_b"))
    m = m[(m["level_num_b"] > m["level_num_a"]) & (m["first_game_b"] > m["first_game_a"])]
    rows = []
    for a in range(1, len(LEVEL_ORDER)):
        for b in range(a + 1, len(LEVEL_ORDER) + 1):
            x = m[(m["level_num_a"] == a) & (m["level_num_b"] == b)]
            row = {"from": LEVEL_LABEL_ORDER[a - 1], "to": LEVEL_LABEL_ORDER[b - 1],
                   "from_num": a, "to_num": b, "players": len(x),
                   "slope": np.nan, "intercept": np.nan, "resid_sd": np.nan}
            if len(x) >= min_players:
                slope, intercept = np.polyfit(x["rate_a"], x["rate_b"], 1)
                resid = x["rate_b"] - (intercept + slope * x["rate_a"])
                row.update(slope=slope, intercept=intercept, resid_sd=float(resid.std(ddof=2)))
            rows.append(row)
    return pd.DataFrame(rows)


# Positions next to each other on the field.
ADJACENT_POSITIONS = [("first_baseman", "second_baseman"), ("second_baseman", "shortstop"),
                      ("shortstop", "third_baseman"), ("left_fielder", "center_fielder"),
                      ("center_fielder", "right_fielder")]


def swap_table(qp, min_players):
    """For each adjacent pair (both directions): fit a player's FRV/100 at one
    position on their FRV/100 at the other, using players who qualified at both in
    the same season and level. Pairs with fewer than `min_players` get no fit."""
    m = qp.merge(qp, on=["player_code", "year", "level"], suffixes=("_a", "_b"))
    rows = []
    for a, b in ADJACENT_POSITIONS:
        for src, dst in [(a, b), (b, a)]:
            x = m[(m["position_a"] == src) & (m["position_b"] == dst)]
            row = {"from": POSITION_LABELS[src], "to": POSITION_LABELS[dst], "players": len(x),
                   "slope": np.nan, "intercept": np.nan, "resid_sd": np.nan, "mean_from": np.nan, "mean_to": np.nan}
            if len(x) >= min_players:
                slope, intercept = np.polyfit(x["sfg_frv_per_100_a"], x["sfg_frv_per_100_b"], 1)
                resid = x["sfg_frv_per_100_b"] - (intercept + slope * x["sfg_frv_per_100_a"])
                row.update(slope=slope, intercept=intercept, resid_sd=float(resid.std(ddof=2)),
                           mean_from=x["sfg_frv_per_100_a"].mean(), mean_to=x["sfg_frv_per_100_b"].mean())
            rows.append(row)
    return pd.DataFrame(rows)


def position_pairs(qp):
    """Same player, year and level at exactly two positions: harder minus easier percentile."""
    multi = qp[qp.groupby(["player_code", "year", "level"])["position"].transform("nunique") == 2]
    rows = []
    for _, group in multi.groupby(["player_code", "year", "level"]):
        group = group.assign(rank=group["position"].map(SPECTRUM_RANK)).sort_values("rank", ascending=False)
        harder, easier = group.iloc[0], group.iloc[1]
        rows.append({
            "harder_position": harder["position_label"], "easier_position": easier["position_label"],
            "harder_pctile": harder["percentile"], "easier_pctile": easier["percentile"],
            "gap": harder["percentile"] - easier["percentile"],
        })
    return pd.DataFrame(rows)


def position_moves(qp):
    """Year-over-year changes in primary position (most-opportunity qualified position)."""
    primary = (
        qp.sort_values("opportunities", ascending=False)
        .groupby(["player_code", "year"]).first().reset_index()
        .sort_values(["player_code", "year"])
    )
    primary["rank"] = primary["position"].map(SPECTRUM_RANK)
    grp = primary.groupby("player_code")
    primary["next_position_label"] = grp["position_label"].shift(-1)
    primary["next_rank"] = grp["rank"].shift(-1)
    primary["next_pctile"] = grp["percentile"].shift(-1)
    moves = primary[
        primary["next_position_label"].notna()
        & (primary["position_label"] != primary["next_position_label"])
    ].copy()
    moves["move_direction"] = np.where(moves["next_rank"] < moves["rank"],
                                       "Toward an easier position", "Toward a harder position")
    return moves


# ------------------------------------------------------------------ plots
# One chart per question; each takes the fielding or framing version of the
# same table so both halves of the article look alike.

def plot_level_spread(qualified, title, ylabel):
    fig, ax = plt.subplots(figsize=(FIG_W, 5))
    styled_boxplot(ax, clipped_by_level(qualified), LEVEL_LABEL_ORDER,
                   [LEVEL_RAMP[l] for l in LEVEL_LABEL_ORDER])
    ax.axhline(0, color=REFERENCE, linewidth=1, zorder=0)
    style_ax(ax, title=title,
             subtitle="Each box holds the middle half of players at that level; lines show the typical range",
             ylabel=ylabel)
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    plt.tight_layout()
    plt.show()


def plot_carryover(models, title):
    """Share of a player's edge over average that carries to the next level (slope as %)."""
    import matplotlib.ticker as mticker
    fig, ax = plt.subplots(figsize=(FIG_W, 4.6))
    x = np.arange(len(models))
    bars = ax.bar(x, models["slope"], width=0.6, edgecolor=INK, linewidth=0.7,
                  color=[LEVEL_RAMP[t] for t in models["to"]])
    for bar, value in zip(bars, models["slope"]):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.02, f"{value:.0%}",
                ha="center", va="bottom", fontsize=10, fontweight="bold", color=INK)
    ax.axhline(1, color=REFERENCE, linewidth=1, linestyle="--")
    ax.text(len(models) - 0.5, 1.01, "Everything carries over", ha="right", va="bottom",
            fontsize=8.5, color=MUTED)
    ax.set_xticks(x)
    ax.set_xticklabels(transition_labels(models), fontsize=8.5)
    ax.set_ylim(0, 1.1)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))
    style_ax(ax, title=title, subtitle="Share of a player's edge over average that shows up at the next level",
             ylabel="Share carried over")
    plt.tight_layout()
    plt.show()


def plot_slopes(models, title):
    fig, ax = plt.subplots(figsize=(FIG_W, 4.8))
    x = np.arange(len(models))
    w = 0.36
    ax.bar(x - w / 2, models["slope"], w, color="#9aa0a8", edgecolor=INK, linewidth=0.7,
           label="Raw FRV/100")
    ax.bar(x + w / 2, models["z_slope"], w, color=ACCENT, edgecolor=INK, linewidth=0.7,
           label="Standardized within season and level")
    ax.axhline(1, color=REFERENCE, linewidth=1, linestyle="--")
    ax.set_xticks(x)
    ax.set_xticklabels(transition_labels(models), fontsize=8)
    ax.set_ylim(0, 1.05)
    style_ax(ax, title=title, subtitle="Adjacent-level regression slope (1.0 = full carry-over)",
             ylabel="Slope")
    ax.legend(loc="upper left", frameon=False, fontsize=8.5)
    plt.tight_layout()
    plt.show()


def _share_bars(ax, groups, shares, reference=None, reference_label=None):
    """One labelled bar per rank group (bottom 20% ... top 20%)."""
    import matplotlib.ticker as mticker
    x = np.arange(len(groups))
    bars = ax.bar(x, shares, width=0.62, color=GROUP_COLORS[: len(groups)], edgecolor=INK, linewidth=0.7)
    for bar, value in zip(bars, shares):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.02, f"{value:.0%}",
                ha="center", va="bottom", fontsize=10.5, fontweight="bold", color=INK)
    if reference is not None:
        ax.axhline(reference, color=REFERENCE, linewidth=1, linestyle="--", zorder=0)
        ax.text(-0.45, reference + 0.01, reference_label, ha="left", va="bottom",
                fontsize=8.5, color=MUTED)
    ax.set_xticks(x)
    ax.set_xticklabels(groups)
    ax.set_ylim(0, 1)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))


def plot_persistence(pers, title, noun):
    fig, ax = plt.subplots(figsize=(FIG_W, 4.8))
    _share_bars(ax, list(pers["starting_group"]), pers["finished_above_average"],
                reference=0.5, reference_label="Coin flip")
    style_ax(ax, title=title,
             subtitle=f"Share of {noun} who were above average after moving up a level",
             xlabel="Where they ranked among peers before moving up",
             ylabel="Above average at the next level")
    plt.tight_layout()
    plt.show()


def plot_promotion(summary, metric, title, subtitle, noun):
    """metric: "moved_up" or "reached_mlb"."""
    fig, ax = plt.subplots(figsize=(FIG_W, 4.4))
    _share_bars(ax, list(summary["starting_group"]), summary[metric])
    style_ax(ax, title=title, subtitle=subtitle, ylabel=f"Share of {noun}",
             xlabel="Where they ranked among peers that season")
    plt.tight_layout()
    plt.show()


def plot_translation_grid(table, title, subtitle, levels=None):
    """Share of a player's edge that carries from each level (rows) to each higher level (columns)."""
    import matplotlib.colors as mcolors
    levels = levels or LEVEL_LABEL_ORDER
    table = table[table["from"].isin(levels) & table["to"].isin(levels)].copy()
    table["from_num"] = table["from"].map(levels.index) + 1
    table["to_num"] = table["to"].map(levels.index) + 1
    fig, ax = plt.subplots(figsize=(FIG_W, 0.85 * len(levels) + 0.9))
    cmap = mcolors.LinearSegmentedColormap.from_list("carry", ["#fde9df", "#f58a5c", "#c2410c", "#7c2d12"])
    for _, r in table.iterrows():
        x, y = r["to_num"] - 2, r["from_num"] - 1
        if np.isnan(r["slope"]):
            ax.add_patch(plt.Rectangle((x - 0.46, y - 0.44), 0.92, 0.88, facecolor="#f1efea",
                                       edgecolor="none"))
            ax.text(x, y - 0.08, "Too few", ha="center", va="center", fontsize=7.5, color=MUTED)
            ax.text(x, y + 0.2, f"{r['players']} players", ha="center", va="center", fontsize=6.5, color=MUTED)
            continue
        share = max(r["slope"], 0)
        color = mcolors.to_hex(cmap(min(share / 0.5, 1)))
        ax.add_patch(plt.Rectangle((x - 0.46, y - 0.44), 0.92, 0.88, facecolor=color, edgecolor="none"))
        ink = "white" if _is_dark(color) else INK
        ax.text(x, y - 0.08, f"{share:.0%}", ha="center", va="center", fontsize=11, fontweight="bold", color=ink)
        ax.text(x, y + 0.22, f"{r['players']} players", ha="center", va="center", fontsize=6.5, color=ink)
    ax.set_xlim(-0.5, len(levels) - 1.5)
    ax.set_ylim(len(levels) - 1.5, -0.5)
    ax.set_xticks(range(len(levels) - 1))
    ax.set_xticklabels(levels[1:], fontsize=8.5)
    ax.set_yticks(range(len(levels) - 1))
    ax.set_yticklabels(levels[:-1], fontsize=8.5)
    ax.xaxis.set_ticks_position("top")
    ax.tick_params(length=0)
    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_ylabel("From", fontsize=10, fontweight="bold")
    ax.xaxis.set_label_position("top")
    ax.set_xlabel("To", fontsize=10, fontweight="bold", labelpad=8)
    fig.text(0.012, 0.975, title, fontsize=12, fontweight="bold", color=INK, va="top")
    fig.text(0.012, 0.925, subtitle, fontsize=8.5, color=MUTED, va="top")
    plt.tight_layout(rect=[0, 0, 1, 0.9])
    plt.show()


def plot_age_profile(profile, title):
    fig, ax = plt.subplots(figsize=(FIG_W, 4.6))
    ax.fill_between(profile["age"], profile["lo"], profile["hi"], color=ACCENT, alpha=0.15, linewidth=0,
                    label="Likely range")
    ax.plot(profile["age"], profile["rate"], color=ACCENT, linewidth=2.2, marker="o", markersize=6,
            markeredgecolor="white", markeredgewidth=1.2, label="Average position player")
    ax.axhline(0, color=INK, linewidth=1, zorder=1)
    ax.set_xticks(profile["age"])
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:+.1f}" if v else "0")
    style_ax(ax, title=title,
             subtitle="Average runs saved per 100 chances at each age, all levels combined",
             xlabel="Age", ylabel="Runs saved per 100 chances")
    ax.legend(loc="lower left", frameon=False, fontsize=8.5)
    plt.tight_layout()
    plt.show()


def plot_aging_curve(by_age, title):
    """One bar per age: typical change in rank over the next season, with its likely range."""
    fig, ax = plt.subplots(figsize=(FIG_W, 4.8))
    pts = by_age["change"] * 100
    colors = [ACCENT if v >= 0 else "#59616c" for v in pts]
    ax.bar(by_age["age"], pts, width=0.65, color=colors, edgecolor=INK, linewidth=0.6, zorder=2)
    ax.errorbar(by_age["age"], pts, yerr=[pts - by_age["lo"] * 100, by_age["hi"] * 100 - pts],
                fmt="none", ecolor="#8a857d", elinewidth=1, capsize=2.5, zorder=3)
    ax.axhline(0, color=INK, linewidth=1, zorder=1)
    ax.set_xticks(by_age["age"])
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:+.0f}" if v else "0")
    style_ax(ax, title=title,
             subtitle="Typical change in rank over the next season for an average position player; "
                      "lines show the likely range",
             xlabel="Age", ylabel="Change in rank (points)")
    ax.text(by_age["age"].iloc[0] - 0.4, ax.get_ylim()[1] * 0.92, "Gaining ground on peers",
            fontsize=8.5, color=ACCENT, fontweight="bold")
    ax.text(by_age["age"].iloc[0] - 0.4, ax.get_ylim()[0] * 0.92, "Losing ground",
            fontsize=8.5, color="#59616c", fontweight="bold", va="bottom")
    plt.tight_layout()
    plt.show()


def plot_cohort_scatter(cohort, year, title, noun):
    import matplotlib.ticker as mticker
    fig, ax = plt.subplots(figsize=(FIG_W, 5.6))
    above = cohort["current_mlb_percentile"] > 0.5
    ax.scatter(cohort.loc[above, "average_minor_percentile"], cohort.loc[above, "current_mlb_percentile"],
               color=ACCENT, s=45, edgecolor=INK, linewidth=0.6, zorder=3,
               label=f"Above-average {noun} now")
    ax.scatter(cohort.loc[~above, "average_minor_percentile"], cohort.loc[~above, "current_mlb_percentile"],
               color="#59616c", s=45, edgecolor=INK, linewidth=0.6, alpha=0.75, zorder=3,
               label=f"Below-average {noun} now")
    ax.plot([0, 1], [0.5, 0.5], color=REFERENCE, linewidth=1, linestyle="--", zorder=0)
    ax.plot([0.5, 0.5], [0, 1], color=REFERENCE, linewidth=1, linestyle="--", zorder=0)
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.xaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))
    style_ax(ax, title=title,
             subtitle=f"Each dot is one {year} MLB {noun}; top right = above average in both",
             xlabel="Average rank among minor-league peers", ylabel=f"Rank among MLB peers in {year}")
    ax.legend(loc="lower right", frameon=False, fontsize=8.5)
    plt.tight_layout()
    plt.show()


def plot_journeys(cohort, minors, year, title, n=6):
    """Percentile path to MLB for the n highest and n lowest current FRV/100."""
    import matplotlib.ticker as mticker
    extremes = pd.concat([cohort.nlargest(n, "sfg_frv_per_100"), cohort.nsmallest(n, "sfg_frv_per_100")])
    extremes = extremes.drop_duplicates("player_code").sort_values("sfg_frv_per_100", ascending=False)
    cols = ["player_code", "year", "level_label", "level_num", "percentile"]
    trajectory = pd.concat([minors[minors["player_code"].isin(extremes["player_code"])][cols],
                            extremes[cols]]).sort_values(["player_code", "year", "level_num"])

    rows = int(np.ceil(len(extremes) / 3))
    fig, axes = plt.subplots(rows, 3, figsize=(FIG_W, 2.5 * rows + 0.9), sharey=True)
    axes = np.atleast_1d(axes).flatten()
    for ax in axes[len(extremes):]:
        ax.set_visible(False)
    for ax, (_, row) in zip(axes, extremes.iterrows()):
        pdata = trajectory[trajectory["player_code"] == row["player_code"]]
        ax.axhline(0.5, color="#c9cdd3", linewidth=1, linestyle="--", zorder=0)
        ax.plot(pdata["year"], pdata["percentile"], color="#c9cdd3", linewidth=1.4, zorder=1)
        for level, pts in pdata.groupby("level_label"):
            ax.scatter(pts["year"], pts["percentile"], color=LEVEL_COLORS[level],
                       marker=LEVEL_MARKERS[level], s=90 if level == "MLB" else 50,
                       edgecolor=INK, linewidth=0.6, zorder=2)
        ax.set_ylim(-0.02, 1.02)
        ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))
        years = sorted(pdata["year"].unique())
        ax.set_xticks(years)
        ax.set_xticklabels([f"'{int(y) % 100:02d}" for y in years], fontsize=8)
        label = f"{row['position_label']}, " if "position_label" in row else ""
        ax.set_title(f"{row['player_name']} ({label}{row['sfg_frv_per_100']:+.2f})",
                     fontsize=8.5, fontweight="bold", color=INK, pad=5)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
        ax.tick_params(axis="both", labelsize=8)
        ax.grid(axis="x", visible=False)

    fig.legend(handles=[
        plt.Line2D([0], [0], marker=LEVEL_MARKERS[l], color="w", markerfacecolor=c, markeredgecolor=INK,
                   markersize=10 if l == "MLB" else 8, label=l)
        for l, c in LEVEL_COLORS.items()
    ], loc="lower center", ncol=4, frameon=False, fontsize=8.5, bbox_to_anchor=(0.5, 0.0))
    plt.tight_layout(rect=[0, 0.06, 1, 0.92])
    fig.suptitle(f"{title}: the best and worst of {year}", fontsize=12, fontweight="bold",
                 x=0.015, y=0.99, ha="left")
    fig.text(0.015, 0.955, "Rank among peers at each stop on the way to MLB (100% = best at that level).\n"
             f"Number next to each name = runs saved per 100 chances in {year}.",
             fontsize=8.5, color=MUTED, ha="left", va="top")
    plt.show()


# ------------------------------------------------------------- catcher throwing
# Stolen-base attempts from queries/catcher_throwing.sql. The catcher's value is
# the stolen-base model's catcher_runs_plus_minus, which is on the offense's side,
# so throw_runs = -runs_plus_minus (positive = runs saved by the catcher), like
# framing. The source's single "rok" rookie code can't be split into DSL /
# Complex League like the rest of the article, and "win" is winter ball, so only
# Low-A to MLB are kept.

THROWING_MIN_ATTEMPTS = 30  # steal attempts per catcher-season-level
POP_RANGE, TTP_RANGE, SPEED_RANGE = (1.6, 2.4), (1.1, 1.8), (22, 32)  # plausible tracking values
ARM_RANGE = (60, 95)  # catcher arm strength, mph
FRAMING_COLOR, THROWING_COLOR = "#2a78d6", "#eb6834"


def load_catcher_throwing(refresh=False):
    sql = (QUERY_DIR / "catcher_throwing.sql").read_text(encoding="utf-8")
    t = cached_query("catcher_throwing", sql, refresh).rename(columns={"catcher_sfg_id": "player_code"})
    t = t[t["level"].isin(LEVEL_ORDER) & t["catcher_runs_plus_minus"].notna()].copy()
    # Steals mostly succeed, so the raw value averages below zero; measure it
    # against the average attempt at that level and season so 0 = average catcher.
    raw = -t["catcher_runs_plus_minus"]
    t["throw_runs"] = raw - raw.groupby([t["level"], t["year"]]).transform("mean")
    t["caught"] = 1 - t["is_successful_stolen_base_attempt"].astype(float)
    t["level_num"] = t["level"].map(LEVEL_NUM)
    t["level_label"] = t["level"].map(LEVEL_LABELS)
    t["game_date"] = pd.to_datetime(t["game_date"])
    for col, (lo, hi) in [("catcher_pop_time", POP_RANGE), ("ttp", TTP_RANGE), ("sprint_speed", SPEED_RANGE),
                          ("arm_strength", ARM_RANGE)]:
        t.loc[~t[col].between(lo, hi), col] = np.nan
    return t


def qualify_throwing(throws):
    """Catcher-season-level throwing rows, same schema as the framing/fielding tables
    (opportunities = steal attempts, sfg_frv_per_100 = throwing runs per 100 attempts)."""
    agg = throws.groupby(["player_code", "level", "year"], as_index=False).agg(
        opportunities=("caught", "size"), total_sfg_frv=("throw_runs", "sum"),
        caught_rate=("caught", "mean"), pop_time=("catcher_pop_time", "mean"),
        pops=("catcher_pop_time", "count"),
        first_game=("game_date", "min"), last_game=("game_date", "max"))
    agg = _add_rates(agg)
    qualified = agg[agg["opportunities"] >= THROWING_MIN_ATTEMPTS].copy()
    qualified["percentile"] = qualified.groupby(["year", "level"])["sfg_frv_per_100"].rank(pct=True)
    return agg, qualified


def catcher_value_split(framing_q, throwing_all):
    """Per level: spread (SD) of season framing runs vs season throwing runs, for
    catcher-seasons with a qualifying framing season and any throwing attempts."""
    m = framing_q.merge(throwing_all, on=["player_code", "level", "year"], suffixes=("_frame", "_throw"))
    rows = []
    for level_num, g in m.groupby("level_num_frame"):
        v_f, v_t = g["total_sfg_frv_frame"].var(), g["total_sfg_frv_throw"].var()
        rows.append({"level_num": level_num, "level_label": LEVEL_LABEL_ORDER[level_num - 1],
                     "catcher_seasons": len(g),
                     "framing_sd": np.sqrt(v_f), "throwing_sd": np.sqrt(v_t),
                     "throwing_share": v_t / (v_f + v_t),
                     "corr": g["total_sfg_frv_frame"].corr(g["total_sfg_frv_throw"])})
    return pd.DataFrame(rows).sort_values("level_num").reset_index(drop=True)


STEAL_FACTORS = ["catcher_pop_time", "arm_strength", "ttp", "sprint_speed"]


def steal_model(throws):
    """Logistic regression of caught stealing on the catcher's pop time and arm
    strength, the pitcher's time to plate and the runner's speed (plus level), on
    steals of second with all four measured.
    Returns (effects, n): change in caught-stealing rate in percentage points for a
    typical (1 SD) difference and per unit (0.1 s, 1 mph, 1 ft/s)."""
    d = throws[throws["attempted_base"] == "2B"].dropna(subset=STEAL_FACTORS)
    lv = pd.get_dummies(d["level"], drop_first=True, dtype=float)
    X = np.column_stack([np.ones(len(d))] + [d[c].to_numpy(float) for c in STEAL_FACTORS] + [lv.to_numpy()])
    y = d["caught"].to_numpy()
    beta = np.zeros(X.shape[1])
    for _ in range(100):  # Newton / IRLS
        p = 1 / (1 + np.exp(-X @ beta))
        step = np.linalg.solve(X.T @ (X * (p * (1 - p))[:, None]), X.T @ (y - p))
        beta += step
        if np.abs(step).max() < 1e-10:
            break
    p = 1 / (1 + np.exp(-X @ beta))
    scale = (p * (1 - p)).mean() * 100  # average marginal effect, in points
    sd = d[STEAL_FACTORS].std()
    b = dict(zip(STEAL_FACTORS, beta[1:1 + len(STEAL_FACTORS)]))
    # Reported as the gain for the defense: a quicker pop or delivery and a stronger
    # arm help the catcher; a faster runner hurts (negative).
    effects = {
        "pop_sd": -b["catcher_pop_time"] * sd["catcher_pop_time"] * scale,
        "pop_tenth": -b["catcher_pop_time"] * 0.1 * scale,
        "arm_sd": b["arm_strength"] * sd["arm_strength"] * scale, "arm_mph": b["arm_strength"] * scale,
        "ttp_sd": -b["ttp"] * sd["ttp"] * scale, "ttp_tenth": -b["ttp"] * 0.1 * scale,
        "speed_sd": b["sprint_speed"] * sd["sprint_speed"] * scale, "speed_1": b["sprint_speed"] * scale,
        "pop_sd_seconds": sd["catcher_pop_time"], "arm_sd_mph": sd["arm_strength"],
        "ttp_sd_seconds": sd["ttp"], "speed_sd_fts": sd["sprint_speed"], "caught_rate": y.mean(),
        "arm_pop_corr": d["arm_strength"].corr(d["catcher_pop_time"]),
    }
    return effects, len(d)


def caught_stealing_by_arm(throws, groups=4):
    """Caught-stealing rate on steals of second by the catcher's arm strength (equal-size groups)."""
    d = throws[throws["attempted_base"] == "2B"].dropna(subset=["arm_strength"])
    bins = pd.qcut(d["arm_strength"], groups)
    table = d.groupby(bins, observed=True).agg(
        attempts=("caught", "size"), caught_rate=("caught", "mean"),
        low=("arm_strength", "min"), high=("arm_strength", "max")).reset_index(drop=True)
    labels = []
    for i, r in table.iterrows():
        if i == 0:
            labels.append(f"Under {r['high']:.0f} mph")
        elif i == len(table) - 1:
            labels.append(f"Over {r['low']:.0f} mph")
        else:
            labels.append(f"{r['low']:.0f}–{r['high']:.0f} mph")
    table["label"] = labels
    return table, len(d)


def plot_cs_by_arm(table, title):
    import matplotlib.ticker as mticker
    fig, ax = plt.subplots(figsize=(FIG_W, 4.2))
    x = np.arange(len(table))
    bars = ax.bar(x, table["caught_rate"], width=0.6, color=GROUP_COLORS[1:1 + len(table)],
                  edgecolor=INK, linewidth=0.7)
    for bar, v, n in zip(bars, table["caught_rate"], table["attempts"]):
        ax.text(bar.get_x() + bar.get_width() / 2, v + 0.006, f"{v:.0%}", ha="center", va="bottom",
                fontsize=10.5, fontweight="bold", color=INK)
        ax.text(bar.get_x() + bar.get_width() / 2, 0.006, f"{n:,} attempts", ha="center", va="bottom",
                fontsize=7.5, color=INK)
    ax.set_xticks(x)
    ax.set_xticklabels(table["label"])
    ax.set_ylim(0, max(0.35, table["caught_rate"].max() * 1.25))
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))
    style_ax(ax, title=title, subtitle="Caught-stealing rate on steals of second, by the catcher's arm strength (four equal groups)",
             xlabel="Catcher's arm strength on the throw", ylabel="Caught-stealing rate")
    plt.tight_layout()
    plt.show()


POP_BINS = [1.6, 1.8, 1.9, 2.0, 2.4]
POP_LABELS = ["1.80 or faster", "1.80–1.90", "1.90–2.00", "Slower than 2.00"]
TTP_BINS = [1.1, 1.3, 1.4, 1.5, 1.8]
TTP_LABELS = ["1.30 or quicker", "1.30–1.40", "1.40–1.50", "Slower than 1.50"]


def caught_stealing_grid(throws):
    d = throws[throws["attempted_base"] == "2B"].dropna(subset=["catcher_pop_time", "ttp"])
    d = d.assign(pop_bin=pd.cut(d["catcher_pop_time"], POP_BINS, labels=POP_LABELS),
                 ttp_bin=pd.cut(d["ttp"], TTP_BINS, labels=TTP_LABELS))
    grid = d.groupby(["pop_bin", "ttp_bin"], observed=False).agg(
        attempts=("caught", "size"), caught_rate=("caught", "mean")).reset_index()
    return grid, len(d)


def throw_runs_by_delivery(throws, pop_window=(1.8, 1.9)):
    """Catcher throwing runs per attempt by the pitcher's time to plate (thirds),
    for throws in a narrow pop-time window so the catcher's own throw is similar."""
    d = throws[(throws["attempted_base"] == "2B") & throws["catcher_pop_time"].between(*pop_window)]
    d = d.dropna(subset=["ttp"])
    d = d.assign(delivery=pd.qcut(d["ttp"], 3, labels=["Quick to the plate", "Average", "Slow to the plate"]))
    return d.groupby("delivery", observed=True).agg(
        attempts=("caught", "size"), ttp=("ttp", "median"), caught_rate=("caught", "mean"),
        runs_per_attempt=("throw_runs", "mean")).reset_index()


def plot_value_split(split, title):
    fig, ax = plt.subplots(figsize=(FIG_W, 4.6))
    x = np.arange(len(split))
    w = 0.36
    for off, col, color, label in [(-w / 2, "framing_sd", FRAMING_COLOR, "Framing"),
                                   (w / 2, "throwing_sd", THROWING_COLOR, "Throwing")]:
        bars = ax.bar(x + off, split[col], w, color=color, edgecolor="white", linewidth=2, label=label)
        for bar, v in zip(bars, split[col]):
            ax.text(bar.get_x() + bar.get_width() / 2, v + 0.1, f"{v:.1f}", ha="center", va="bottom",
                    fontsize=9, color=INK)
    ax.set_xticks(x)
    ax.set_xticklabels(split["level_label"])
    style_ax(ax, title=title,
             subtitle="Runs per season separating a good catcher (one standard deviation above average) from an average one",
             ylabel="Runs per season")
    ax.legend(loc="upper right", frameon=False, fontsize=9, ncol=2)
    ax.set_ylim(0, split[["framing_sd", "throwing_sd"]].max().max() * 1.25)
    plt.tight_layout()
    plt.show()


def plot_caught_stealing_grid(grid, title):
    import matplotlib.colors as mcolors
    fig, ax = plt.subplots(figsize=(FIG_W, 4.8))
    cmap = mcolors.LinearSegmentedColormap.from_list("cs", ["#fde9df", "#f58a5c", "#c2410c", "#7c2d12"])
    vmax = grid["caught_rate"].max()
    for _, r in grid.iterrows():
        x, y = POP_LABELS.index(r["pop_bin"]), TTP_LABELS.index(r["ttp_bin"])
        if r["attempts"] < 50 or np.isnan(r["caught_rate"]):
            ax.add_patch(plt.Rectangle((x - 0.47, y - 0.45), 0.94, 0.9, facecolor="#f1efea"))
            ax.text(x, y, "Too few", ha="center", va="center", fontsize=8, color=MUTED)
            continue
        color = mcolors.to_hex(cmap(r["caught_rate"] / vmax))
        ax.add_patch(plt.Rectangle((x - 0.47, y - 0.45), 0.94, 0.9, facecolor=color))
        ink = "white" if _is_dark(color) else INK
        ax.text(x, y - 0.08, f"{r['caught_rate']:.0%}", ha="center", va="center", fontsize=12,
                fontweight="bold", color=ink)
        ax.text(x, y + 0.24, f"{int(r['attempts']):,} attempts", ha="center", va="center", fontsize=7, color=ink)
    ax.set_xlim(-0.5, len(POP_LABELS) - 0.5)
    ax.set_ylim(len(TTP_LABELS) - 0.5, -0.5)
    ax.set_xticks(range(len(POP_LABELS)))
    ax.set_xticklabels(POP_LABELS, fontsize=8.5)
    ax.set_yticks(range(len(TTP_LABELS)))
    ax.set_yticklabels(TTP_LABELS, fontsize=8.5)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    style_ax(ax, title=title, subtitle="Caught-stealing rate on steals of second",
             xlabel="Catcher's pop time (seconds)", ylabel="Pitcher's time to plate (seconds)")
    ax.grid(False)
    plt.tight_layout()
    plt.show()


def plot_delivery_effect(table, title):
    fig, ax = plt.subplots(figsize=(FIG_W, 4.4))
    x = np.arange(len(table))
    vals = table["runs_per_attempt"] * 100
    bars = ax.bar(x, vals, width=0.55, color=[THROWING_COLOR if v >= 0 else "#59616c" for v in vals],
                  edgecolor="white", linewidth=2)
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, v + (0.4 if v >= 0 else -0.4), f"{v:+.1f}",
                ha="center", va="bottom" if v >= 0 else "top", fontsize=10.5, fontweight="bold", color=INK)
    ax.axhline(0, color=INK, linewidth=1)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{d}\n(about {t:.2f} s, {cs:.0%} caught)" for d, t, cs in
                        zip(table["delivery"], table["ttp"], table["caught_rate"])], fontsize=8.5)
    ax.set_ylim(min(vals.min() * 1.6, -2), vals.max() * 1.35)
    ax.set_yticks(np.arange(np.ceil(ax.get_ylim()[0] / 2) * 2, ax.get_ylim()[1], 2))
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:+.0f}" if v else "0")
    style_ax(ax, title=title,
             subtitle="Catcher throwing runs per 100 steal attempts, throws with a pop time of 1.80–1.90 s",
             ylabel="Throwing runs per 100 attempts")
    plt.tight_layout()
    plt.show()


def plot_promotion_compare(framing, throwing, title):
    """Share who later moved up, by framing rank and by throwing rank."""
    import matplotlib.ticker as mticker
    fig, ax = plt.subplots(figsize=(FIG_W, 4.6))
    x = np.arange(len(PERCENTILE_GROUPS))
    w = 0.36
    for off, table, color, label in [(-w / 2, framing, FRAMING_COLOR, "Ranked by framing"),
                                     (w / 2, throwing, THROWING_COLOR, "Ranked by throwing")]:
        vals = table.set_index("starting_group").reindex(PERCENTILE_GROUPS)["moved_up"]
        bars = ax.bar(x + off, vals, w, color=color, edgecolor="white", linewidth=2, label=label)
        for bar, v in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, v + 0.015, f"{v:.0%}", ha="center", va="bottom",
                    fontsize=8.5, color=INK)
    ax.set_xticks(x)
    ax.set_xticklabels(PERCENTILE_GROUPS)
    ax.set_ylim(0, 1)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))
    style_ax(ax, title=title, subtitle="Share of catchers who later reached a higher level",
             xlabel="Where they ranked among peers that season", ylabel="Share of catchers")
    ax.legend(loc="upper left", frameon=False, fontsize=9, ncol=2)
    plt.tight_layout()
    plt.show()


def pop_time_by_level(throws, min_pops=10):
    """Median of catchers' average pop time at each level (catchers with min_pops tracked throws there)."""
    per = throws.groupby(["player_code", "level_num"])["catcher_pop_time"].agg(["mean", "count"])
    per = per[per["count"] >= min_pops].reset_index()
    return per.groupby("level_num")["mean"].median()


def pop_time_carry(throws, min_pops=10):
    """Slope of a catcher's average pop time at the next level on their pop time at
    the level below (catchers with min_pops tracked throws at both). Returns (slope, r, n)."""
    per = throws.groupby(["player_code", "level_num"])["catcher_pop_time"].agg(["mean", "count"])
    per = per[per["count"] >= min_pops].reset_index()
    m = per.merge(per, on="player_code", suffixes=("_a", "_b"))
    m = m[m["level_num_b"] == m["level_num_a"] + 1]
    if len(m) < 10:
        return np.nan, np.nan, len(m)
    slope = np.polyfit(m["mean_a"], m["mean_b"], 1)[0]
    return slope, m["mean_a"].corr(m["mean_b"]), len(m)


def pop_time_repeat(throws, min_pops=10):
    """Correlation of a catcher's average pop time in one season with the next
    (catchers with min_pops tracked throws in both seasons). Returns (r, n)."""
    per = throws.groupby(["player_code", "year"])["catcher_pop_time"].agg(["mean", "count"])
    per = per[per["count"] >= min_pops].reset_index()
    m = per.merge(per.assign(year=per["year"] - 1), on=["player_code", "year"], suffixes=("", "_next"))
    return (m["mean"].corr(m["mean_next"]) if len(m) >= 10 else np.nan), len(m)


def up_down_comparison(groups):
    """For each (label, qualified, group_cols): how much of a player's standing
    (within-season-and-level z-score) carries to the next level, for promotions
    and for demotions, plus how often top/bottom-20% players are above average
    at the new level."""
    rows = []
    for label, qualified, group_cols in groups:
        for direction in ("up", "down"):
            tr = adjacent_transitions(qualified, group_cols, direction).dropna(subset=["z_frv", "next_z"])
            p = tr["percentile"]
            rows.append({"group": label, "direction": direction, "moves": len(tr),
                         "z_slope": np.polyfit(tr["z_frv"], tr["next_z"], 1)[0],
                         "top_above": (tr.loc[p > 0.8, "next_percentile"] > 0.5).mean(),
                         "bottom_above": (tr.loc[p <= 0.2, "next_percentile"] > 0.5).mean(),
                         "pct_before": p.mean(), "pct_after": tr["next_percentile"].mean(),
                         "steps": (tr["from"] + " → " + tr["to"]).value_counts().to_dict()})
    return pd.DataFrame(rows)


UP_COLOR, DOWN_COLOR = "#4a3aa7", "#1baf7a"


def plot_up_down(table, title):
    import matplotlib.ticker as mticker
    fig, ax = plt.subplots(figsize=(FIG_W, 4.6))
    groups = list(dict.fromkeys(table["group"]))
    x = np.arange(len(groups))
    w = 0.36
    for off, direction, color, label in [(-w / 2, "up", UP_COLOR, "Moving up a level"),
                                         (w / 2, "down", DOWN_COLOR, "Moving down a level")]:
        sub = table[table["direction"] == direction].set_index("group").reindex(groups)
        bars = ax.bar(x + off, sub["z_slope"], w, color=color, edgecolor="white", linewidth=2, label=label)
        for bar, v, n in zip(bars, sub["z_slope"], sub["moves"]):
            ax.text(bar.get_x() + bar.get_width() / 2, v + 0.015, f"{v:.0%}", ha="center", va="bottom",
                    fontsize=10, fontweight="bold", color=INK)
            ax.text(bar.get_x() + bar.get_width() / 2, 0.02, f"{n:,}\nmoves", ha="center", va="bottom",
                    fontsize=7.5, color="white")
    ax.set_xticks(x)
    ax.set_xticklabels(groups)
    ax.set_ylim(0, max(0.6, table["z_slope"].max() * 1.3))
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))
    style_ax(ax, title=title,
             subtitle="Share of a player's edge over their peers that carries to the new level, "
                      "measured against peers at each level",
             ylabel="Share carried over")
    ax.legend(loc="upper right", frameon=False, fontsize=9, ncol=2)
    plt.tight_layout()
    plt.show()


# ------------------------------------------------------------- reliability
# How much of a rate is the player (signal) and how much is chance (noise).
# Split-half: for each sample size n, take player-seasons with at least 2n
# events, put their events in random order, and correlate the rate over the
# first n with the rate over the next n, across players (each half measured
# against its season-level(-position) peers). That correlation is the
# reliability of a rate based on n events. Between measured sample sizes we
# interpolate; past the largest one we extend with the Spearman-Brown formula
# from the largest measured point (flagged as extrapolated).

def split_half_points(events, group_cols, value_col, peer_cols, sizes, seed=0):
    """Split-half correlation at each sample size, from event-level rows."""
    rng = np.random.default_rng(seed)
    d = events[group_cols + [value_col]].dropna().copy()
    d["order"] = rng.random(len(d))
    d = d.sort_values(group_cols + ["order"])
    d["rn"] = d.groupby(group_cols).cumcount() + 1
    d["total"] = d.groupby(group_cols)[value_col].transform("size")
    rows = []
    for n in sizes:
        x = d[(d["total"] >= 2 * n) & (d["rn"] <= 2 * n)]
        halves = (x.assign(half=np.where(x["rn"] <= n, "a", "b"))
                  .groupby(group_cols + ["half"])[value_col].mean().unstack("half").reset_index())
        rows.append(_half_corr(halves, peer_cols, n))
    return pd.DataFrame([r for r in rows if r is not None])


def split_half_points_from_sums(sums, peer_cols):
    """Split-half correlation from per-player half sums (framing, done in BigQuery)."""
    rows = []
    for n, g in sums.groupby("n"):
        halves = g.assign(a=g["half_a_frv"] / n, b=g["half_b_frv"] / n)
        rows.append(_half_corr(halves, peer_cols, int(n)))
    return pd.DataFrame([r for r in rows if r is not None])


def _half_corr(halves, peer_cols, n, min_players=30):
    if len(halves) < min_players:
        return None
    for h in "ab":
        halves[h + "_c"] = halves[h] - halves.groupby(peer_cols)[h].transform("mean")
    return {"n": n, "r": halves["a_c"].corr(halves["b_c"]), "players": len(halves)}


def _spearman_brown(r, factor):
    return factor * r / (1 + (factor - 1) * r)


def reliability_at(points, n):
    """Reliability of a rate over n events: interpolated between measured points,
    Spearman-Brown from the nearest end point outside them."""
    pts = points.sort_values("n")
    ns, rs = pts["n"].to_numpy(float), pts["r"].to_numpy(float)
    n = np.asarray(n, dtype=float)
    out = np.interp(n, ns, rs)
    out = np.where(n > ns[-1], _spearman_brown(rs[-1], n / ns[-1]), out)
    return np.where(n < ns[0], _spearman_brown(rs[0], n / ns[0]), out)


def n_for_reliability(points, target):
    """Events needed to reach `target` reliability. Returns (n, extrapolated)."""
    pts = points.sort_values("n")
    ns, rs = pts["n"].to_numpy(float), pts["r"].to_numpy(float)
    above = np.nonzero(rs >= target)[0]
    if len(above) and above[0] > 0:
        i = above[0]
        return ns[i - 1] + (target - rs[i - 1]) * (ns[i] - ns[i - 1]) / (rs[i] - rs[i - 1]), False
    if len(above):
        return ns[0], False
    # Spearman-Brown from the largest measured point
    factor = target * (1 - rs[-1]) / (rs[-1] * (1 - target))
    return ns[-1] * factor, True


def season_to_season(rows, keys, peer_cols, min_opportunities):
    """Correlation of a player's rate in one season with the next, each measured
    against level-season(-position) peers (rows at several levels in a season are
    combined, weighted by opportunities). Returns (r, pairs)."""
    r = rows[rows["opportunities"] >= min_opportunities].copy()
    r["c"] = r["sfg_frv_per_100"] - r.groupby(peer_cols)["sfg_frv_per_100"].transform("mean")
    r["cw"] = r["c"] * r["opportunities"]
    s = r.groupby(keys + ["year"], as_index=False)[["cw", "opportunities"]].sum()
    s["c"] = s["cw"] / s["opportunities"]
    m = s.merge(s.assign(year=s["year"] - 1), on=keys + ["year"], suffixes=("", "_next"))
    return m["c"].corr(m["c_next"]), len(m)


def plot_reliability(curves, title):
    """curves: list of dicts with label, unit, points, typical (median qualifying season)."""
    import matplotlib.ticker as mticker
    fig, axes = plt.subplots(1, len(curves), figsize=(FIG_W, 4.2), sharey=True)
    axes = np.atleast_1d(axes)
    for ax, c in zip(axes, curves):
        pts = c["points"].sort_values("n")
        xmax = max(pts["n"].max(), c["typical"]) * 1.25
        ax.axhline(0.5, color=REFERENCE, linewidth=1, linestyle="--", zorder=0)
        ax.axhline(0.7, color=REFERENCE, linewidth=1, linestyle=":", zorder=0)
        ax.plot(pts["n"], pts["r"], color=ACCENT, linewidth=2.2, marker="o", markersize=5, zorder=3)
        if xmax > pts["n"].max():
            xs = np.linspace(pts["n"].max(), xmax, 50)
            ax.plot(xs, reliability_at(pts, xs), color=ACCENT, linewidth=1.6, linestyle="--", zorder=2)
        ax.axvline(c["typical"], color="#59616c", linewidth=1, zorder=1)
        ax.text(c["typical"], 0.03, " typical\n season", fontsize=7.5, color="#59616c", va="bottom")
        ax.set_xlim(0, xmax)
        ax.set_ylim(0, 1)
        ax.xaxis.set_major_locator(mticker.MaxNLocator(4))
        ax.xaxis.set_major_formatter(mticker.StrMethodFormatter("{x:,.0f}"))
        ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))
        style_ax(ax, title=c["label"], xlabel=c["unit"], ylabel="Reliability" if ax is axes[0] else None)
        ax.title.set_fontsize(10.5)
    fig.text(0.01, 0.985, title, fontsize=12, fontweight="bold", color=INK, ha="left", va="top")
    fig.text(0.01, 0.925, "Share of a rate that reflects the player rather than chance. Solid = measured "
             "(split-half), dashed = extended; grey lines at 50% and 70%", fontsize=8, color=MUTED, ha="left",
             va="top")
    plt.tight_layout(rect=[0, 0, 1, 0.88], w_pad=2.5)
    plt.show()


# ------------------------------------------------------- caught-stealing rates
CURRENT_RULES_FROM = 2023  # MLB adopted the minor-league running-game rules this season


def caught_stealing_by_level(throws, first_year=CURRENT_RULES_FROM):
    """Caught-stealing rate and attempts by level and base stolen, from first_year on."""
    d = throws[throws["year"] >= first_year]
    return (d.groupby(["level_num", "level_label", "attempted_base"])
            .agg(attempts=("caught", "size"), caught_rate=("caught", "mean")).reset_index())


def caught_stealing_by_season(throws):
    return (throws.groupby(["year", "level_label"])
            .agg(attempts=("caught", "size"), caught_rate=("caught", "mean")).reset_index())


def plot_cs_by_level(table, title):
    import matplotlib.ticker as mticker
    fig, ax = plt.subplots(figsize=(FIG_W, 4.4))
    levels = [l for l in LEVEL_LABEL_ORDER if l in set(table["level_label"])]
    x = np.arange(len(levels))
    w = 0.36
    for off, base, color, label in [(-w / 2, "2B", ACCENT, "Steals of second"),
                                    (w / 2, "3B", "#59616c", "Steals of third")]:
        sub = table[table["attempted_base"] == base].set_index("level_label").reindex(levels)
        bars = ax.bar(x + off, sub["caught_rate"], w, color=color, edgecolor="white", linewidth=2, label=label)
        for bar, v in zip(bars, sub["caught_rate"]):
            ax.text(bar.get_x() + bar.get_width() / 2, v + 0.006, f"{v:.0%}", ha="center", va="bottom",
                    fontsize=9, color=INK)
    ax.set_xticks(x)
    ax.set_xticklabels(levels)
    ax.set_ylim(0, max(0.3, table["caught_rate"].max() * 1.3))
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))
    style_ax(ax, title=title, subtitle=f"Share of steal attempts that ended in a caught stealing, "
                                       f"{CURRENT_RULES_FROM} and later", ylabel="Caught-stealing rate")
    ax.legend(loc="upper right", frameon=False, fontsize=9, ncol=2)
    plt.tight_layout()
    plt.show()


def plot_cs_by_season(table, title):
    import matplotlib.ticker as mticker
    fig, ax = plt.subplots(figsize=(FIG_W, 4.6))
    all_years = range(int(table["year"].min()), int(table["year"].max()) + 1)
    for level in LEVEL_LABEL_ORDER:
        sub = table[table["level_label"] == level].set_index("year")
        if sub.empty:
            continue
        # reindex over every season so a missing one (2020 in the minors) breaks the line
        sub = sub.reindex(all_years).reset_index()
        ax.plot(sub["year"], sub["caught_rate"], color=LEVEL_COLORS[level], marker=LEVEL_MARKERS[level],
                markersize=9 if level == "MLB" else 6, markeredgecolor=INK, markeredgewidth=0.5,
                linewidth=1.8, label=level)
    ax.axvline(CURRENT_RULES_FROM - 0.5, color=REFERENCE, linewidth=1, linestyle="--", zorder=0)
    ax.text(CURRENT_RULES_FROM - 0.4, 0.315, "Same running-game\nrules at every level", fontsize=8,
            color=MUTED, va="top")
    years = sorted(table["year"].unique())
    ax.set_xticks(years)
    ax.set_xticklabels([f"'{int(y) % 100:02d}" for y in years])
    ax.set_ylim(0, 0.33)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))
    style_ax(ax, title=title, subtitle="Caught-stealing rate by season (no minor-league season in 2020)",
             ylabel="Caught-stealing rate")
    ax.legend(loc="lower left", frameon=False, fontsize=8.5, ncol=5)
    plt.tight_layout()
    plt.show()


def persistence_by_z(trans):
    """Rank-persistence check on z-scores: group transitions into fifths by their
    z-score (within season and level) and report the share above average (z > 0)
    at the next level."""
    groups = pd.qcut(trans["z_frv"], 5, labels=PERCENTILE_GROUPS)
    return (trans.assign(starting_group=groups).groupby("starting_group", observed=True)
            .agg(transitions=("next_z", "size"), finished_above_average=("next_z", lambda s: (s > 0).mean()))
            .reset_index())
