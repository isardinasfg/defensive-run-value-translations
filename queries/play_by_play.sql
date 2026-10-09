SELECT
    rv.*,
    ge.game_date,
    CONCAT(map.last_name, ', ', map.first_name) AS player_name
FROM
    `sfgiants-viewer.analyst_isardina.pbp_dfrv` rv
    LEFT JOIN (
        SELECT
            game_pk,
            MAX(game_date) AS game_date
        FROM
            `sfgiants-viewer.game_event.pro`
        GROUP BY
            game_pk
    ) ge ON ge.game_pk = rv.game_pk
    LEFT JOIN `sfgiants-viewer.scout_replica_scouting.tblPlayer_Pro` map ON map.player_code = rv.player_code