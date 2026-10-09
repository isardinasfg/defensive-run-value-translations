CREATE
OR REPLACE TABLE `sfgiants-viewer.analyst_isardina.frv-catching` AS WITH game_sport AS (
    SELECT
        game_pk,
        ANY_VALUE(sport_code) AS sport_code
    FROM
        `sfgiants-analyst.runs_above_average.fielding_play_by_play_pro_combined_linear_weights_current`
    WHERE
        year >= 2021
        AND sport_code NOT IN ('dwl', 'afl')
        AND player_type NOT IN ('baserunner', 'pitcher')
    GROUP BY
        game_pk
),
pitches AS (
    SELECT
        pitch_type,
        catcher_sfg_id,
        strikezone_top,
        strikezone_bottom,
        catcher_classifications.glove_location_side,
        catcher_classifications.glove_location_primary_zone,
        catcher_classifications.glove_location_broad_zone,
        catcher_classifications.glove_location_depth,
        catcher_classifications.stance,
        trackman_pitch_uid,
        game_date,
        game_pk,
        inning,
        pitcher_sfg_id,
        hitter_sfg_id
    FROM
        `sfgiants-viewer.game_event.pro`
    WHERE
        game_date >= '2021-01-01'
        AND game_type = 'R'
),
catching AS (
    SELECT
        pitch_uid,
        ANY_VALUE(sfg_id) AS sfg_id,
        AVG(called_strike_pred) AS called_strike_pred,
        AVG(called_strike_avg) AS called_strike_avg,
        ANY_VALUE(event_type) AS event_type,
        AVG(runs_above_average) AS runs_above_average,
        AVG(runs_plus_minus) AS runs_plus_minus
    FROM
        `sfgiants-analyst.runs_above_average.catching_play_by_play_pro_trackman_current_materialized`
    WHERE
        year >= 2021
        AND player_type = 'catcher'
    GROUP BY
        pitch_uid
)
SELECT
    p.*,
    gs.sport_code,
    CONCAT(map.last_name, ", ", map.first_name) AS catcher_name,
    c.called_strike_pred,
    c.called_strike_avg,
    c.event_type,
    c.runs_above_average,
    c.runs_plus_minus
FROM
    pitches p
    LEFT JOIN catching c ON p.trackman_pitch_uid = c.pitch_uid
    LEFT JOIN game_sport gs ON p.game_pk = gs.game_pk
    LEFT JOIN `sfgiants-viewer.scout_replica_scouting.tblPlayer_Pro` map ON p.catcher_sfg_id = map.player_code;