import json
import requests
import logging
import os
import subprocess
import pytest
import time
import pandas as pd

from py_mimic_fhir.terminology import TerminologyMetaData
import py_mimic_fhir.terminology as trm

from fhir.resources.codesystem import CodeSystem, CodeSystemConcept
from fhir.resources.valueset import ValueSet

from py_mimic_fhir.lookup import (MIMIC_CODESYSTEMS, MIMIC_VALUESETS)


def test_terminology_meta_data(db_conn):
    meta = TerminologyMetaData(db_conn)
    logging.error(meta)
    assert meta.language == 'en'


def test_codesystem_descriptions(db_conn, meta):
    description = meta.cs_descriptions[meta.cs_descriptions['codesystem'] ==
                                       'lab_flags']['description'].iloc[0]
    assert description == 'The lab alarm flags for abnormal lab events in MIMIC'


def test_valueset_descriptions(db_conn, meta):
    description = meta.vs_descriptions[meta.vs_descriptions['valueset'] ==
                                       'lab_flags']['description'].iloc[0]
    assert description == 'The lab alarm flags for abnormal lab events in MIMIC'


def test_db_get_table(db_conn):
    df_table = db_conn.get_table('fhir_trm', 'cs_lab_flags')
    print(df_table)


def test_generate_codesystem(db_conn, meta):
    mimic_codesystem = 'lab_flags'
    codesystem = trm.generate_codesystem(mimic_codesystem, db_conn, meta)
    assert codesystem.resource_type == 'CodeSystem'


def test_generate_valueset(db_conn, meta):
    mimic_valueset = 'lab_flags'
    valueset = trm.generate_valueset(mimic_valueset, db_conn, meta)
    assert valueset.resource_type == 'ValueSet'


# Check that the valueset coded generates without errors, not checking contents
def test_generate_valueset_coded(db_conn, meta):
    mimic_valueset = 'chartevents_d_items'
    valueset = trm.generate_valueset(mimic_valueset, db_conn, meta)
    logging.error(valueset.compose)
    assert valueset.resource_type == 'ValueSet'


# Check that the valueset double system generates without errors, not checking contents
def test_generate_valueset_double_system(db_conn, meta):
    mimic_valueset = 'procedure_icd'
    valueset = trm.generate_valueset(mimic_valueset, db_conn, meta)
    logging.error(valueset)
    assert valueset.resource_type == 'ValueSet'


def test_write_codeystem(example_codesystem, terminology_path):
    current_time = time.localtime()
    trm.write_terminology(example_codesystem, terminology_path)

    # Confirm the file has been updated
    output_filepath = f'{terminology_path}{example_codesystem.resource_type}-{example_codesystem.id}.json'
    modified_time_unstructured = os.path.getmtime(output_filepath)
    modified_time = time.localtime(modified_time_unstructured)
    assert current_time == modified_time


def test_write_valueset(example_valueset, terminology_path):
    current_time = time.localtime()
    trm.write_terminology(example_valueset, terminology_path)

    # Confirm the file has been updated
    output_filepath = f'{terminology_path}{example_valueset.resource_type}-{example_valueset.id}.json'
    modified_time_unstructured = os.path.getmtime(output_filepath)
    modified_time = time.localtime(modified_time_unstructured)
    assert current_time == modified_time


def test_generate_all_codesystems(db_conn, meta, terminology_path):
    trm.generate_codesystems(db_conn, meta, terminology_path)
    assert True


def test_generate_all_valuesets(db_conn, meta, terminology_path):
    trm.generate_valuesets(db_conn, meta, terminology_path)
    assert True


#----------------------------------------------------------------
#--------------- COMPLETE DISPLAY TERMS FEATURE -----------------
#----------------------------------------------------------------

# The three code systems below have SQL scripts, description rows, committed
# resources, and validation tests, but were dropped from the batch generation
# list in a past refactor. They must be restored to MIMIC_CODESYSTEMS so that
# "all code systems" genuinely covers all 39, and so the batch generator emits
# them again (FR-012).
DROPPED_CODESYSTEMS = [
    'identifier_type', 'lab_flags', 'microbiology_interpretation'
]


