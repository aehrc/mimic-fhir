-- Medication Method ICU CodeSystem
-- Could map to SNOMED codes - http://hl7.org/fhir/valueset-administration-method-codes.html

-- Author: John Grimes
DROP TABLE IF EXISTS fhir_trm.cs_medication_method_icu;
CREATE TABLE fhir_trm.cs_medication_method_icu(
    code      VARCHAR NOT NULL,
    display   VARCHAR NOT NULL
);

INSERT INTO fhir_trm.cs_medication_method_icu
SELECT DISTINCT TRIM(ordercategorydescription) AS code,
    TRIM(ordercategorydescription) AS display
FROM mimiciv_icu.inputevents;
