-- Microbiology Antibiotic Codesystem

DROP TABLE IF EXISTS fhir_trm.cs_microbiology_antibiotic;
CREATE TABLE fhir_trm.cs_microbiology_antibiotic(
    code      VARCHAR NOT NULL,
    display   VARCHAR NOT NULL
);

INSERT INTO fhir_trm.cs_microbiology_antibiotic
SELECT
    ab_itemid AS code
    , COALESCE(NULLIF(TRIM(MAX(ab_name)), ''), ab_itemid::text) AS display
FROM mimiciv_hosp.microbiologyevents m
WHERE ab_itemid IS NOT NULL
GROUP BY ab_itemid