@pytest.mark.parametrize('codesystem', DROPPED_CODESYSTEMS)
def test_dropped_codesystem_in_generation_list(codesystem):
    # Regression guard: each restored code system must be present in the batch
    # generation list.
    assert codesystem in MIMIC_CODESYSTEMS


@pytest.mark.parametrize('codesystem', DROPPED_CODESYSTEMS)
def test_dropped_codesystem_generates(db_conn, meta, codesystem):
    # Each restored code system must generate a valid CodeSystem resource.
    generated = trm.generate_codesystem(codesystem, db_conn, meta)
    assert generated.resource_type == 'CodeSystem'


# Helpers shared by the display-completeness and enrichment tests. The generator
# builds each concept as a plain dict; support attribute access too in case a
# future fhir.resources version coerces them into CodeSystemConcept objects.
def _concept_field(concept, field):
    if isinstance(concept, dict):
        return concept.get(field)
    return getattr(concept, field, None)


def _concepts(generated):
    return generated.concept or []


def _find_concept(generated, code):
    for concept in _concepts(generated):
        if _concept_field(concept, 'code') == code:
            return concept
    return None


# Systems whose richer display source was delivered incrementally across the
# user stories (US2 medication names, US3 documented expansions). All are now
# complete, so the completeness invariant below holds for every code system and
# this set is empty. A non-empty entry marks a system as a strict xfail so it
# cannot silently regress or be left incomplete.
PENDING_DISPLAY_SYSTEMS = {}


def _completeness_params():
    # Parametrise the completeness invariant over every code system, marking the
    # systems whose display source is not yet delivered as strict xfails.
    params = []
    for codesystem in MIMIC_CODESYSTEMS:
        if codesystem in PENDING_DISPLAY_SYSTEMS:
            params.append(
                pytest.param(
                    codesystem,
                    marks=pytest.mark.xfail(
                        reason=
                        f'display source pending: {PENDING_DISPLAY_SYSTEMS[codesystem]}',
                        strict=True
                    )
                )
            )
        else:
            params.append(codesystem)
    return params


@pytest.mark.parametrize('codesystem', _completeness_params())
def test_codesystem_display_completeness(db_conn, meta, codesystem):
    # FR-001 / SC-001 / contract G-B1-B2: every concept in every generated
    # CodeSystem must carry a present, non-empty (non-whitespace) display.
    # Contract G-A3: each code appears exactly once within the system.
    generated = trm.generate_codesystem(codesystem, db_conn, meta)
    codes = []
    for concept in _concepts(generated):
        code = _concept_field(concept, 'code')
        display = _concept_field(concept, 'display')
        assert display is not None and str(display).strip() != '', (
            f'{codesystem}: code {code!r} has a missing or empty display'
        )
        codes.append(code)
    assert len(codes) == len(set(codes)), (
        f'{codesystem}: duplicate codes present'
    )


def test_generate_concept_emits_display_when_equal_to_code():
    # Guards the display=code case at the generator level: a staging row whose
    # display equals its code must still emit a display, not drop it.
    df = pd.DataFrame(
        [
            {
                'code': 'ART',
                'display': 'Arterial'
            },  # a genuine descriptive display
            {
                'code': 'PO',
                'display': 'PO'
            },  # display equals code (self-text)
        ]
    )
    concept = trm.generate_concept(df)
    assert concept[0]['display'] == 'Arterial'
    assert concept[1]['display'] == 'PO'


