-- Purpose: Generate a FHIR Observation resource from the labevents rows
-- Methods: uuid_generate_v5 --> requires uuid or text input, some inputs cast to text to fit

DROP TABLE IF EXISTS mimic_fhir.observation_labevents;
CREATE TABLE mimic_fhir.observation_labevents(
    id          uuid PRIMARY KEY,
    patient_id  uuid NOT NULL,
    fhir        jsonb NOT NULL 
);

WITH fhir_observation_labevents AS (
    SELECT
        CAST(lab.labevent_id AS TEXT) AS lab_LABEVENT_ID 
        , CAST(lab.itemid AS TEXT) AS lab_ITEMID
        , dlab.label AS dlab_LABEL
        , CAST(lab.charttime AS TIMESTAMPTZ) AS lab_CHARTTIME
        , CAST(lab.storetime AS TIMESTAMPTZ) AS lab_STORETIME
        , lab.flag AS lab_FLAG
        , lab.comments AS lab_COMMENTS
        , lab.ref_range_lower AS lab_REF_RANGE_LOWER
        , lab.ref_range_upper AS lab_REF_RANGE_UPPER
        , CASE WHEN lab.valueuom != ' ' THEN
            lab.valueuom 
        ELSE NULL END AS lab_VALUEUOM
        , lab.value AS lab_VALUE
        , lab.priority AS lab_PRIORITY
  
        -- Parse values with a comparator and pulling out numeric value
        , CASE 
            WHEN lab.valuenum IS NOT NULL THEN lab.valuenum
            WHEN value LIKE '%<=%' THEN CAST(split_part(lab.value,'<=',2) AS NUMERIC)
            WHEN value LIKE '%<%' THEN CAST(split_part(lab.value,'<',2) AS NUMERIC)
            WHEN value LIKE '%>=%' THEN CAST(split_part(lab.value,'>=',2) AS NUMERIC)
            WHEN value LIKE '%>%' THEN CAST(split_part(lab.value,'>',2) AS NUMERIC)
            ELSE NULL
        END as lab_VALUENUM
        , CASE 
            WHEN value LIKE '%<=%' THEN '<='
            WHEN value LIKE '%<%' THEN '<'
            WHEN value LIKE '%>=%' THEN '>='
            WHEN value LIKE '%>%' THEN '>'
            WHEN value LIKE '%GREATER THAN%' THEN '>'
            WHEN value LIKE '%LESS THAN%' THEN '<'
            ELSE NULL
        END as VALUE_COMPARATOR  
        
        -- Get lab status from comments (error, corrected, cancelled)
        , CASE 
            WHEN comments ILIKE '%error%' THEN 'entered-in-error'
            WHEN comments ILIKE '%corrected%' THEN 'corrected'
            WHEN comments ILIKE '%cancel%' THEN 'cancelled'
            ELSE 'final'
        END AS lab_STATUS
  
        -- reference uuids
        , uuid_generate_v5(ns_observation_labs.uuid, CAST(lab.labevent_id AS TEXT)) AS uuid_LABEVENT_ID
        , uuid_generate_v5(ns_patient.uuid, CAST(lab.subject_id AS TEXT)) AS uuid_SUBJECT_ID
        , uuid_generate_v5(ns_encounter.uuid, CAST(lab.hadm_id AS TEXT)) AS uuid_HADM_ID
        , uuid_generate_v5(ns_specimen.uuid, CAST(lab.specimen_id AS TEXT)) AS uuid_SPECIMEN_ID
    FROM
        mimic_hosp.labevents lab
        INNER JOIN fhir_etl.subjects sub
            ON lab.subject_id =sub.subject_id 
        LEFT JOIN mimic_hosp.d_labitems dlab
            ON lab.itemid = dlab.itemid                             
        LEFT JOIN fhir_etl.uuid_namespace ns_encounter
            ON ns_encounter.name = 'Encounter'
        LEFT JOIN fhir_etl.uuid_namespace ns_patient
            ON ns_patient.name = 'Patient'
        LEFT JOIN fhir_etl.uuid_namespace ns_observation_labs
            ON ns_observation_labs.name = 'ObservationLabs'
        LEFT JOIN fhir_etl.uuid_namespace ns_specimen
            ON ns_specimen.name = 'SpecimenLab'
)
INSERT INTO mimic_fhir.observation_labevents
SELECT 
    uuid_LABEVENT_ID as id
    , uuid_SUBJECT_ID AS patient_id 
    , jsonb_strip_nulls(jsonb_build_object(
        'resourceType', 'Observation'
        , 'id', uuid_LABEVENT_ID
        , 'meta', jsonb_build_object(
            'profile', jsonb_build_array(
                'http://fhir.mimic.mit.edu/StructureDefinition/mimic-observation-labevents'
            )
        ) 
        , 'identifier', jsonb_build_array(jsonb_build_object(
            'value', lab_LABEVENT_ID
            , 'system', 'http://fhir.mimic.mit.edu//identifier/observation-labevents'
        ))       
        , 'status', lab_STATUS
        , 'category', jsonb_build_array(jsonb_build_object(
            'coding', jsonb_build_array(jsonb_build_object(
                'system', 'http://terminology.hl7.org/CodeSystem/observation-category'  
                , 'code', 'laboratory'
            ))
        ))
          
        -- Lab test completed  
        , 'code', jsonb_build_object(
            'coding', jsonb_build_array(jsonb_build_object(
                'system', 'http://fhir.mimic.mit.edu/CodeSystem/d-labitems'  
                , 'code', lab_ITEMID
                , 'display', dlab_LABEL
            ))
        )
        , 'subject', jsonb_build_object('reference', 'Patient/' || uuid_SUBJECT_ID)
        , 'encounter', 
            CASE WHEN uuid_HADM_ID IS NOT NULL
                THEN jsonb_build_object('reference', 'Encounter/' || uuid_HADM_ID) 
            ELSE NULL END
        , 'effectiveDateTime', lab_CHARTTIME
        , 'issued', lab_STORETIME
        , 'valueQuantity', 
            CASE WHEN lab_VALUENUM IS NOT NULL THEN
                jsonb_build_object(
                    'value', lab_VALUENUM
                    , 'unit', lab_VALUEUOM
                    , 'system', 'http://fhir.mimic.mit.edu/CodeSystem/units'
                    , 'code', lab_VALUEUOM 
                    , 'comparator', VALUE_COMPARATOR
                ) 
            ELSE NULL END
        , 'valueString', 
            CASE WHEN lab_VALUENUM IS NULL THEN lab_VALUE    
            ELSE NULL END      
        , 'interpretation', 
            CASE WHEN lab_FLAG IS NOT NULL THEN
                jsonb_build_array(jsonb_build_object(
                    'coding', jsonb_build_array(jsonb_build_object(
                        'system', 'http://fhir.mimic.mit.edu/CodeSystem/lab-flags'  
                        , 'code', lab_FLAG
                    ))
                ))
            ELSE NULL END
            
        -- Add clinical notes    
        , 'note', 
            CASE WHEN lab_COMMENTS IS NOT NULL THEN
                jsonb_build_array(jsonb_build_object(
                    'text', lab_COMMENTS
                ))
            ELSE NULL END
        , 'specimen', jsonb_build_object('reference', 'Specimen/' || uuid_SPECIMEN_ID) 
        , 'referenceRange', 
            CASE WHEN (lab_REF_RANGE_LOWER IS NOT NULL) OR (lab_REF_RANGE_UPPER IS NOT NULL) THEN   
                jsonb_build_array(jsonb_build_object(
                    'low', CASE WHEN lab_REF_RANGE_LOWER IS NOT NULL THEN 
                        jsonb_strip_nulls(jsonb_build_object(
                            'value', lab_REF_RANGE_LOWER
                            , 'unit', lab_VALUEUOM
                            , 'system', 'http://fhir.mimic.mit.edu/CodeSystem/units'
                            , 'code', lab_VALUEUOM
                        ))
                    ELSE NULL END
                    , 'high', CASE WHEN lab_REF_RANGE_UPPER IS NOT NULL THEN 
                        jsonb_strip_nulls(jsonb_build_object(
                            'value', lab_REF_RANGE_UPPER
                            , 'unit', lab_VALUEUOM
                            , 'system', 'http://fhir.mimic.mit.edu/CodeSystem/units'
                            , 'code', lab_VALUEUOM
                        ))
                    ELSE NULL END
                ))
            ELSE NULL END
        , 'extension', 
            CASE WHEN lab_PRIORITY IS NOT NULL THEN
                jsonb_build_array(jsonb_build_object(
                    'url', 'http://fhir.mimic.mit.edu/StructureDefinition/lab-priority'
                    , 'valueString', lab_PRIORITY
                ))
            ELSE NULL END
    )) as fhir 
FROM
    fhir_observation_labevents;