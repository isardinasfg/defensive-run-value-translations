SELECT
    game_pk,
    sfg_id as catcher_sfg_id,
    runs_above_average as catcher_throwing_runs_plus_minus,
    is_sb,
    sport_code,
    year
FROM
    `sfgiants-analyst.runs_above_average.catcher_throw_play_by_play_pro_statcast_current`
WHERE
    year >= 2021