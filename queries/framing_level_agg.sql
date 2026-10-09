-- Catcher framing rolled up to one row per catcher-season-level.
-- The source table (frv-catching) is pitch-level (~24M rows), too large to
-- pull client-side, so the roll-up happens here instead of in pandas.
-- "Opportunities" = called pitches (ball_called / strike_called), the same
-- population `runs_plus_minus` is modeled over.
SELECT
    catcher_sfg_id,
    ANY_VALUE(catcher_name) AS catcher_name,
    sport_code AS level,
    EXTRACT(YEAR FROM game_date) AS year,
    COUNT(*) AS opportunities,
    COUNT(DISTINCT game_pk) AS games,
    CAST(MIN(game_date) AS STRING) AS first_game,
    CAST(MAX(game_date) AS STRING) AS last_game,
    SUM(-runs_plus_minus) AS total_sfg_frv
FROM
    `sfgiants-viewer.analyst_isardina.frv-catching`
WHERE
    runs_plus_minus IS NOT NULL
    AND sport_code IS NOT NULL
GROUP BY
    catcher_sfg_id, sport_code, year
