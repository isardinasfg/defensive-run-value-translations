select
    year,
    game_pk,
    sfg_id as player_code,
    sport_code,
    runs_plus_minus,
    player_type as position
from
    `sfgiants-analyst.runs_above_average.fielding_play_by_play_pro_combined_linear_weights_current`
where
    year >= 2021
    and sport_code not in ('dwl', 'afl')
    and player_type not in ('baserunner', 'pitcher')