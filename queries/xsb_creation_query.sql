CREATE OR REPLACE TABLE `sfgiants-viewer.analyst_isardina.xsb` AS

WITH sba AS (
  SELECT
    CAST(trackman_pitch_uid AS STRING) AS trackman_pitch_uid,
    origin,

    CASE
      WHEN origin = '1B' THEN '2B'
      WHEN origin = '2B' THEN '3B'
    END AS attempted_base,

    MAX(is_sb) = 1 AS is_successful_stolen_base_attempt,

    MAX(
      IF(player_type = 'pitcher', runs_plus_minus, NULL)
    ) AS pitcher_runs_plus_minus,

    MAX(
      IF(player_type = 'catcher', runs_plus_minus, NULL)
    ) AS catcher_runs_plus_minus,

    MAX(
      IF(player_type = 'baserunner', runs_plus_minus, NULL)
    ) AS baserunner_runs_plus_minus

  FROM
    `sfgiants-analyst.runs_above_average.stolen_base_attempt_pro_trackman_current`

  WHERE
    is_sba = 1
    AND trackman_pitch_uid IS NOT NULL
    AND origin IN ('1B', '2B')

  GROUP BY
    trackman_pitch_uid,
    origin
),

sba_ids AS (
  SELECT DISTINCT
    trackman_pitch_uid
  FROM sba
),

-- ============================================================
-- GAME / PLAY INFORMATION
-- Keep this independent of Hawkeye/TTP availability.
-- ============================================================

game_info AS (
  SELECT
    CAST(ge.trackman_pitch_uid AS STRING) AS trackman_pitch_uid,

    ge.game_pk,
    ge.game_date,

    ge.pitcher_sfg_id,
    ge.pitcher_name,
    ge.pitch_type,

    ge.catcher_sfg_id,

    ge.runner_on_first_base_sfg_id,
    ge.runner_on_second_base_sfg_id,
    ge.runner_on_third_base_sfg_id,

    ge.pitch_zone_time

  FROM
    `prod-warehouse-sfgiants.game_event.pro` ge

  INNER JOIN sba_ids
    ON CAST(ge.trackman_pitch_uid AS STRING) =
       sba_ids.trackman_pitch_uid

  WHERE
    ge.game_type = 'R'

  QUALIFY
    ROW_NUMBER() OVER (
      PARTITION BY CAST(ge.trackman_pitch_uid AS STRING)
      ORDER BY ge.game_date DESC
    ) = 1
),

-- ============================================================
-- TRACKING METRICS
-- ============================================================

tracking_metrics AS (
  SELECT
    CAST(met.playID AS STRING) AS trackman_pitch_uid,

    COUNT(DISTINCT met.stat_type_id) AS tracking_stats_matched,

    MAX(
      IF(met.stat_type_id = 28, met.value, NULL)
    ) AS catcher_pop_time,

    MAX(
      IF(met.stat_type_id = 3, met.value, NULL)
    ) AS arm_strength,

    MAX(
      IF(met.stat_type_id = 74, met.value, NULL)
    ) AS sprint_speed

  FROM
    `prod-etl-sfgiants.dbt.stg_player_tracking_positional_metrics_pro` met

  INNER JOIN sba_ids
    ON CAST(met.playID AS STRING) =
       sba_ids.trackman_pitch_uid

  WHERE
    met.stat_type_id IN (28, 3, 41, 43, 44, 74, 15)

  GROUP BY
    trackman_pitch_uid
),

-- ============================================================
-- TIME TO PLATE
-- Supplemental measurement only.
-- Missing TTP will no longer remove game/catcher information.
-- ============================================================

ttp AS (
  SELECT
    CAST(ge.trackman_pitch_uid AS STRING) AS trackman_pitch_uid,

    CASE
      WHEN ge.pitcher_name = 'Rogers, Tyler'
        THEN ROUND(
          he.total_delivery_time + ge.pitch_zone_time,
          2
        )
      ELSE ROUND(
        he.total_delivery_time + ge.pitch_zone_time - 0.15,
        2
      )
    END AS ttp,

    he.total_delivery_time,
    he.max_knee_height

  FROM
    `prod-warehouse-sfgiants.game_event.pro` ge

  INNER JOIN sba_ids
    ON CAST(ge.trackman_pitch_uid AS STRING) =
       sba_ids.trackman_pitch_uid

  INNER JOIN
    `sfgiants-analyst.pitcher_biomechanics.hawkeye` he
    ON CAST(he.pitch_uid AS STRING) =
       CAST(ge.trackman_pitch_uid AS STRING)

  WHERE
    ge.game_type = 'R'
    AND he.total_delivery_time IS NOT NULL
    AND ge.pitch_zone_time IS NOT NULL

  QUALIFY
    ROW_NUMBER() OVER (
      PARTITION BY CAST(ge.trackman_pitch_uid AS STRING)
      ORDER BY
        he.max_knee_height IS NOT NULL DESC,
        he.total_delivery_time DESC
    ) = 1
),

-- ============================================================
-- CATCHER THROWING
-- ============================================================

catching AS (
  SELECT
    CAST(play_id AS STRING) AS trackman_pitch_uid,

    ANY_VALUE(sfg_id) AS catching_sfg_id,

    SUM(runs_plus_minus) AS catcher_throwing_runs_plus_minus

  FROM
    `sfgiants-analyst.runs_above_average.catcher_throw_play_by_play_pro_statcast_current`

  WHERE
    play_id IS NOT NULL

  GROUP BY
    trackman_pitch_uid
)

-- ============================================================
-- FINAL TABLE
-- Grain = trackman_pitch_uid + origin
-- ============================================================

SELECT
  -- Attempt
  sba.trackman_pitch_uid,
  sba.origin,
  sba.attempted_base,
  sba.is_successful_stolen_base_attempt,

  -- SBA run values
  sba.pitcher_runs_plus_minus,
  sba.catcher_runs_plus_minus,
  sba.baserunner_runs_plus_minus,

  -- Game
  ge.game_pk,
  ge.game_date,

  -- Pitcher / pitch
  ge.pitcher_sfg_id,
  ge.pitcher_name,
  ge.pitch_type,

  -- Catcher
  ge.catcher_sfg_id,

  -- Runners
  ge.runner_on_first_base_sfg_id,
  ge.runner_on_second_base_sfg_id,
  ge.runner_on_third_base_sfg_id,

  -- Tracking
  met.tracking_stats_matched,
  met.catcher_pop_time,
  met.arm_strength,
  met.sprint_speed,

  -- TTP
  ttp.ttp,
  ttp.total_delivery_time,
  ge.pitch_zone_time,

  -- Catcher throwing
  cat.catching_sfg_id,
  cat.catcher_throwing_runs_plus_minus,

  -- Availability flags
  ttp.trackman_pitch_uid IS NOT NULL AS has_ttp_match,
  met.trackman_pitch_uid IS NOT NULL AS has_tracking_match

FROM
  sba

LEFT JOIN game_info ge
  USING (trackman_pitch_uid)

LEFT JOIN tracking_metrics met
  USING (trackman_pitch_uid)

LEFT JOIN ttp
  USING (trackman_pitch_uid)

LEFT JOIN catching cat
  USING (trackman_pitch_uid);