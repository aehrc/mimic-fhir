-- Microbiology Interpretation Codesystem

-- Author: John Grimes
DROP TABLE IF EXISTS fhir_trm.cs_microbiology_interpretation;
CREATE TABLE fhir_trm.cs_microbiology_interpretation(
    code      VARCHAR NOT NULL,
    display   VARCHAR NOT NULL
);

-- The documented antibiotic-sensitivity interpretation codes from the MIMIC-IV
-- hosp/microbiologyevents documentation. Any code not present in this map falls
-- back to the code.
WITH interpretation_map (code, display) AS (
    VALUES
        ('S', 'Sensitive'),
        ('R', 'Resistant'),
        ('I', 'Intermediate'),
        ('P', 'Pending')
)
INSERT INTO fhir_trm.cs_microbiology_interpretation
SELECT
    i.interpretation AS code
    , COALESCE(m.display, i.interpretation) AS display
FROM (
    SELECT DISTINCT interpretation
    FROM mimiciv_hosp.microbiologyevents
    WHERE interpretation IS NOT NULL
) i
LEFT JOIN interpretation_map m ON m.code = i.interpretation;