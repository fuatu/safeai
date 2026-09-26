"""Multilingual plain-language 'For Dummies' explainer engine."""

import locale
import os
import re
from typing import Any, Dict, List, Optional

from backend.security.engine import SecurityAssessment


class ExplainerEngine:
    """
    Converts raw technical tool executions and AST security assessments
    into concise, 1-2 sentence human-understandable summaries in the user's active language.
    """

    SUPPORTED_LANGUAGES = {"en", "tr", "es", "de", "fr"}
    DEFAULT_LANGUAGE = "en"

    # Localized danger alerts for high-risk threat categories
    ALERT_TERMS: Dict[str, Dict[str, str]] = {
        "destructive": {
            "en": "WARNING: This action permanently alters or deletes files and directories on your system.",
            "tr": "UYARI: Bu işlem sisteminizdeki dosya veya dizinleri kalıcı olarak siler veya değiştirir.",
            "es": "ADVERTENCIA: Esta acción modifica o elimina permanentemente archivos y carpetas del sistema.",
            "de": "WARNUNG: Diese Aktion ändert oder löscht Dateien und Verzeichnisse auf Ihrem System dauerhaft.",
            "fr": "ATTENTION: Cette action modifie ou supprime définitivement des fichiers et répertoires système.",
        },
        "confidentiality": {
            "en": "WARNING: This action accesses sensitive security credentials, private keys, or secret files.",
            "tr": "UYARI: Bu işlem hassas kimlik bilgilerine, gizli anahtarlara veya parola dosyalarına erişir.",
            "es": "ADVERTENCIA: Esta acción accede a credenciales confidenciales, claves privadas o secretos.",
            "de": "WARNUNG: Diese Aktion greift auf vertrauliche Anmeldedaten, private Schlüssel oder Passwörter zu.",
            "fr": "ATTENTION: Cette action accède à des identifiants confidentiels, clés privées ou secrets.",
        },
        "exfiltration": {
            "en": "WARNING: This action attempts to send local machine data to an external network endpoint.",
            "tr": "UYARI: Bu işlem yerel bilgisayar verilerinizi harici bir internet adresine sızdırmaya çalışır.",
            "es": "ADVERTENCIA: Esta acción intenta transmitir datos locales a un servidor o red externa.",
            "de": "WARNUNG: Diese Aktion versucht, lokale Daten an einen externen Netzwerkendpunkt zu übertragen.",
            "fr": "ATTENTION: Cette action tente d'envoyer des données locales vers un réseau externe.",
        },
        "injection": {
            "en": "WARNING: Detected prompt injection or instruction override sequences intended to bypass safety boundaries.",
            "tr": "UYARI: Güvenlik sınırlarını aşmayı amaçlayan yönlendirme manipülasyonu veya talimat geçersiz kılma tespit edildi.",
            "es": "ADVERTENCIA: Se detectó una inyección de instrucciones para eludir las restricciones de seguridad.",
            "de": "WARNUNG: Prompt-Injection oder Manipulationsanweisungen zur Umgehung von Sicherheitsregeln erkannt.",
            "fr": "ATTENTION: Injection d'instructions détectée visant à contourner les règles de sécurité.",
        },
        "unparseable": {
            "en": "WARNING: The command uses obfuscation or unparseable encoding and cannot be verified automatically.",
            "tr": "UYARI: Komut gizleme (obfuscation) veya ayrıştırılamayan kodlama içerdiğinden otomatik doğrulanamıyor.",
            "es": "ADVERTENCIA: El comando utiliza ofuscación o codificación no analizable y no puede verificarse automáticamente.",
            "de": "WARNUNG: Der Befehl verwendet Verschleierung oder Kodierung und kann nicht automatisch überprüft werden.",
            "fr": "ATTENTION: La commande utilise une obfuscation ou un encodage non analysable.",
        },
    }

    # Action description templates by tool
    TOOL_TEMPLATES: Dict[str, Dict[str, str]] = {
        "read": {
            "en": "Reads contents of {target}.",
            "tr": "{target} içeriğini görüntülüyor.",
            "es": "Lee el contenido de {target}.",
            "de": "Liest den Inhalt von {target}.",
            "fr": "Lit le contenu de {target}.",
        },
        "write": {
            "en": "Writes or updates file {target}.",
            "tr": "{target} dosyasını oluşturuyor veya güncelliyor.",
            "es": "Crea o actualiza el archivo {target}.",
            "de": "Schreibt oder aktualisiert die Datei {target}.",
            "fr": "Crée ou modifie le fichier {target}.",
        },
        "delete": {
            "en": "Permanently deletes {target}.",
            "tr": "{target} hedefini kalıcı olarak siliyor.",
            "es": "Elimina permanentemente {target}.",
            "de": "Löscht {target} dauerhaft.",
            "fr": "Supprime définitivement {target}.",
        },
        "list": {
            "en": "Lists files and folders in {target}.",
            "tr": "{target} dizinindeki dosya ve klasörleri listeliyor.",
            "es": "Lista los archivos y carpetas en {target}.",
            "de": "Listet Dateien und Ordner in {target} auf.",
            "fr": "Liste les fichiers et dossiers dans {target}.",
        },
        "test": {
            "en": "Executes automated test suites.",
            "tr": "Otomatik test paketlerini çalıştırıyor.",
            "es": "Ejecuta suites de pruebas automatizadas.",
            "de": "Führt automatisierte Testsuiten aus.",
            "fr": "Exécute les suites de tests automatisés.",
        },
        "build": {
            "en": "Compiles or builds project assets.",
            "tr": "Proje dosyalarını derliyor veya derleme oluşturuyor.",
            "es": "Compila o construye el proyecto.",
            "de": "Kompiliert oder erstellt Projektressourcen.",
            "fr": "Compile ou génère les ressources du projet.",
        },
        "git": {
            "en": "Performs Git version control operation ({subcmd}).",
            "tr": "Git sürüm kontrol işlemi ({subcmd}) gerçekleştiriyor.",
            "es": "Realiza la operación de control de versiones Git ({subcmd}).",
            "de": "Führt Git-Versionskontrolloperation ({subcmd}) aus.",
            "fr": "Effectue une opération de contrôle de version Git ({subcmd}).",
        },
        "generic_command": {
            "en": "Executes shell command '{cmd}'.",
            "tr": "'{cmd}' komutunu terminalde çalıştırıyor.",
            "es": "Ejecuta el comando '{cmd}' en la terminal.",
            "de": "Führt den Shell-Befehl '{cmd}' aus.",
            "fr": "Exécute la commande '{cmd}' dans le terminal.",
        },
        "generic_tool": {
            "en": "Executes '{tool}' action.",
            "tr": "'{tool}' işlemini çalıştırıyor.",
            "es": "Ejecuta la acción '{tool}'.",
            "de": "Führt die Aktion '{tool}' aus.",
            "fr": "Exécute l'action '{tool}'.",
        },
    }

    def resolve_active_language(self, user_preference: Optional[str]) -> str:
        """
        Resolves active language preference.
        Falls back to system locale or 'en' if unspecified or invalid.
        """
        if user_preference and user_preference != "auto":
            clean = user_preference.strip().lower()[:2]
            if clean in self.SUPPORTED_LANGUAGES:
                return clean

        # Attempt system locale detection
        try:
            sys_loc = locale.getlocale()[0] or os.environ.get("LANG", "")
            if sys_loc:
                sys_lang = sys_loc.split("_")[0].lower()
                if sys_lang in self.SUPPORTED_LANGUAGES:
                    return sys_lang
        except Exception:
            pass

        return self.DEFAULT_LANGUAGE

    def get_localized_alert(self, category: str, active_language: str) -> str:
        """Returns localized warning badge phrase for given threat category."""
        lang = active_language if active_language in self.SUPPORTED_LANGUAGES else self.DEFAULT_LANGUAGE
        category_clean = category.lower()
        if category_clean in self.ALERT_TERMS:
            return self.ALERT_TERMS[category_clean].get(lang, self.ALERT_TERMS[category_clean]["en"])
        return f"WARNING: {category}"

    def generate_explanation(
        self,
        tool_name: str,
        payload: Dict[str, Any],
        assessment: SecurityAssessment,
        active_language: Optional[str] = None,
    ) -> str:
        """
        Generates a 1-2 sentence plain-language summary of consequences
        in the specified or auto-resolved active language.
        """
        lang = self.resolve_active_language(active_language)

        base_summary = self._describe_action(tool_name, payload, lang)

        # Append alert statement if high-risk threat detected (Req 3.7)
        alert_statement = ""
        if assessment.is_unparseable:
            alert_statement = self.get_localized_alert("unparseable", lang)
        elif assessment.exfiltration_score >= 85:
            alert_statement = self.get_localized_alert("exfiltration", lang)
        elif assessment.integrity_score >= 70:
            alert_statement = self.get_localized_alert("destructive", lang)
        elif assessment.confidentiality_score >= 80:
            alert_statement = self.get_localized_alert("confidentiality", lang)
        elif assessment.injection_score >= 75:
            alert_statement = self.get_localized_alert("injection", lang)

        if alert_statement:
            return f"{base_summary} {alert_statement}".strip()

        return base_summary

    def _describe_action(self, tool_name: str, payload: Dict[str, Any], lang: str) -> str:
        """Generates primary consequence sentence for common actions."""
        # Check command payload
        cmd = ""
        if tool_name in ("bash", "run_command", "shell", "execute_command"):
            for k in ("command", "cmd", "CommandLine", "script"):
                if k in payload and isinstance(payload[k], str):
                    cmd = payload[k].strip()
                    break

        if cmd:
            # Check for common patterns
            if re.match(r"^rm\b", cmd):
                target = cmd.replace("rm", "").replace("-rf", "").replace("-r", "").strip() or "specified items"
                return self.TOOL_TEMPLATES["delete"][lang].format(target=target)
            if re.match(r"^(?:ls|dir|find)\b", cmd):
                target = cmd.split()[-1] if len(cmd.split()) > 1 and not cmd.split()[-1].startswith("-") else "current directory"
                return self.TOOL_TEMPLATES["list"][lang].format(target=target)
            if re.search(r"\b(?:pytest|vitest|jest|cargo test|npm test)\b", cmd):
                return self.TOOL_TEMPLATES["test"][lang]
            if re.search(r"\b(?:npm run build|cargo build|make|docker build)\b", cmd):
                return self.TOOL_TEMPLATES["build"][lang]
            if cmd.startswith("git "):
                subcmd = cmd.split()[1] if len(cmd.split()) > 1 else "status"
                return self.TOOL_TEMPLATES["git"][lang].format(subcmd=subcmd)

            short_cmd = cmd if len(cmd) <= 40 else cmd[:37] + "..."
            return self.TOOL_TEMPLATES["generic_command"][lang].format(cmd=short_cmd)

        # File reading/writing tools
        if tool_name in ("view_file", "read_file", "get_file", "cat"):
            target = payload.get("file_path") or payload.get("path") or payload.get("AbsolutePath") or "file"
            return self.TOOL_TEMPLATES["read"][lang].format(target=target)

        if tool_name in ("write_to_file", "write_file", "edit_file", "replace_file_content"):
            target = payload.get("TargetFile") or payload.get("file_path") or payload.get("path") or "file"
            return self.TOOL_TEMPLATES["write"][lang].format(target=target)

        return self.TOOL_TEMPLATES["generic_tool"][lang].format(tool=tool_name)
