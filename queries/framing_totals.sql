select
    player_code,
    year,
    sum(plus_minus),
    sum(framing_chances)
from
    `sfgiants-viewer.scout_replica_scouting.tblStats_Catching_Framing`
where
    year >= 2026
group by
    year,
    player_code