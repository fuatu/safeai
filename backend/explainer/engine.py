"""Multilingual plain-language 'For Dummies' explainer engine."""

import locale
import os
import re
from typing import Any, Dict, List, Optional, Set

from backend.security.engine import SecurityAssessment


class ExplainerEngine:
    """
    Converts raw technical tool executions and AST security assessments
    into concise, 1-2 sentence human-understandable summaries in the user's active language.
    """

    SUPPORTED_LANGUAGES = {"en", "tr", "es", "de", "fr"}
    DEFAULT_LANGUAGE = "en"

    def __init__(self, default_language: str = "en"):
        self.default_language = (
            default_language if default_language in self.SUPPORTED_LANGUAGES else self.DEFAULT_LANGUAGE
        )

    # Localized danger alerts for high-risk threat categories
    ALERT_TERMS: Dict[str, Dict[str, str]] = {
        "destructive": {
            "en": "WARNING: This action permanently alters or deletes files and directories on your system.",
            "tr": "UYARI: Bu işlem sisteminizdeki dosya veya dizinleri kalıcı olarak siler veya değiştirir.",
            "es": "ADVERTENCIA: Esta acción modifica o elimina permanentemente archivos y carpetas del sistema.",
            "de": "WARNUNG: Diese Aktion ändert oder löscht Dateien und Verzeichnisse auf Ihrem System dauerhaft.",
            "fr": "ATTENTION: Cette action modifie ou supprime définitivement des fichiers et répertoires système.",
        },
        "dataloss": {
            "en": "CRITICAL WARNING: This action permanently wipes database records, drops tables, or truncates data.",
            "tr": "KRİTİK UYARI: Bu işlem veritabanı kayıtlarını, tabloları kalıcı olarak siler veya verileri yok eder.",
            "es": "ADVERTENCIA CRÍTICA: Esta acción borra permanentemente registros de base de datos o elimina tablas.",
            "de": "KRITISCHE WARNUNG: Diese Aktion löscht dauerhaft Datenbankdatensätze oder Tabellen.",
            "fr": "ATTENTION CRITIQUE: Cette action supprime définitivement des enregistrements ou des tables de base de données.",
        },
        "cloud": {
            "en": "WARNING: This action deletes or terminates cloud infrastructure resources (AWS, Azure, GCP, K8s).",
            "tr": "UYARI: Bu işlem bulut altyapı kaynaklarını (AWS, Azure, GCP, K8s) kalıcı olarak siler veya sonlandırır.",
            "es": "ADVERTENCIA: Esta acción elimina o termina recursos de infraestructura en la nube.",
            "de": "WARNUNG: Diese Aktion löscht oder beendet Cloud-Infrastrukturressourcen.",
            "fr": "ATTENTION: Cette action supprime ou termine des ressources d'infrastructure cloud.",
        },
        "availability": {
            "en": "WARNING: This action forces process termination, stops services, or halts the system.",
            "tr": "UYARI: Bu işlem çalışan süreçleri zorla sonlandırır, servisleri durdurur veya sistemi kapatır.",
            "es": "ADVERTENCIA: Esta acción fuerza la finalización de procesos o detiene servicios.",
            "de": "WARNUNG: Diese Aktion beendet Prozesse gewaltsam oder stoppt Dienste.",
            "fr": "ATTENTION: Cette action termine des processus ou arrête des services.",
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

    # Unique character markers (characters exclusive to this language among supported set)
    UNIQUE_CHAR_MARKERS: Dict[str, Set[str]] = {
        "tr": set("çğışÇĞIŞ"),
        "de": set("äßÄẞ"),
        "es": set("ñÑ¿¡"),
        "fr": set("êàùâîôëïÊÀÙÂÎÔËÏ"),
    }
    # Shared accent markers
    SHARED_CHAR_MARKERS: Dict[str, Set[str]] = {
        "tr": set("öüÖÜİ"),
        "de": set("öüÖÜ"),
        "es": set("áéíóúÁÉÍÓÚ"),
        "fr": set("éèÉÈçÇ"),
    }

    # Distinctive stopword dictionaries
    VOCAB_MARKERS: Dict[str, Set[str]] = {
        "tr": {"bir", "ve", "için", "bu", "ile", "dosya", "sil", "yap", "çalıştır", "güncelle", "lütfen", "kod", "hata", "klasör", "komut", "bunu", "göster", "proje", "listele", "kontrol"},
        "de": {"der", "die", "das", "und", "für", "mit", "ist", "nicht", "bitte", "datei", "löschen", "ausführen", "kannst", "machen", "alles", "projekt", "überprüfe", "zeige", "führen", "führe"},
        "es": {"el", "la", "los", "las", "para", "con", "por", "archivo", "eliminar", "ejecutar", "favor", "puedes", "hacer", "proyecto", "pruebas", "muestra"},
        "fr": {"le", "la", "les", "pour", "avec", "dans", "fichier", "supprimer", "exécuter", "peux", "faire", "projet", "affiche"},
        "en": {"the", "and", "for", "with", "this", "file", "delete", "remove", "directory", "please", "can", "you", "make", "show", "check", "run"},
    }

    def detect_language_from_context(self, context_text: Optional[str]) -> Optional[str]:
        """
        Auto-detection from context has been disabled to strictly honor policy settings.
        Always returns None.
        """
        return None

    def resolve_active_language(
        self,
        user_preference: Optional[str] = None,
        context_text: Optional[str] = None,
    ) -> str:
        """
        Resolves active language strictly from user/system policy setting.
        Never auto-detects or guesses from code or conversational substrings.
        """
        if user_preference and user_preference != "auto":
            clean = user_preference.strip().lower()[:2]
            if clean in self.SUPPORTED_LANGUAGES:
                return clean

        return getattr(self, "default_language", self.DEFAULT_LANGUAGE)

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
        context_text: Optional[str] = None,
    ) -> str:
        """
        Generates a 1-2 sentence plain-language summary of consequences
        strictly in the configured active language.
        """
        lang = self.resolve_active_language(active_language)

        base_summary = self._describe_action(tool_name, payload, lang)

        # Append alert statement if high-risk threat detected (Req 3.7)
        # Append alert statement if high-risk threat detected
        alert_statement = ""
        if assessment.is_unparseable:
            alert_statement = self.get_localized_alert("unparseable", lang)
        elif any("sql_" in f or "data_loss" in f for f in assessment.risk_factors):
            alert_statement = self.get_localized_alert("dataloss", lang)
        elif any("aws_" in f or "az_" in f or "gcloud_" in f or "k8s_" in f or "iac_" in f for f in assessment.risk_factors):
            alert_statement = self.get_localized_alert("cloud", lang)
        elif assessment.integrity_score >= 70:
            alert_statement = self.get_localized_alert("destructive", lang)
        elif assessment.availability_score >= 70:
            alert_statement = self.get_localized_alert("availability", lang)
        elif assessment.exfiltration_score >= 85:
            alert_statement = self.get_localized_alert("exfiltration", lang)
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
            # Check for SQL Data Loss
            if re.search(r"(?i)\b(?:DELETE\s+FROM|DROP\s+TABLE|DROP\s+DATABASE|TRUNCATE)\b", cmd):
                return {
                    "en": "Modifies or wipes records in a database table or schema.",
                    "tr": "Veritabanı tablosundaki kayıtları veya şemayı siliyor ya da sıfırlıyor.",
                    "es": "Modifica o elimina registros en una tabla o esquema de base de datos.",
                    "de": "Ändert oder löscht Datensätze in einer Datenbanktabelle oder einem Schema.",
                    "fr": "Modifie ou supprime des enregistrements dans une table de base de données.",
                }.get(lang, "Modifies or wipes database table records.")

            # Check for Cloud Mutations
            if re.search(r"\baws\s+s3\s+(?:rm|rb)\b", cmd):
                return {
                    "en": "Deletes files or buckets from AWS S3 cloud storage.",
                    "tr": "AWS S3 bulut depolamasından dosya veya depolama alanı siliyor.",
                    "es": "Elimina archivos o depósitos del almacenamiento en la nube AWS S3.",
                    "de": "Löscht Dateien oder Buckets aus dem AWS S3-Cloud-Speicher.",
                    "fr": "Supprime des fichiers ou des compartiments du stockage cloud AWS S3.",
                }.get(lang, "Deletes files from AWS S3 storage.")

            if re.search(r"\b(?:aws\s+ec2\s+terminate-instances|az\s+vm\s+delete|gcloud\s+compute\s+instances\s+delete)\b", cmd):
                return {
                    "en": "Permanently terminates virtual machine instances in the cloud.",
                    "tr": "Buluttaki sanal sunucu örneklerini kalıcı olarak sonlandırıyor.",
                    "es": "Termina permanentemente instancias de máquinas virtuales en la nube.",
                    "de": "Beendet virtuelle Maschineninstanzen in der Cloud dauerhaft.",
                    "fr": "Arrête définitivement des instances de machines virtuelles dans le cloud.",
                }.get(lang, "Terminates cloud virtual machines.")

            if re.search(r"\b(?:terraform\s+destroy|pulumi\s+destroy)\b", cmd):
                return {
                    "en": "Destroys all infrastructure resources provisioned by infrastructure-as-code.",
                    "tr": "Kod olarak altyapı (IaC) ile oluşturulmuş tüm bulut kaynaklarını yok ediyor.",
                    "es": "Destruye todos los recursos de infraestructura gestionados por código.",
                    "de": "Zerstört alle durch Infrastructure-as-Code bereitgestellten Ressourcen.",
                    "fr": "Détruit toutes les ressources d'infrastructure gérées par code.",
                }.get(lang, "Destroys all provisioned infrastructure resources.")

            if re.search(r"\b(?:killall|pkill|kill\s+-9)\b", cmd):
                return {
                    "en": "Terminates active system processes or services.",
                    "tr": "Çalışan sistem süreçlerini veya servisleri sonlandırıyor.",
                    "es": "Termina procesos o servicios activos del sistema.",
                    "de": "Beendet aktive Systemprozesse oder Dienste.",
                    "fr": "Termine des processus ou des services système actifs.",
                }.get(lang, "Terminates system processes.")

            # Check for common patterns
            if re.match(r"^rm\b", cmd):
                target = cmd.replace("rm", "").replace("-rf", "").replace("-r", "").replace("-f", "").strip() or "specified items"
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
            if re.search(r"\baws\s+iam\s+list-users\b", cmd):
                return {
                    "en": "Lists and discovers IAM user accounts in the AWS cloud environment.",
                    "tr": "AWS bulut ortamındaki IAM kullanıcı hesaplarını listeliyor.",
                    "es": "Lista las cuentas de usuario IAM en el entorno de AWS.",
                    "de": "Listet IAM-Benutzerkonten in der AWS-Cloud-Umgebung auf.",
                    "fr": "Répertorie les comptes d'utilisateurs IAM dans l'environnement cloud AWS.",
                }.get(lang, "Lists IAM user accounts in AWS.")
            if re.search(r"\baws\s+sts\s+get-caller-identity\b", cmd):
                return {
                    "en": "Checks AWS credentials to verify active account and caller identity.",
                    "tr": "Etkin hesabı ve kimliği doğrulamak için AWS kimlik bilgilerini kontrol ediyor.",
                    "es": "Verifica las credenciales de AWS para identificar la cuenta activa.",
                    "de": "Überprüft die AWS-Anmeldeinformationen zur Überprüfung des aktiven Kontos.",
                    "fr": "Vérifie les identifiants AWS pour vérifier le compte actif.",
                }.get(lang, "Checks AWS account and caller identity.")

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
