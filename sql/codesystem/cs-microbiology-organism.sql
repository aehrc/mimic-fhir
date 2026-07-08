-- Microbiology Organism CodeSystem


-- Author: John Grimes
DROP TABLE IF EXISTS fhir_trm.cs_microbiology_organism;
CREATE TABLE fhir_trm.cs_microbiology_organism(
    code      VARCHAR NOT NULL,
    display   VARCHAR NOT NULL
);

INSERT INTO fhir_trm.cs_microbiology_organism
SELECT
    org_itemid AS code
    , COALESCE(NULLIF(TRIM(MAX(org_name)), ''), org_itemid::text) AS display
FROM mimiciv_hosp.microbiologyevents m
WHERE org_itemid IS NOT NULL
GROUP BY org_itemid