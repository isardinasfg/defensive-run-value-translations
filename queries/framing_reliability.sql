-- Framing reliability inputs, one row per catcher-season-level (same filters as
-- framing_level_agg.sql). Besides the totals it returns the sum of squared
-- per-pitch values (for the within-catcher pitch-to-pitch variance) and the
-- totals for a random half of pitches (a fixed hash of the pitch id), so
-- split-half reliability can be computed without pulling ~24M pitch rows.
SELECT
    catcher_sfg_id,
    sport_code AS level,
    EXTRACT(YEAR FROM game_date) AS year,
    COUNT(*) AS opportunities,
    SUM(-runs_plus_minus) AS total_sfg_frv,
    SUM(runs_plus_minus * runs_plus_minus) AS sum_sq,
    COUNTIF(MOD(ABS(FARM_FINGERPRINT(trackman_pitch_uid)), 2) = 0) AS half_a_opportunities,
    SUM(IF(MOD(ABS(FARM_FINGERPRINT(trackman_pitch_uid)), 2) = 0, -runs_plus_minus, 0)) AS half_a_frv
FROM
    `sfgiants-viewer.analyst_isardina.frv-catching`
WHERE
    runs_plus_minus IS NOT NULL
    AND sport_code IS NOT NULL
GROUP BY
    catcher_sfg_id, sport_code, year
