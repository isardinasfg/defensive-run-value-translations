-- Split-half inputs for framing reliability at several sample sizes, without
-- pulling pitch-level rows. Within each catcher-season-level, pitches are put in
-- a fixed random order (hash of the pitch id). For each sample size n, catcher-
-- seasons with at least 2n pitches contribute the sum of their first n pitches
-- (half A) and of the next n (half B). Same filters as framing_level_agg.sql.
WITH pitches AS (
    SELECT
        catcher_sfg_id,
        sport_code AS level,
        EXTRACT(YEAR FROM game_date) AS year,
        -runs_plus_minus AS frv,
        ROW_NUMBER() OVER (
            PARTITION BY catcher_sfg_id, sport_code, EXTRACT(YEAR FROM game_date)
            ORDER BY FARM_FINGERPRINT(trackman_pitch_uid)
        ) AS rn,
        COUNT(*) OVER (
            PARTITION BY catcher_sfg_id, sport_code, EXTRACT(YEAR FROM game_date)
        ) AS total
    FROM
        `sfgiants-viewer.analyst_isardina.frv-catching`
    WHERE
        runs_plus_minus IS NOT NULL
        AND sport_code IS NOT NULL
)
SELECT
    catcher_sfg_id,
    level,
    year,
    n,
    SUM(IF(rn <= n, frv, 0)) AS half_a_frv,
    SUM(IF(rn > n, frv, 0)) AS half_b_frv
FROM
    pitches
    CROSS JOIN UNNEST([50, 100, 200, 300, 500, 750, 1000, 1500, 2000]) AS n
WHERE
    total >= 2 * n
    AND rn <= 2 * n
GROUP BY
    catcher_sfg_id, level, year, n
