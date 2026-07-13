"""Infrastructure i18n légère (FR + EN) pour le sidecar Workproba.

Substitution Mustache minimale ``{var}`` ; pluriel via clés ``.one`` / ``.many``.
"""

from __future__ import annotations

import re
from typing import Any

Locale = str
DEFAULT_LOCALE: Locale = "fr"
SUPPORTED_LOCALES: frozenset[str] = frozenset({"fr", "en"})

_MUSTACHE_RE = re.compile(r"\{(\w+)\}")


def normalize_locale(locale: str | None) -> Locale:
    if not locale:
        return DEFAULT_LOCALE
    base = locale.lower().replace("_", "-").split("-", 1)[0]
    if base in SUPPORTED_LOCALES:
        return base
    return DEFAULT_LOCALE


def _lookup(locale: Locale, key: str) -> str:
    loc = normalize_locale(locale)
    parts = key.split(".")
    node: Any = MESSAGES.get(loc)
    for part in parts:
        if not isinstance(node, dict) or part not in node:
            fallback = MESSAGES.get(DEFAULT_LOCALE, {})
            node = fallback
            for fallback_part in parts:
                if not isinstance(node, dict) or fallback_part not in node:
                    return key
                node = node[fallback_part]
            break
        node = node[part]
    return node if isinstance(node, str) else key


def t(locale: str | None, key: str, **vars: Any) -> str:
    """Traduit une clé et substitue les variables ``{name}``."""
    try:
        template = _lookup(normalize_locale(locale), key)

        def replace(match: re.Match[str]) -> str:
            name = match.group(1)
            if name not in vars:
                return match.group(0)
            return str(vars[name])

        return _MUSTACHE_RE.sub(replace, template)
    except Exception:
        return key


def format_summary(
    locale: str | None,
    key: str,
    vars: dict[str, Any] | None = None,
    count: int = 0,
) -> str:
    """Choisit ``{key}.one`` ou ``{key}.many`` selon ``count``."""
    try:
        suffix = "one" if count == 1 else "many"
        return t(locale, f"{key}.{suffix}", count=count, **(vars or {}))
    except Exception:
        return key


