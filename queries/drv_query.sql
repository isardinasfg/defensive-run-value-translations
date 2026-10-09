WITH player_tracking AS (
  SELECT
    s.player_code,
    s.year,
    ROUND(
      AVG(
        CASE
          WHEN s.stat_type_id = 3 THEN s.value
        END
      ),
      1
    ) AS arm,
    ROUND(
      AVG(
        CASE
          WHEN s.stat_type_id = 28 THEN s.value
        END
      ),
      2
    ) AS pop_time,
    ROUND(
      AVG(
        CASE
          WHEN s.stat_type_id = 74 THEN s.value
        END
      ),
      1
    ) AS sprint_speed
  FROM
    `prod-warehouse-sfgiants-onprem.scout_replica_scouting.tblStats_StatCast_Avgs` s
  WHERE
    s.year BETWEEN 2022
    AND 2026
    AND s.stat_type_id IN (3, 28, 74)
  GROUP BY
    s.player_code,
    s.year
)
SELECT
  rv.year,
  rv.player_code,
  CONCAT(map.last_name, ', ', map.first_name) AS player_name,
  rv.age,
  rv.level,
  ROUND(fielding.sfg.run_value_fielder, 1) AS sfg_drv,
  ROUND(fielding.zelus.run_value_fielder, 1) AS zelus_drv,
  ROUND(
    COALESCE(fielding.average.innings_catcher, 0) + COALESCE(fielding.average.innings_first_baseman, 0) + COALESCE(fielding.average.innings_second_baseman, 0) + COALESCE(fielding.average.innings_shortstop, 0) + COALESCE(fielding.average.innings_third_baseman, 0) + COALESCE(fielding.average.innings_left_fielder, 0) + COALESCE(fielding.average.innings_center_fielder, 0) + COALESCE(fielding.average.innings_right_fielder, 0),
    1
  ) AS total_innings,
  fielding.position_one.abbreviation AS position_one,
  fielding.position_two.abbreviation AS position_two,
  fielding.position_three.abbreviation AS position_three,
  tracking.arm,
  tracking.pop_time,
  tracking.sprint_speed
FROM
  `prod-warehouse-sfgiants.run_values_by_level_and_year.pro` rv
  LEFT JOIN `sfgiants-viewer.scout_replica_scouting.tblPlayer_Pro` map ON map.player_code = rv.player_code
  LEFT JOIN player_tracking tracking ON tracking.player_code = rv.player_code
  AND tracking.year = rv.year
WHERE
  rv.year > 2021
  AND rv.level IN ('rok', 'afx', 'afa', 'aax', 'aaa', 'mlb')
ORDER BY
  rv.year;