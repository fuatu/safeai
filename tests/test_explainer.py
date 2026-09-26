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


def test_explainer_conversational_auto_detect_turkish(explainer):
    # Context contains Turkish chat / prompt
    context = "Lütfen proje dosyalarını listele ve kontrol et"
    lang = explainer.resolve_active_language("auto", context_text=context)
    assert lang == "tr"

    assessment = SecurityAssessment(risk_score=10, risk_factors=[])
    payload = {"command": "ls -la"}
    summary = explainer.generate_explanation(
        "bash", payload, assessment, active_language="auto", context_text=context
    )
    assert "dosya ve klasörleri" in summary


def test_explainer_conversational_auto_detect_german(explainer):
    # Context contains German chat / prompt
    context = "Bitte führe die Tests für das Projekt aus und überprüfe alles"
    lang = explainer.resolve_active_language("auto", context_text=context)
    assert lang == "de"

    assessment = SecurityAssessment(risk_score=10, risk_factors=[])
    payload = {"command": "pytest"}
    summary = explainer.generate_explanation(
        "bash", payload, assessment, active_language="auto", context_text=context
    )
    assert "Führt automatisierte Testsuiten aus." in summary


def test_explainer_conversational_auto_detect_spanish(explainer):
    # Context contains Spanish chat / prompt
    context = "¿Por favor ejecuta las pruebas unitarias y crea un commit?"
    lang = explainer.resolve_active_language("auto", context_text=context)
    assert lang == "es"


def test_explainer_conversational_fallback_when_ambiguous(explainer):
    # Ambiguous or purely technical code without stop words / markers
    context = "ls -la /tmp"
    lang = explainer.resolve_active_language("auto", context_text=context)
    # Should fall back to host locale or 'en'
    assert lang in ["en", "tr", "de", "es", "fr"]

