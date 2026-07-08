-- Medication Site Codesystem
-- Need to map out to SNOMED route codes - http://hl7.org/fhir/valueset-route-codes.html

-- Author: John Grimes
DROP TABLE IF EXISTS fhir_trm.cs_medication_site;
CREATE TABLE fhir_trm.cs_medication_site(
    code      VARCHAR NOT NULL,
    display   VARCHAR NOT NULL
);

INSERT INTO fhir_trm.cs_medication_site
-- Need TO remove ALL whitespaces TO pass fhir validation.
SELECT DISTINCT TRIM(REGEXP_REPLACE(site, '\s+', ' ', 'g')) AS code,
    TRIM(REGEXP_REPLACE(site, '\s+', ' ', 'g')) AS display
FROM mimiciv_hosp.emar_detail
WHERE 
    site IS NOT NULL 
    AND TRIM(REGEXP_REPLACE(site, '\s+', ' ', 'g')) != ''