MESSAGES: dict[str, dict[str, Any]] = {
    "fr": {
        "human": {
            "space_default": "l'espace",
            "document_default": "ce document",
            "location_root": "de l'espace",
            "location_subdir": "du dossier {name}",
            "query_default": "cette recherche",
            "query_labeled": "« {text} »",
            "detail_pages": " ({pages} pages)",
            "detail_lines": " ({lines} lignes)",
            "list_files": {
                "will": "Je vais lister les fichiers {location}",
                "cannot": "Je n'ai pas pu lister les fichiers {location}",
                "empty": "J'ai listé les fichiers {location} (aucun élément)",
                "count": {
                    "one": "J'ai listé les fichiers {location} ({count} élément)",
                    "many": "J'ai listé les fichiers {location} ({count} éléments)",
                },
            },
            "search_kb": {
                "will": "Je vais chercher {query} dans les fichiers",
                "cannot": "Je n'ai pas pu chercher {query} dans les fichiers",
                "empty": "Je n'ai trouvé aucun résultat pour {query}",
                "count": {
                    "one": "J'ai trouvé {count} résultat pour {query}",
                    "many": "J'ai trouvé {count} résultats pour {query}",
                },
            },
            "read_document": {
                "will": "Je vais lire {name}",
                "cannot": "Je n'ai pas pu lire {name}",
                "done": "J'ai lu {name}{detail}",
            },
            "run_code": {
                "will": "Je vais exécuter un calcul",
                "cannot": "Je n'ai pas pu exécuter le calcul",
                "done": "J'ai exécuté un calcul",
            },
            "generate_document": {
                "will": "Je vais créer {name}",
                "cannot": "Je n'ai pas pu créer {name}",
                "done": "J'ai créé {name}",
            },
            "write_docx": {
                "will": "Je vais créer le document Word {filename}",
                "cannot": "Je n'ai pas pu créer le document Word {filename}",
                "done": "J'ai créé le document Word {filename}",
            },
            "write_xlsx": {
                "will": "Je vais créer le classeur Excel {filename}",
                "cannot": "Je n'ai pas pu créer le classeur Excel {filename}",
                "done": "J'ai créé le classeur Excel {filename}",
            },
            "write_pdf": {
                "will": "Je vais créer le PDF {filename}",
                "cannot": "Je n'ai pas pu créer le PDF {filename}",
                "done": "J'ai créé le PDF {filename}",
            },
            "generic": {
                "cannot_finish": "Je n'ai pas pu terminer cette action",
                "finished": "J'ai terminé cette action",
                "will_act": "Je vais effectuer une action",
            },
            "cancelled": "Action annulée",
        },
        "loop": {
            "internal_error": (
                "Une erreur interne est survenue. Veuillez réessayer."
            ),
            "usage_limit_exceeded": (
                "Nombre maximal d'itérations agent atteint avant la réponse finale."
            ),
            "unexpected_model_behavior": "Comportement modèle inattendu : {detail}",
            "action_cancelled": "Action annulée",
        },
        "main": {
            "confirmation_not_found": "Confirmation introuvable ou expirée.",
            "plan_not_found": "Plan introuvable ou expiré.",
            "turn_in_progress": (
                "Un tour agent est déjà en cours pour cette session."
            ),
            "turn_timeout": (
                "Le tour agent a dépassé le délai maximal autorisé ({seconds}s)."
            ),
            "internal_error": (
                "Une erreur interne est survenue. Veuillez réessayer."
            ),
        },
        "auth": {
            "local_only": "Sidecar accessible uniquement en local.",
        },
        "attachments": {
            "header": (
                "Pièces jointes au message (contenu extrait ci-dessous). "
                "Appuie-toi sur ce contenu pour répondre."
            ),
            "title": "Pièce jointe : {name}",
            "title_image": "Pièce jointe (image) : {name}",
            "unreadable": "contenu illisible",
            "unreadable_block": "_Erreur : {message}._",
            "image": (
                "Image jointe ({mime}, {size}). "
                "La saisie multimodale n'est pas encore disponible : "
                "décris-la toi-même si l'utilisateur pose une question à son sujet."
            ),
            "vision_injected": (
                "Image jointe transmise au modèle (vision) : {name}."
            ),
            "vision_pdf_injected": (
                "PDF scanné transmis au modèle (vision) : {name}."
            ),
            "unavailable_guided": (
                "Lecture non disponible pour {name} avec le moteur actif."
            ),
            "unavailable_locked": (
                "Lecture non disponible pour {name} avec le moteur imposé."
            ),
            "ocr_failed": "_OCR impossible : {error}_",
            "binary_too_large": (
                "_Fichier binaire trop volumineux pour extraction "
                "({size} octets > {max_bytes})._"
            ),
            "extraction_failed": "_Extraction impossible : {error}_",
            "truncated_note": (
                "\n_Extrait tronqué à {max_chars} caractères "
                "(sur {total})._"
            ),
            "text_truncated_suffix": "\n\n[tronqué à {max_chars} caractères]",
            "text_decode_failed": "_Déchiffrement du texte impossible._",
            "unsupported_type": (
                "_Type non pris en charge pour l'extraction ({mime})._"
            ),
            "size_unknown": "taille inconnue",
            "size_bytes": "{size} o",
            "size_kb": "{size} Ko",
            "size_mb": "{size} Mo",
            "mime_unknown": "type inconnu",
            "status": {
                "viewed": "Vue (image)",
                "read": "Lue (PDF)",
                "viewed_pdf": "Vue (PDF scanné)",
                "scanned_pdf": "Lue (PDF scanné)",
                "word": "Lue (Word)",
                "excel": "Lue (Excel)",
                "other": "Pièce jointe (non lue)",
                "unavailable": "Lecture non disponible",
            },
        },
        "tools": {
            "system_prompt": (
                "Tu es Workproba, l'assistant IA local d'Improba. Tu aides "
                "l'utilisateur à analyser, comprendre et produire du contenu "
                "à partir des fichiers de son espace de travail local. Utilise "
                "les outils fournis (list_files, search_kb, read_document, "
                "run_code, generate_document) quand c'est pertinent. Réponds en "
                "français, de façon claire et concise, avec un langage accessible "
                "aux non-codeurs. Parle de « l'espace » ou « le dossier de "
                "travail », jamais de « projet » pour désigner le dossier local. "
                "Cite les chemins de fichiers relatifs quand tu t'appuies sur "
                "leur contenu. Les outils appliquent des plafonds de taille : si "
                "read_document renvoie `truncated: true`, rappelle-le avec un "
                "`offset_lines` plus grand pour paginer. Pour décrire le contenu "
                "d'un dossier, commence par list_files."
            ),
            "inventory_empty": (
                "Aucun fichier de l'espace n'a été transmis dans le contexte. "
                "Utilise l'outil list_files pour explorer l'arborescence du "
                "dossier de travail avant de conclure qu'il est vide."
            ),
            "inventory_header": (
                "Inventaire de l'espace (chemins relatifs, extrait de "
                "l'arborescence) :"
            ),
            "inventory_overflow": "… et {count} autres fichiers non listés ici.",
            "inventory_kind_file": "fichier",
            "session_first_request": "Première demande : {text}",
            "session_last_reply": "Dernière réponse : {text}",
            "inventory_footer": (
                "\nUtilise read_document pour lire un fichier (par chemin relatif), "
                "search_kb pour rechercher du contenu par mot-clé, list_files pour "
                "lister une sous-arborescence, run_code pour exécuter du code en "
                "précisant les project_files à exposer au sandbox."
            ),
            "sessions_note": (
                "Cet espace contient {count} autre(s) conversation(s) "
                "antérieure(s). Utilise l'outil recall_project_sessions pour "
                "obtenir un résumé de ces sessions si l'utilisateur fait "
                "référence à un échange précédent ou si le contexte le justifie."
            ),
            "space_name_context": (
                "L'espace de travail actif s'appelle « {name} ». Quand tu désignes "
                "l'espace par son nom, utilise celui-ci plutôt qu'un nom d'espace lu "
                "dans l'historique de conversation. Si l'utilisateur indique travailler "
                "dans un autre espace, fais confiance à l'utilisateur."
            ),
            "sessions_no_folder": "Aucun dossier d'espace associé.",
            "sandbox_unavailable": (
                "Sandbox indisponible : Docker n'est pas démarré. "
                "Lancez Docker ou utilisez le mode guidé."
            ),
            "action_cancelled_by_user": "Action annulée par l'utilisateur",
            "plan_mode_prompt": (
                "Pour les tâches complexes (plusieurs fichiers, plusieurs étapes, "
                "modifications destructives, ou si l'utilisateur demande un plan), "
                "appelle d'abord l'outil propose_plan avec les étapes prévues "
                "(outil, résumé, fichier cible) et une justification. N'exécute pas "
                "les écritures tant que le plan n'est pas approuvé. Pour les tâches "
                "simples (une lecture, une reformulation), agis directement."
            ),
        },
        "plan": {
            "title": "Plan proposé",
            "approve": "Approuver le plan",
            "deny": "Refuser",
            "step_label": "Étape {index} : {summary}",
            "rationale": "Justification",
            "timeout": "L'approbation du plan a expiré.",
            "denied": "Plan refusé par l'utilisateur.",
        },
        "versions": {
            "snapshot_label": "Version créée avant écriture de {file}",
            "restore_label": "Version restaurée de {file}",
            "empty": "Aucune version enregistrée pour ce fichier.",
        },
        "memory": {
            "title": "Mémoire de l'espace",
            "items_empty": "Aucun souvenir enregistré pour cet espace.",
            "forget_done": "Souvenir oublié.",
            "forget_not_found": "Souvenir introuvable.",
            "clear_confirm_required": (
                "Confirmation requise pour effacer la mémoire de l'espace."
            ),
            "clear_done_all": "Toute la mémoire de l'espace a été effacée.",
            "clear_done_memories": "Les souvenirs explicites et l'index ont été effacés.",
            "clear_done_conversations": "L'historique des conversations a été effacé.",
            "search_empty": "Aucun résultat pour cette recherche.",
            "scope_user": "Mémoire utilisateur (globale)",
            "scope_project": "Mémoire projet",
            "scope_all": "Mémoire utilisateur + projet",
            "add_done": "Souvenir enregistré.",
            "add_empty": "Le contenu du souvenir ne peut pas être vide.",
            "agent_user_header": "Souvenirs utilisateur (partagés entre tous les espaces) :",
            "agent_project_header": "Souvenirs projet (cet espace) :",
            "agent_user_empty": "Aucun souvenir utilisateur.",
            "agent_project_empty": "Aucun souvenir projet.",
            "agent_remember_done": "Souvenir enregistré dans la mémoire {scope}.",
            "agent_remember_invalid_scope": "Scope invalide : utiliser \"user\" ou \"project\".",
        },
        "browser": {
            "status_inactive": "Aucune page ouverte",
            "install_required": (
                "Le navigateur intégré nécessite Playwright et Chromium. "
                "Activez le plugin browser pour les installer."
            ),
        },
        "audit": {
            "title": "Journal d'audit",
            "empty": "Aucune entrée d'audit.",
            "config_readonly": "La configuration d'audit est en lecture seule en mode verrouillé.",
            "updated": "Configuration d'audit mise à jour.",
            "export": {
                "filename": "workproba-audit.csv",
                "unsupported_format": "Format d'export non pris en charge : {format}",
            },
        },
        "cloud": {
            "not_configured": "Le dossier cloud n'est pas configuré.",
            "sync_done": "Synchronisation terminée vers {mount_path}.",
            "sync_empty": "Aucun document publié à synchroniser.",
            "project_not_found": "Projet introuvable : {project_id}.",
            "configured": "Dossier cloud configuré.",
        },
        "preset": {
            "active": "Preset enterprise actif",
            "inactive": "Aucun preset enterprise",
            "applied": "Preset enterprise appliqué.",
        },
        "errors": {
            "code_execute_locked": "Exécution de code interdite par le preset",
        },
        "personas": {
            "estimate": {
                "summary": (
                    "Environ {calls} échanges avec {personas} persona(s), "
                    "soit ~{tokens} tokens estimés"
                ),
                "no_personas": "Aucun persona sélectionné",
                "exceeds_cap": (
                    "Session importante : {calls} échanges prévus avec "
                    "{personas} persona(s)"
                ),
                "locked_cap": (
                    "Plafond preset atteint : réduisez le nombre de personas ou de tours"
                ),
            },
        },
        "preview_change": {
            "binary_unavailable": (
                "Aperçu non disponible pour ce format. "
                "Consultez le fichier généré après confirmation."
            ),
        },
        "utility": {
            "title_system_prompt": (
                "Tu génères un titre court en français pour une conversation "
                "Workproba. Réponds uniquement par un titre en texte brut, "
                "60 caractères maximum, sans guillemets et sans ponctuation "
                "finale. Résume l'intention de l'utilisateur."
            ),
            "summary_system_prompt": (
                "Tu synthétises une conversation de travail en français. "
                "Produis un résumé compact et structuré. Utilise seulement les "
                "sections qui ont du contenu : Décisions, Faits établis, Fichiers "
                "concernés, Questions ouvertes. Reste factuel, sans inventer, et "
                "privilégie les informations utiles pour reprendre le travail."
            ),
            "default_title": "Nouvelle conversation",
            "user_message_label": "Message utilisateur :",
            "assistant_reply_label": "Réponse assistant :",
            "title_prompt_suffix": "Titre :",
            "focus_prefix": "Point d'attention à préserver : {focus}",
            "transcript_label": "Transcription :",
            "thinking_label": "Raisonnement assistant : {thinking}",
            "tool_calls_label": "Appels outils : {calls}",
            "empty_transcript": "(vide)",
            "role_prefix": "{index}. {role} : {content}",
            "compaction_focus": (
                "Conserve les décisions, fichiers concernés et questions ouvertes "
                "pour la suite du travail."
            ),
            "compaction_summary_prefix": "Résumé des échanges précédents :",
            "compaction_prior_summary": "Résumé précédent à enrichir :\n{summary}",
        },
    },
    "en": {
        "human": {
            "space_default": "the space",
            "document_default": "this document",
            "location_root": "of the space",
            "location_subdir": "of folder {name}",
            "query_default": "this search",
            "query_labeled": "« {text} »",
            "detail_pages": " ({pages} pages)",
            "detail_lines": " ({lines} lines)",
            "list_files": {
                "will": "I will list files {location}",
                "cannot": "I could not list files {location}",
                "empty": "I listed files {location} (no items)",
                "count": {
                    "one": "I listed files {location} ({count} item)",
                    "many": "I listed files {location} ({count} items)",
                },
            },
            "search_kb": {
                "will": "I will search for {query} in the files",
                "cannot": "I could not search for {query} in the files",
                "empty": "I found no results for {query}",
                "count": {
                    "one": "I found {count} result for {query}",
                    "many": "I found {count} results for {query}",
                },
            },
            "read_document": {
                "will": "I will read {name}",
                "cannot": "I could not read {name}",
                "done": "I read {name}{detail}",
            },
            "run_code": {
                "will": "I will run a calculation",
                "cannot": "I could not run the calculation",
                "done": "I ran a calculation",
            },
            "generate_document": {
                "will": "I will create {name}",
                "cannot": "I could not create {name}",
                "done": "I created {name}",
            },
            "write_docx": {
                "will": "I will create the Word document {filename}",
                "cannot": "I could not create the Word document {filename}",
                "done": "I created the Word document {filename}",
            },
            "write_xlsx": {
                "will": "I will create the Excel workbook {filename}",
                "cannot": "I could not create the Excel workbook {filename}",
                "done": "I created the Excel workbook {filename}",
            },
            "write_pdf": {
                "will": "I will create the PDF {filename}",
                "cannot": "I could not create the PDF {filename}",
                "done": "I created the PDF {filename}",
            },
            "generic": {
                "cannot_finish": "I could not complete this action",
                "finished": "I completed this action",
                "will_act": "I will perform an action",
            },
            "cancelled": "Action cancelled",
        },
        "loop": {
            "internal_error": "An internal error occurred. Please try again.",
            "usage_limit_exceeded": (
                "Maximum agent iterations reached before final answer."
            ),
            "unexpected_model_behavior": "Unexpected model behavior: {detail}",
            "action_cancelled": "Action cancelled",
        },
        "main": {
            "confirmation_not_found": "Confirmation not found or expired.",
            "plan_not_found": "Plan not found or expired.",
            "turn_in_progress": (
                "An agent turn is already in progress for this session."
            ),
            "turn_timeout": (
                "The agent turn exceeded the maximum allowed time ({seconds}s)."
            ),
            "internal_error": "An internal error occurred. Please try again.",
        },
        "auth": {
            "local_only": "Sidecar is only accessible locally.",
        },
        "attachments": {
            "header": (
                "Message attachments (extracted content below). "
                "Use this content to answer."
            ),
            "title": "Attachment: {name}",
            "title_image": "Attachment (image): {name}",
            "unreadable": "unreadable content",
            "unreadable_block": "_Error: {message}._",
            "image": (
                "Attached image ({mime}, {size}). "
                "Multimodal input is not available yet: "
                "describe it yourself if the user asks about it."
            ),
            "vision_injected": (
                "Attached image sent to the model (vision): {name}."
            ),
            "vision_pdf_injected": (
                "Scanned PDF sent to the model (vision): {name}."
            ),
            "unavailable_guided": (
                "Reading unavailable for {name} with the active engine."
            ),
            "unavailable_locked": (
                "Reading unavailable for {name} with the imposed engine."
            ),
            "ocr_failed": "_OCR failed: {error}_",
            "binary_too_large": (
                "_Binary file too large for extraction "
                "({size} bytes > {max_bytes})._"
            ),
            "extraction_failed": "_Extraction failed: {error}_",
            "truncated_note": (
                "\n_Extract truncated to {max_chars} characters "
                "(of {total})._"
            ),
            "text_truncated_suffix": "\n\n[truncated to {max_chars} characters]",
            "text_decode_failed": "_Could not decode text._",
            "unsupported_type": (
                "_Unsupported type for extraction ({mime})._"
            ),
            "size_unknown": "unknown size",
            "size_bytes": "{size} B",
            "size_kb": "{size} KB",
            "size_mb": "{size} MB",
            "mime_unknown": "unknown type",
            "status": {
                "viewed": "Viewed (image)",
                "read": "Read (PDF)",
                "viewed_pdf": "Viewed (scanned PDF)",
                "scanned_pdf": "Read (scanned PDF)",
                "word": "Read (Word)",
                "excel": "Read (Excel)",
                "other": "Attachment (not read)",
                "unavailable": "Reading unavailable",
            },
        },
        "tools": {
            "system_prompt": (
                "You are Workproba, Improba's local AI assistant. You help "
                "the user analyze, understand, and produce content from files "
                "in their local workspace. Use the provided tools (list_files, "
                "search_kb, read_document, run_code, generate_document) when "
                "relevant. Reply in English, clearly and concisely, using "
                "language accessible to non-developers. Refer to the local "
                "folder as the « space » or « workspace folder », never as "
                "« project » for the local directory. Cite relative file paths "
                "when relying on file content. Tools enforce size limits: if "
                "read_document returns `truncated: true`, mention it and use a "
                "larger `offset_lines` to paginate. To describe folder contents, "
                "start with list_files."
            ),
            "inventory_empty": (
                "No space files were sent in context. Use list_files to explore "
                "the workspace folder tree before concluding it is empty."
            ),
            "inventory_header": (
                "Space inventory (relative paths, tree excerpt):"
            ),
            "inventory_overflow": "… and {count} more files not listed here.",
            "inventory_kind_file": "file",
            "session_first_request": "First request: {text}",
            "session_last_reply": "Last reply: {text}",
            "inventory_footer": (
                "\nUse read_document to read a file (by relative path), "
                "search_kb to search content by keyword, list_files to list a "
                "subtree, run_code to run code with project_files exposed to "
                "the sandbox."
            ),
            "sessions_note": (
                "This space has {count} other prior conversation(s). Use "
                "recall_project_sessions for a summary if the user refers to "
                "a previous exchange or context requires it."
            ),
            "space_name_context": (
                'The active workspace is named "{name}". When you refer to the '
                "space by name, use this one rather than a workspace name read from "
                "the conversation history. If the user says they are now working in "
                "a different space, trust the user."
            ),
            "sessions_no_folder": "No space folder associated.",
            "sandbox_unavailable": (
                "Sandbox unavailable: Docker is not running. "
                "Start Docker or use guided mode."
            ),
            "action_cancelled_by_user": "Action cancelled by the user",
            "plan_mode_prompt": (
                "For complex tasks (multiple files, multiple steps, destructive "
                "changes, or when the user asks for a plan), first call propose_plan "
                "with the planned steps (tool, summary, target file) and a rationale. "
                "Do not perform writes until the plan is approved. For simple tasks "
                "(a read, a rewrite), act directly."
            ),
        },
        "plan": {
            "title": "Proposed plan",
            "approve": "Approve plan",
            "deny": "Deny",
            "step_label": "Step {index}: {summary}",
            "rationale": "Rationale",
            "timeout": "Plan approval timed out.",
            "denied": "Plan denied by user.",
        },
        "versions": {
            "snapshot_label": "Version saved before writing {file}",
            "restore_label": "Restored version of {file}",
            "empty": "No versions recorded for this file.",
        },
        "memory": {
            "title": "Workspace memory",
            "items_empty": "No memories stored for this workspace.",
            "forget_done": "Memory forgotten.",
            "forget_not_found": "Memory not found.",
            "clear_confirm_required": (
                "Confirmation is required to clear workspace memory."
            ),
            "clear_done_all": "All workspace memory has been cleared.",
            "clear_done_memories": "Explicit memories and the index have been cleared.",
            "clear_done_conversations": "Conversation history has been cleared.",
            "search_empty": "No results for this search.",
            "scope_user": "User memory (global)",
            "scope_project": "Project memory",
            "scope_all": "User + project memory",
            "add_done": "Memory saved.",
            "add_empty": "Memory content cannot be empty.",
            "agent_user_header": "User memories (shared across all spaces):",
            "agent_project_header": "Project memories (this space):",
            "agent_user_empty": "No user memories.",
            "agent_project_empty": "No project memories.",
            "agent_remember_done": "Memory saved to {scope} memory.",
            "agent_remember_invalid_scope": "Invalid scope: use \"user\" or \"project\".",
        },
        "browser": {
            "status_inactive": "No page open",
            "install_required": (
                "The embedded browser requires Playwright and Chromium. "
                "Enable the browser plugin to install them."
            ),
        },
        "audit": {
            "title": "Audit log",
            "empty": "No audit entries.",
            "config_readonly": "Audit configuration is read-only in locked mode.",
            "updated": "Audit configuration updated.",
            "export": {
                "filename": "workproba-audit.csv",
                "unsupported_format": "Unsupported export format: {format}",
            },
        },
        "cloud": {
            "not_configured": "Cloud folder is not configured.",
            "sync_done": "Sync completed to {mount_path}.",
            "sync_empty": "No published documents to sync.",
            "project_not_found": "Project not found: {project_id}.",
            "configured": "Cloud folder configured.",
        },
        "preset": {
            "active": "Enterprise preset active",
            "inactive": "No enterprise preset",
            "applied": "Enterprise preset applied.",
        },
        "errors": {
            "code_execute_locked": "Code execution is forbidden by the preset",
        },
        "personas": {
            "estimate": {
                "summary": (
                    "About {calls} exchanges with {personas} persona(s), "
                    "~{tokens} estimated tokens"
                ),
                "no_personas": "No persona selected",
                "exceeds_cap": (
                    "Large session: {calls} planned exchanges with "
                    "{personas} persona(s)"
                ),
                "locked_cap": (
                    "Preset cap reached: reduce persona count or round count"
                ),
            },
        },
        "preview_change": {
            "binary_unavailable": (
                "Preview unavailable for this format. "
                "See the generated file after confirmation."
            ),
        },
        "utility": {
            "title_system_prompt": (
                "You generate a short English title for a Workproba "
                "conversation. Reply with plain text only, 60 characters "
                "maximum, no quotes and no trailing punctuation. Summarize "
                "the user's intent."
            ),
            "summary_system_prompt": (
                "You summarize a work conversation in English. Produce a "
                "compact structured summary. Use only sections with content: "
                "Decisions, Established facts, Files involved, Open questions. "
                "Stay factual, do not invent, and favor information useful to "
                "resume work."
            ),
            "default_title": "New conversation",
            "user_message_label": "User message:",
            "assistant_reply_label": "Assistant reply:",
            "title_prompt_suffix": "Title:",
            "focus_prefix": "Focus to preserve: {focus}",
            "transcript_label": "Transcript:",
            "thinking_label": "Assistant reasoning: {thinking}",
            "tool_calls_label": "Tool calls: {calls}",
            "empty_transcript": "(empty)",
            "role_prefix": "{index}. {role}: {content}",
            "compaction_focus": (
                "Preserve decisions, files involved, and open questions for "
                "continuing the work."
            ),
            "compaction_summary_prefix": "Summary of previous exchanges:",
            "compaction_prior_summary": "Previous summary to extend:\n{summary}",
        },
    },
}


