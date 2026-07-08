-- Observation Category CodeSystem
-- Map values to http://hl7.org/fhir/valueset-observation-category.html

-- Author: John Grimes
DROP TABLE IF EXISTS fhir_trm.cs_observation_category;
CREATE TABLE fhir_trm.cs_observation_category(
    code      VARCHAR NOT NULL,
    display   VARCHAR NOT NULL
);

INSERT INTO fhir_trm.cs_observation_category
SELECT DISTINCT di.category AS code, di.category AS display
FROM mimiciv_icu.d_items di


