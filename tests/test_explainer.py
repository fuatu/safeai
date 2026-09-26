"""Tests for ExplainerEngine multilingual translations and alert generation."""

import pytest
from backend.explainer.engine import ExplainerEngine
from backend.security.engine import SecurityAssessment


@pytest.fixture
def explainer():
    return ExplainerEngine()


def test_explainer_english_safe_command(explainer):
    assessment = SecurityAssessment(risk_score=10, risk_factors=[])
    payload = {"command": "ls -la /tmp"}
    summary = explainer.generate_explanation("bash", payload, assessment, active_language="en")
    assert "Lists files and folders" in summary
    assert "WARNING" not in summary


def test_explainer_turkish_translation(explainer):
    assessment = SecurityAssessment(risk_score=10, risk_factors=[])
    payload = {"command": "pytest tests/"}
    summary_tr = explainer.generate_explanation("bash", payload, assessment, active_language="tr")
    assert "Otomatik test paketlerini çalıştırıyor." in summary_tr


def test_explainer_spanish_translation(explainer):
    assessment = SecurityAssessment(risk_score=10, risk_factors=[])
    payload = {"command": "git commit -m 'test'"}
    summary_es = explainer.generate_explanation("bash", payload, assessment, active_language="es")
    assert "Git" in summary_es
    assert "commit" in summary_es


def test_explainer_destructive_alert_localization(explainer):
    # Req 3.7: Highlight dangerous consequences using localized alert terminology
    assessment = SecurityAssessment(
        risk_score=85,
        risk_factors=["destructive_recursive_delete"],
        integrity_score=85,
    )
    payload = {"command": "rm -rf /var/log"}
    # English
    summary_en = explainer.generate_explanation("bash", payload, assessment, active_language="en")
    assert "WARNING: This action permanently alters or deletes files" in summary_en

    # Turkish
    summary_tr = explainer.generate_explanation("bash", payload, assessment, active_language="tr")
    assert "UYARI: Bu işlem sisteminizdeki dosya veya dizinleri kalıcı olarak siler" in summary_tr


def test_explainer_confidentiality_alert(explainer):
    assessment = SecurityAssessment(
        risk_score=80,
        risk_factors=["sensitive_path"],
        confidentiality_score=80,
    )
    payload = {"file_path": ".env"}
    summary = explainer.generate_explanation("view_file", payload, assessment, active_language="en")
    assert "Reads contents of .env." in summary
    assert "WARNING: This action accesses sensitive security credentials" in summary


def test_explainer_fallback_on_unsupported_language(explainer):
    # Req 3.3: Fallback to system locale or English when unsupported
    resolved = explainer.resolve_active_language("unknown_lang")
    assert resolved == "en"

    assessment = SecurityAssessment(risk_score=10, risk_factors=[])
    payload = {"command": "cargo build"}
    summary = explainer.generate_explanation("bash", payload, assessment, active_language="xyz")
    assert "Compiles or builds project assets." in summary


def test_explainer_configured_language_turkish(explainer):
    # Explicitly configured Turkish
    lang = explainer.resolve_active_language("tr")
    assert lang == "tr"

    assessment = SecurityAssessment(risk_score=10, risk_factors=[])
    payload = {"command": "ls -la"}
    summary = explainer.generate_explanation(
        "bash", payload, assessment, active_language="tr"
    )
    assert "dosya ve klasörleri" in summary


def test_explainer_configured_language_german(explainer):
    # Explicitly configured German
    lang = explainer.resolve_active_language("de")
    assert lang == "de"

    assessment = SecurityAssessment(risk_score=10, risk_factors=[])
    payload = {"command": "pytest"}
    summary = explainer.generate_explanation(
        "bash", payload, assessment, active_language="de"
    )
    assert "Führt automatisierte Testsuiten aus." in summary


def test_explainer_code_keywords_do_not_switch_language_to_spanish(explainer):
    # Code containing words like 'con' must NOT trigger Spanish when setting is English
    code_context = "import sqlite3; con = sqlite3.connect('/data/safeai.db')"
    lang = explainer.resolve_active_language("en", context_text=code_context)
    assert lang == "en"

    assessment = SecurityAssessment(risk_score=10, risk_factors=[])
    payload = {"command": code_context}
    summary = explainer.generate_explanation(
        "bash", payload, assessment, active_language="en", context_text=code_context
    )
    assert "Executes shell command" in summary
    assert "Ejecuta" not in summary


def test_explainer_fallback_strictly_to_configured_setting(explainer):
    explainer.default_language = "en"
    assert explainer.resolve_active_language("auto") == "en"
    assert explainer.resolve_active_language(None) == "en"
    assert explainer.resolve_active_language("") == "en"

