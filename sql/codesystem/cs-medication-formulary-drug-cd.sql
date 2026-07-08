-- Medication formulary drug codes CodeSystem
-- Codes will need to be mapped in future to a standard medication system (ie using rxnorm)

-- Author: John Grimes
DROP TABLE IF EXISTS fhir_trm.cs_medication_formulary_drug_cd;
CREATE TABLE fhir_trm.cs_medication_formulary_drug_cd(
    code      VARCHAR NOT NULL,
    display   VARCHAR NOT NULL
);

-- The product name lives alongside the code in the same source rows: the drug
-- in prescriptions and the product description in emar_detail. Take one per
-- code deterministically and fall back to the code where absent.
WITH formulary_drug_cd AS (
    SELECT DISTINCT formulary_drug_cd AS code, drug AS display FROM mimiciv_hosp.prescriptions p
    UNION
    SELECT DISTINCT product_code AS code, product_description AS display FROM mimiciv_hosp.emar_detail ed
)
INSERT INTO fhir_trm.cs_medication_formulary_drug_cd
SELECT
    code
    , COALESCE(NULLIF(TRIM(MAX(display)), ''), code) AS display
FROM formulary_drug_cd
WHERE
    code IS NOT NULL
    AND code != ''
GROUP BY code
