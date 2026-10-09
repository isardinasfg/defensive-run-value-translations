-- Every stolen-base attempt in the xsb table, plus level and season from the
-- game event table (xsb has neither). One row per attempt.
-- Run values (runs_plus_minus) are from the offense's side: positive = good
-- for the runner. catcher_runs_plus_minus is the stolen-base model's catcher
-- share of the attempt (pitcher and baserunner shares are separate columns);
-- catcher_throwing_runs_plus_minus is the throw model's value, only on
-- attempts with a tracked throw. Pop time / arm strength / runner speed /
-- time to plate are NULL where tracking or pitcher biomechanics didn't match.
SELECT
    x.trackman_pitch_uid,
    x.origin,
    x.attempted_base,
    x.is_successful_stolen_base_attempt,
    x.catcher_runs_plus_minus,
    x.pitcher_runs_plus_minus,
    x.baserunner_runs_plus_minus,
    x.catcher_throwing_runs_plus_minus,
    x.catcher_pop_time,
    x.arm_strength,
    x.sprint_speed,
    x.ttp,
    x.total_delivery_time,
    x.pitch_zone_time,
    x.catcher_sfg_id,
    x.pitcher_sfg_id,
    x.game_pk,
    x.game_date,
    ge.sport_code AS level,
    ge.year
FROM
    `sfgiants-viewer.analyst_isardina.xsb` x
    INNER JOIN (
        SELECT
            CAST(trackman_pitch_uid AS STRING) AS trackman_pitch_uid,
            ANY_VALUE(sport_code) AS sport_code,
            ANY_VALUE(year) AS year
        FROM
            `prod-warehouse-sfgiants.game_event.pro`
        WHERE
            game_type = 'R'
            AND CAST(trackman_pitch_uid AS STRING) IN (
                SELECT trackman_pitch_uid FROM `sfgiants-viewer.analyst_isardina.xsb`
            )
        GROUP BY
            1
    ) ge USING (trackman_pitch_uid)
WHERE
    x.catcher_sfg_id IS NOT NULL
