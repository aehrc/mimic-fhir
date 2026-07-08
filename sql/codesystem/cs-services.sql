-- Services CodeSystem
-- Codes will need to be mapped to service-type valueset: http://hl7.org/fhir/R4/valueset-service-type.html 

-- Author: John Grimes
DROP TABLE IF EXISTS fhir_trm.cs_services;
CREATE TABLE fhir_trm.cs_services(
    code      VARCHAR NOT NULL,
    display   VARCHAR NOT NULL
);

-- The documented service-name expansions from the MIMIC-IV hosp/services
-- documentation. Any service code not present in this map falls back to the
-- code.
WITH service_map (code, display) AS (
    VALUES
        ('CMED', 'Cardiac Medical'),
        ('CSURG', 'Cardiac Surgery'),
        ('DENT', 'Dental'),
        ('ENT', 'Ear, Nose, and Throat'),
        ('EYE', 'Eye'),
        ('GU', 'Genitourinary'),
        ('GYN', 'Gynecological'),
        ('MED', 'Medical'),
        ('NB', 'Newborn'),
        ('NBB', 'Newborn Baby'),
        ('NMED', 'Neurologic Medical'),
        ('NSURG', 'Neurologic Surgical'),
        ('OBS', 'Obstetrics'),
        ('OMED', 'Oncologic Medical'),
        ('ORTHO', 'Orthopaedic'),
        ('PSURG', 'Plastic'),
        ('PSYCH', 'Psychiatric'),
        ('SURG', 'Surgical'),
        ('TRAUM', 'Trauma'),
        ('TSURG', 'Thoracic Surgical'),
        ('VSURG', 'Vascular Surgical')
)
INSERT INTO fhir_trm.cs_services
SELECT
    s.curr_service AS code
    , COALESCE(m.display, s.curr_service) AS display
FROM (SELECT DISTINCT curr_service FROM mimiciv_hosp.services) s
LEFT JOIN service_map m ON m.code = s.curr_service;
