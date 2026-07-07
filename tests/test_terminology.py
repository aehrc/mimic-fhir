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


# Systems whose richer display source is delivered by a later user story: the
# medication codes gain adjacent drug/product names in US2, and the coded
# abbreviations gain documented expansions in US3. Until their story lands they
# emit code-only, so the completeness invariant is expected to fail for them.
# Each entry is removed as its owning story is implemented, and the strict xfail
# guarantees the entry cannot be left behind once the system is complete.
PENDING_DISPLAY_SYSTEMS = {
    'medication_ndc': 'US2 adjacent drug name',
    'medication_gsn': 'US2 adjacent name',
    'medication_formulary_drug_cd': 'US2 adjacent product name',
    'services': 'US3 documented service map',
    'microbiology_interpretation': 'US3 documented S/R/I/P map',
}


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
