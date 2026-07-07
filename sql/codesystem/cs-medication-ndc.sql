-- Medication NDC CodeSystem
-- National Drug Codes will need to be mapped in future to a standard medication system (ie using rxnorm)

DROP TABLE IF EXISTS fhir_trm.cs_medication_ndc;
CREATE TABLE fhir_trm.cs_medication_ndc(
    code      VARCHAR NOT NULL,
    display   VARCHAR NOT NULL
);

-- The drug name lives alongside the NDC in the same prescriptions rows; take
-- one per code deterministically and fall back to the code where absent.
INSERT INTO fhir_trm.cs_medication_ndc
SELECT
    ndc AS code
    , COALESCE(NULLIF(TRIM(MAX(drug)), ''), ndc) AS display
FROM mimiciv_hosp.prescriptions
WHERE
    ndc IS NOT NULL
    AND ndc != ''
GROUP BY ndc;