def attachment_status_label(locale: str | None, status: str) -> str:
    """Libellé user-facing d'un statut de pièce jointe."""
    key = f"attachments.status.{status}"
    translated = t(locale, key)
    if translated == key:
        return t(locale, "attachments.status.unavailable")
    return translated


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def merge_plugin_messages(plugin_messages: dict[str, dict[str, Any]]) -> None:
    """Fusionne les traductions d'un plugin dans ``MESSAGES`` (idempotent)."""
    for locale, tree in plugin_messages.items():
        if locale not in MESSAGES:
            MESSAGES[locale] = {}
        MESSAGES[locale] = _deep_merge(MESSAGES[locale], tree)


def all_message_keys(locale: str) -> set[str]:
    """Aplatit les clés feuilles d'une locale (tests de parité)."""

    def walk(node: Any, prefix: str = "") -> set[str]:
        keys: set[str] = set()
        if isinstance(node, dict):
            for name, child in node.items():
                path = f"{prefix}.{name}" if prefix else name
                if isinstance(child, str):
                    keys.add(path)
                else:
                    keys.update(walk(child, path))
        return keys

    return walk(MESSAGES.get(locale, {}))


from app.plugins.workproba_projet.i18n import MESSAGES as _PROJET_PLUGIN_MESSAGES  # noqa: E402
from app.plugins.workproba_personas.i18n import MESSAGES as _PERSONAS_PLUGIN_MESSAGES  # noqa: E402
from app.plugins.workproba_browser.i18n import MESSAGES as _BROWSER_PLUGIN_MESSAGES  # noqa: E402
from app.plugins.workproba_cloud.i18n import MESSAGES as _CLOUD_PLUGIN_MESSAGES  # noqa: E402

merge_plugin_messages(_PROJET_PLUGIN_MESSAGES)
merge_plugin_messages(_PERSONAS_PLUGIN_MESSAGES)
merge_plugin_messages(_BROWSER_PLUGIN_MESSAGES)
merge_plugin_messages(_CLOUD_PLUGIN_MESSAGES)
