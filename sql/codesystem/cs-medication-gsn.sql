-- Medication GSN CodeSystem (for MIMIC-ED)
-- Generic Sequence Number Codes will need to be mapped in future to a standard medication system (ie using rxnorm)
-- GSN codes pulled in from mimiciv_ed.medrecon mimiciv_ed.pyxis

DROP TABLE IF EXISTS fhir_trm.cs_medication_gsn;
CREATE TABLE fhir_trm.cs_medication_gsn(
    code      VARCHAR NOT NULL,
    display   VARCHAR NOT NULL
);

-- The medication name lives alongside the GSN in medrecon/pyxis; take one per
-- code deterministically and fall back to the code where absent.
WITH mimic_gsn AS (
    SELECT DISTINCT gsn, name FROM mimiciv_ed.medrecon
    UNION
    SELECT DISTINCT gsn, name FROM mimiciv_ed.pyxis
)
INSERT INTO fhir_trm.cs_medication_gsn
SELECT
    gsn AS code
    , COALESCE(NULLIF(TRIM(MAX(name)), ''), gsn) AS display
FROM mimic_gsn
WHERE
    gsn IS NOT NULL
    AND gsn != '0'
GROUP BY gsn