def test_present_group_preserves_source_display(db_conn, meta):
    # No-regression guard (FR-011): the "present" group must keep its
    # source-provided display (label / long title), not collapse to display=code.
    for codesystem, table in [('d_items', 'cs_d_items'),
                              ('diagnosis_icd10', 'cs_diagnosis_icd10')]:
        df = db_conn.get_table('fhir_trm', table)
        # A row whose display genuinely differs from its code proves the source
        # descriptive term is carried through rather than the code repeated.
        descriptive = df[df['display'].notna() & (df['display'] != df['code'])]
        assert not descriptive.empty, (
            f'{table}: expected at least one row with a descriptive display'
        )
        sample = descriptive.iloc[0]
        generated = trm.generate_codesystem(codesystem, db_conn, meta)
        concept = _find_concept(generated, sample['code'])
        assert concept is not None, (
            f'{codesystem}: code {sample["code"]!r} missing from generated system'
        )
        assert _concept_field(concept, 'display') == sample['display']


# ---- User Story 2: meaningful names for opaque medication codes ----


def _names_by_code(df):
    # Collapse a (code, name) frame into {code: {names}}, the set of candidate
    # source display strings for each code.
    return df.groupby('code')['name'].apply(set).to_dict()


def test_medication_ndc_display_is_source_drug_name(db_conn, meta):
    # SC-002 / FR-004: every NDC whose prescriptions rows carry a drug name shows
    # one of those names as its display, never the opaque code repeated.
    src = db_conn.read_query(
        """
        SELECT ndc AS code, TRIM(drug) AS name
        FROM mimiciv_hosp.prescriptions
        WHERE ndc IS NOT NULL AND ndc != ''
          AND NULLIF(TRIM(drug), '') IS NOT NULL
        """
    )
    names_by_code = _names_by_code(src)
    generated = trm.generate_codesystem('medication_ndc', db_conn, meta)
    checked = 0
    for concept in _concepts(generated):
        code = _concept_field(concept, 'code')
        if code not in names_by_code:
            continue
        display = _concept_field(concept, 'display')
        assert display in names_by_code[code], (
            f'ndc {code}: display {display!r} is not a source drug name'
        )
        assert display != code
        checked += 1
    assert checked > 0, 'the demo must exercise at least one enriched NDC'


def test_medication_gsn_display_is_source_name(db_conn, meta):
    # SC-002 / FR-004: every GSN present in medrecon/pyxis with a name shows one
    # of those names as its display.
    src = db_conn.read_query(
        """
        SELECT gsn AS code, TRIM(name) AS name
        FROM (
            SELECT gsn, name FROM mimiciv_ed.medrecon
            UNION ALL
            SELECT gsn, name FROM mimiciv_ed.pyxis
        ) g
        WHERE gsn IS NOT NULL AND gsn != '0'
          AND NULLIF(TRIM(name), '') IS NOT NULL
        """
    )
    names_by_code = _names_by_code(src)
    generated = trm.generate_codesystem('medication_gsn', db_conn, meta)
    checked = 0
    for concept in _concepts(generated):
        code = _concept_field(concept, 'code')
        if code not in names_by_code:
            continue
        display = _concept_field(concept, 'display')
        assert display in names_by_code[code], (
            f'gsn {code}: display {display!r} is not a source name'
        )
        assert display != code
        checked += 1
    assert checked > 0, 'the demo must exercise at least one enriched GSN'


