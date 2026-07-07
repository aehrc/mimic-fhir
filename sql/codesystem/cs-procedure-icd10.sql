-- Generate codes for procedure-icd10 codesystem
-- Only taking the codes used in procedure_icd versus all the codes in d_icd_procedures 
-- Need to trim to remove whitespaces, or validator will fail it


DROP TABLE IF EXISTS fhir_trm.cs_procedure_icd10;
CREATE TABLE fhir_trm.cs_procedure_icd10(
    code      VARCHAR NOT NULL,
    display   VARCHAR NOT NULL
);

INSERT INTO fhir_trm.cs_procedure_icd10
SELECT
    TRIM(proc.icd_code) AS code
    -- Fall back to the code where the ICD dictionary has no title, and group to
    -- one row per code where a title differs slightly across sources.
    , COALESCE(NULLIF(TRIM(MAX(icd.long_title)), ''), TRIM(proc.icd_code)) AS display
FROM
    mimiciv_hosp.procedures_icd proc
    LEFT JOIN mimiciv_hosp.d_icd_procedures icd
        ON proc.icd_code = icd.icd_code
        AND proc.icd_version = icd.icd_version
WHERE proc.icd_version = 10
GROUP BY TRIM(proc.icd_code)

