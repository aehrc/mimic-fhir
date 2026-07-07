-- Microbiology Test Codesystem

DROP TABLE IF EXISTS fhir_trm.cs_microbiology_test;
CREATE TABLE fhir_trm.cs_microbiology_test(
    code      VARCHAR NOT NULL,
    display   VARCHAR NOT NULL
);

INSERT INTO fhir_trm.cs_microbiology_test
SELECT
    test_itemid AS code
    , COALESCE(NULLIF(TRIM(MAX(test_name)), ''), test_itemid::text) AS display
FROM mimiciv_hosp.microbiologyevents m
WHERE test_itemid IS NOT NULL
GROUP BY test_itemid