INSERT INTO reference.diff_polygon_cluster (
    id,
    energy_sum,
    energy_distribution,
    cluster_area,
    geom
)
WITH threshold AS (
    SELECT
        percentile_cont(0.25) WITHIN GROUP (ORDER BY relevance_score) AS threshold_value
    FROM reference.diff_polygon
),

clustered AS (
    SELECT
        ST_ClusterDBSCAN(m.geom, eps := 0.25, minpoints := 1)
            OVER () AS cluster_id,
        m.geom,
        m.energy_sum
    FROM reference.diff_polygon AS m, threshold AS t
    WHERE m.relevance_score > t.threshold_value AND ST_Area(m.geom) > 50
),

cluster_union AS (
    SELECT
        cluster_id,
        ST_Union(geom) AS cluster_geom,
        SUM(COALESCE(energy_sum, 0)) AS energy_sum
    FROM clustered
    WHERE cluster_id IS NOT NULL
    GROUP BY cluster_id
),

hulls AS (
    SELECT
        c.cluster_id,
        c.energy_sum,
        ST_Area(c.cluster_geom) AS cluster_area,
        ST_ConvexHull(c.cluster_geom) AS geom
    FROM cluster_union AS c
    WHERE ST_Area(c.cluster_geom) >= 900
)

SELECT
    gen_random_uuid() AS id,
    energy_sum,
    (energy_sum * :pixel_area) / NULLIF(cluster_area, 0) AS energy_distribution,
    cluster_area,
    geom
FROM hulls;