def test_medication_formulary_drug_cd_display_from_both_sources(db_conn, meta):
    # SC-002 / FR-004: formulary_drug_cd codes take the drug name from
    # prescriptions and the product_description from emar_detail; a code with a
    # source name shows it rather than the opaque code. Both source columns must
    # actually be exercised.
    presc = _names_by_code(
        db_conn.read_query(
            """
            SELECT formulary_drug_cd AS code, TRIM(drug) AS name
            FROM mimiciv_hosp.prescriptions
            WHERE formulary_drug_cd IS NOT NULL AND formulary_drug_cd != ''
              AND NULLIF(TRIM(drug), '') IS NOT NULL
            """
        )
    )
    emar = _names_by_code(
        db_conn.read_query(
            """
            SELECT product_code AS code, TRIM(product_description) AS name
            FROM mimiciv_hosp.emar_detail
            WHERE product_code IS NOT NULL AND product_code != ''
              AND NULLIF(TRIM(product_description), '') IS NOT NULL
            """
        )
    )
    all_names = {}
    for source in (presc, emar):
        for code, names in source.items():
            all_names.setdefault(code, set()).update(names)

    generated = trm.generate_codesystem(
        'medication_formulary_drug_cd', db_conn, meta
    )
    presc_only = emar_only = 0
    for concept in _concepts(generated):
        code = _concept_field(concept, 'code')
        if code not in all_names:
            continue
        display = _concept_field(concept, 'display')
        assert display in all_names[code], (
            f'formulary code {code}: display {display!r} is not a source name'
        )
        assert display != code
        if code in presc and code not in emar:
            presc_only += 1
        if code in emar and code not in presc:
            emar_only += 1
    # Confirm each source column is genuinely surfaced by an isolated code.
    assert presc_only > 0, 'a prescriptions.drug name must be surfaced'
    assert emar_only > 0, 'an emar_detail.product_description must be surfaced'


# ---- User Story 3: documented expansions for coded abbreviations ----

# The MIMIC-IV documented service-name expansions (hosp/services). Held here so
# the test and the SQL map are checked against the same authoritative source.
DOCUMENTED_SERVICES = {
    'CMED': 'Cardiac Medical',
    'CSURG': 'Cardiac Surgery',
    'DENT': 'Dental',
    'ENT': 'Ear, Nose, and Throat',
    'EYE': 'Eye',
    'GU': 'Genitourinary',
    'GYN': 'Gynecological',
    'MED': 'Medical',
    'NB': 'Newborn',
    'NBB': 'Newborn Baby',
    'NMED': 'Neurologic Medical',
    'NSURG': 'Neurologic Surgical',
    'OBS': 'Obstetrics',
    'OMED': 'Oncologic Medical',
    'ORTHO': 'Orthopaedic',
    'PSURG': 'Plastic',
    'PSYCH': 'Psychiatric',
    'SURG': 'Surgical',
    'TRAUM': 'Trauma',
    'TSURG': 'Thoracic Surgical',
    'VSURG': 'Vascular Surgical',
}

# The MIMIC-IV documented antibiotic-sensitivity interpretation codes.
DOCUMENTED_INTERPRETATIONS = {
    'S': 'Sensitive',
    'R': 'Resistant',
    'I': 'Intermediate',
    'P': 'Pending',
}


def _concept_map(generated):
    return {
        _concept_field(c, 'code'): _concept_field(c, 'display')
        for c in _concepts(generated)
    }


def test_services_documented_expansions(db_conn, meta):
    # SC-003 / FR-005: documented service codes show their documented expansion;
    # a code absent from the map falls back to the code.
    concepts = _concept_map(trm.generate_codesystem('services', db_conn, meta))
    # Headline examples from the spec.
    assert concepts.get('CMED') == 'Cardiac Medical'
    assert concepts.get('TRAUM') == 'Trauma'
    for code, display in concepts.items():
        if code in DOCUMENTED_SERVICES:
            assert display == DOCUMENTED_SERVICES[code], (
                f'service {code}: display {display!r} != '
                f'documented {DOCUMENTED_SERVICES[code]!r}'
            )
        else:
            # A service code not in the documented map falls back to the code.
            assert display == code


def test_microbiology_interpretation_documented_expansions(db_conn, meta):
    # SC-003 / FR-005: documented interpretation codes show their expansion; a
    # code absent from the map falls back to the code.
    concepts = _concept_map(
        trm.generate_codesystem('microbiology_interpretation', db_conn, meta)
    )
    # S/R/I are present in the demo (P is documented but absent from the demo).
    assert concepts.get('S') == 'Sensitive'
    assert concepts.get('R') == 'Resistant'
    assert concepts.get('I') == 'Intermediate'
    for code, display in concepts.items():
        if code in DOCUMENTED_INTERPRETATIONS:
            assert display == DOCUMENTED_INTERPRETATIONS[code]
        else:
            assert display == code
