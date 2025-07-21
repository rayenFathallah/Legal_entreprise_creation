# app/services/chatbot_service.py

import json
import re
from datetime import datetime, timedelta

from app.core.session_memory import (
    get_user_state,
    update_user_slot,
    set_awaiting_slot,
    reset_session
)
from app.core.gemini_client import ask_gemini

# ────────────────────────────────────────────────────────────────────────────────
# 1) Load the flow definitions (unchanged)
# ────────────────────────────────────────────────────────────────────────────────
with open("app/data/flow_definitions.json", "r", encoding="utf-8") as f:
    FLOW = json.load(f)

print(">>> Loaded FLOW (type={}):\n{}".format(type(FLOW), FLOW))

# 2) Load scraped_data.json for final lookup (unchanged)
with open("app/data/scraped_data.json", "r", encoding="utf-8") as f:
    SCRAPED = json.load(f)

# ────────────────────────────────────────────────────────────────────────────────
# 3) Define the exact lists for creation vs mise à jour (unchanged)
# ────────────────────────────────────────────────────────────────────────────────

CREATION_TYPES = [
    "Société anonyme",
    "Groupement d'intérêt économique",
    "Etablissement stable",
    "Succursale d’une société étrangère",
    "Etablissement public",
    "Réseau d'associations",
    "Association tunisienne régie par le décret-loi n° 88/2011 portant organisation des associations",
    "Association tunisienne régie par des réglementations particulières",
    "Filiale d'une association étrangère régie par le décret-loi n° 88/2011 portant organisation des associations",
    "Filiale d'une association étrangère régie par des réglementations particulières",
    "Sarl/Suarl/La société en nom collectif/La société en commandite par actions/La société en commandite simple/Société civile",
    "Syndicat des propriétaires",
    "Société mutuelle de services agricoles",
    "Associations mutuelles",
    "Les Centres d’affaires d’intérêt public économique",
    "Les groupements de développement dans le secteur de l’agriculture et de la pêche",
    "Les centres techniques dans les secteurs industriels/les centres techniques dans le secteur agricole",
    "Les groupements de médecine du travail",
    "Groupements interprofessionnels dans le secteur agricole et agro-alimentaire",
    "Les groupements de maintenance et de gestion des zones industrielles",
    "Les sociétés civiles professionnelles",
    "Les sociétés mutuelles d’assurances",
    "Les coopératives",
    "Syndicat professionnel",
    "Parti politique",
    "Sociétés citoyennes locales ou régionales",
    "tout type d'entreprise"
]

MISE_A_JOUR_TYPES = [
    "Etablissement Public",
    "Association",
    "Sociétés"
]

UPDATE_ACTIONS = [
    "Désignation des dirigeants",
    "Désignation/changement/renouvellement du mandat du réviseur aux comptes",
    "Transfert du siège",
    "Dépôt des états financiers",
    "Désignation/changement/renouvellement du mandat du commissaire aux comptes",
    "Désignation / changement des dirigeants",
    "Transfert du siège ou de filiale",
    "Changement du nom de l'association",
    "Changement des objectifs",
    "Mise à jour des statuts",
    "Ouverture d'une filiale",
    "Fermeture d'une filiale",
    "Fusion des associations",
    "Dissolution/liquidation de l'association",
    "Radiation du registre",
    "Changement de dénomination sociale ou du nom commercial ou de l'enseigne",
    "Mise à jour de l'activité",
    "Transfert du siège social",
    "Changement d'adresse d'une filiale",
    "Désignation /changement /renouvellement du mandat des dirigeants",
    "Désignation/changement/renouvellement du mandat du commissaire aux comptes",
    "Dépôt des états financiers consolidés",
    "Mise à jour des associés ou actionnaires",
    "Cession des parts /actions",
    "Transformation de la forme juridique",
    "Augmentation du capital (les sociétés à responsabilité limité/ sociétés de personnes)",
    "Dépôt du rapport du commissaire aux apports en nature en cas d'augmentation du capital",
    "Augmentation du capital (les sociétés anonymes)",
    "Augmentation du capital (les sociétés civiles)",
    "Réduction du capital (les sociétés anonymes)",
    "Réduction du capital (les sociétés civiles)",
    "Réduction du capital (les sociétés à responsabilité limitée / Sociétés de personnes)",
    "Dépôt du projet de fusion des sociétés",
    "Fusion des sociétés",
    "Dépôt du projet de scission",
    "Scission des sociétés",
    "Ajout ou changement du compte bancaire",
    "Dépôt d'un contrat d'achat/location/gérance libre d'un fonds de commerce",
    "La cessation temporaire de l'activité / reprise de l'activité",
    "Prorogation de la durée de la société",
    "Changement de la date de clôture de l'exercice comptable",
    "Dissolution et liquidation de la société",
    "Désignation/renouvellement mandat/changement du liquidateur",
    "Dépôt d’une autorisation d'agir en faveur de l'un des liquidateurs en cas de pluralité",
    "Dépôt des états financiers de liquidation",
    "L'avis de clôture de la liquidation",
    "Radiation du registre",
    "Dépôt du PV de l'approbation des états financiers"
]

# ────────────────────────────────────────────────────────────────────────────────
# 4) Main orchestrator: handle_chat_turn
# ────────────────────────────────────────────────────────────────────────────────
def handle_chat_turn(user_id: str, user_input: str) -> str:
    state = get_user_state(user_id)
    slots = state["slots"]
    awaiting = state["awaiting_slot"]

    print("===== New chat turn =====")
    print(f"User ID: {user_id}")
    print(f"Message: {user_input!r}")
    print(f"Slots before processing: {slots}")
    print(f"Awaiting slot: {awaiting}")
    print("------------------------")

    # ── A) If awaiting_slot is set, validate that one slot ───────────────────────
    if awaiting is not None:
        slot_def = next(s for s in FLOW if s["slot_key"] == awaiting)
        print(f">>> Validating slot '{awaiting}'…")
        valid, extracted_value = _validate_and_extract_slot(awaiting, user_input)
        print(f"    Validation for '{awaiting}': valid={valid}, value={extracted_value!r}")

        if not valid:
            # Ask the retry prompt for that slot
            return slot_def["retry_prompt"]

        # If valid, store it
        print(f"    Storing slot '{awaiting}' = {extracted_value!r}")
        update_user_slot(user_id, awaiting, extracted_value)

        # Re‐extract any other slots from the same message
        print("    Re‐extracting other slots from this message…")
        _extract_slots_from_free_form(user_id, user_input)

        slots = get_user_state(user_id)["slots"]
        print(f"    Slots after re‐extraction: {slots}")

    else:
        # ── B) Free‐form extraction for missing slots ───────────────────────────────
        print(">>> Free‐form extraction for missing slots…")
        _extract_slots_from_free_form(user_id, user_input)
        slots = get_user_state(user_id)["slots"]
        print(f"    Slots after free‐form extraction: {slots}")

    # ── C) Find next missing slot (treat 'unknown' as missing) ──────────────────
    next_slot = _find_next_missing_slot(slots)
    if next_slot is not None:
        slot_def = next(s for s in FLOW if s["slot_key"] == next_slot)
        print(f">>> Next missing slot: {next_slot}. Asking prompt.")
        set_awaiting_slot(user_id, next_slot)
        return slot_def["prompt"]

    # ── D) All required slots filled → compute final answer ─────────────────────
    print(">>> All required slots filled. Computing final answer…")
    final_answer = _compute_final_answer_using_scraped_data(slots)
    print(f"    Final answer: {final_answer!r}")
    reset_session(user_id)
    print("    Session reset. End of turn.")
    return final_answer


# ────────────────────────────────────────────────────────────────────────────────
# 5) Slot validation helpers, with updated intent logic
# ────────────────────────────────────────────────────────────────────────────────
def _validate_and_extract_slot(slot_key: str, user_input: str):
    normalized = user_input.strip()
    state = get_user_state(user_id=None)  # assumes global or closure provides user_id if needed

    print(f"    [_validate_and_extract_slot] slot_key={slot_key}, input={normalized!r}")

    if slot_key == "intent_type":
        print("    → Calling Gemini for 'classify_intent'…")
        parsed = ask_gemini("classify_intent", user_input)
        print(f"    → Gemini returned: {parsed}")
        intent = parsed.get("intent_type")
        if intent in ["création", "mise à jour"]:
            return True, intent
        print("    → Intent non clair. Nous laisserons intent_type = None (unknown).")
        return False, None

    elif slot_key == "type_ent":
        candidates = state.get("awaiting_details", [])
        if candidates:
            # User must choose from existing candidates
            for cand in candidates:
                if normalized.lower() == cand.lower():
                    return True, cand
            # Ask Gemini to pick from candidates
            prompt = (
                f"L’utilisateur a précisé : '{user_input}'.\n"
                f"Parmi ces options, choisis l’unique type : {candidates}\n"
                "Réponds uniquement en JSON : { \"chosen\": \"<valeur_exacte>\" }"
            )
            parsed = ask_gemini_custom(prompt)  # implement a simple wrapper if needed
            chosen = parsed.get("chosen", "").strip()
            for cand in candidates:
                if chosen.lower() == cand.lower():
                    return True, cand
            return False, None
        else:
            # First time match: depending on intent, call appropriate prompt
            intent = state["slots"].get("intent_type")
            if intent == "création":
                prompt_key = "match_type_ent_creation"
            else:
                prompt_key = "match_type_ent_mise_a_jour"
            print(f"    → Calling Gemini for '{prompt_key}'…")
            parsed = ask_gemini(prompt_key, user_input)
            print(f"    → Gemini returned: {parsed}")
            candidates = parsed.get("candidates", [])
            if not isinstance(candidates, list) or len(candidates) == 0:
                print("    → Aucun candidat trouvé par Gemini pour type_ent.")
                return False, None
            if len(candidates) == 1:
                return True, candidates[0].strip()
            # Multiple candidates: store and ask user to clarify
            state["awaiting_details"] = candidates
            follow_up = (
                f"J’ai identifié plusieurs types d’entités possibles : {', '.join(candidates)}.\n"
                "Lequel correspond le mieux à ton cas ?"
            )
            set_awaiting_slot(state["user_id"], "type_ent")
            state["last_follow_up"] = follow_up
            return None, None  # indicate that follow-up must be sent

    elif slot_key == "needs_documents_or_penalty":
        print("    → Calling Gemini for 'one_of_documents_or_penalty'…")
        parsed = ask_gemini("one_of_documents_or_penalty", user_input)
        print(f"    → Gemini returned: {parsed}")
        choice = parsed.get("choice", "")
        if choice in ["documents", "amende"]:
            return True, choice
        return False, None

    elif slot_key == "creation_date":
        print("    → Calling Gemini for 'valid_date_string'…")
        parsed = ask_gemini("valid_date_string", user_input)
        print(f"    → Gemini returned: {parsed}")
        if parsed.get("error") == "invalid_date":
            return False, None
        return True, parsed["date"]

    elif slot_key == "update_action":
        print("    → Calling Gemini for 'choose_update_action'…")
        parsed = ask_gemini("choose_update_action", user_input)
        print(f"    → Gemini returned: {parsed}")
        action = parsed.get("update_action", "").strip()
        for ua in UPDATE_ACTIONS:
            if action.lower() == ua.lower():
                return True, ua
        print("    → Gemini’s update_action not in UPDATE_ACTIONS.")
        return False, None

    else:
        print(f"    → Unknown slot_key '{slot_key}' in validation.")
        return False, None


def _extract_slots_from_free_form(user_id: str, user_input: str):
    state = get_user_state(user_id)
    slots = state["slots"]
    intent = slots.get("intent_type")
    normalized = user_input.strip()

    # --- 1) intent_type ---
    if intent is None:
        print("    → intent_type is missing. Calling Gemini…")
        parsed = ask_gemini("classify_intent", user_input)
        print(f"    → Gemini classify_intent returned: {parsed}")
        found_intent = parsed.get("intent_type")
        if found_intent in ["création", "mise à jour"]:
            print(f"    → Storing intent_type = {found_intent!r}")
            update_user_slot(user_id, "intent_type", found_intent)
            intent = found_intent
        else:
            print("    → Gemini did not return 'création' or 'mise à jour'. Stopping.")
            return

    # Reload slots
    state = get_user_state(user_id)
    slots = state["slots"]
    intent = slots["intent_type"]

    # --- 2) type_ent ---
    if intent in ["création", "mise à jour"] and slots.get("type_ent") is None:
        print("    → type_ent is missing; calling Gemini…")
        # Gemini logic inside _validate_and_extract_slot will store follow-up if needed
        valid, extracted = _validate_and_extract_slot("type_ent", user_input)
        if valid:
            print(f"    → Storing type_ent = {extracted!r}")
            update_user_slot(user_id, "type_ent", extracted)
        elif valid is None:
            # Follow-up has been set in state["last_follow_up"]
            return state.get("last_follow_up")

    # Reload slots
    state = get_user_state(user_id)
    slots = state["slots"]
    intent = slots["intent_type"]
    choice = slots.get("needs_documents_or_penalty")

    # --- 3) needs_documents_or_penalty ---
    if slots.get("needs_documents_or_penalty") is None:
        print("    → needs_documents_or_penalty is missing; calling Gemini…")
        parsed = ask_gemini("one_of_documents_or_penalty", user_input)
        print(f"    → Gemini returned: {parsed}")
        doc_choice = parsed.get("choice", "").strip()
        if doc_choice in ["documents", "amende"]:
            print(f"    → Storing needs_documents_or_penalty = {doc_choice}")
            update_user_slot(user_id, "needs_documents_or_penalty", doc_choice)
        else:
            print("    → Gemini did not return 'documents' or 'amende'")

    # Reload slots
    state = get_user_state(user_id)
    slots = state["slots"]
    intent = slots["intent_type"]
    choice = slots.get("needs_documents_or_penalty")

    # --- 4) creation_date ---
    if intent == "création" and choice == "amende" and slots.get("creation_date") is None:
        print("    → creation_date is missing and choice is 'amende'; looking for date pattern…")
        date_match = re.search(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", user_input)
        if date_match:
            candidate = date_match.group(1)
            print(f"    → Found date pattern '{candidate}'; validating via Gemini…")
            parsed = ask_gemini("valid_date_string", candidate)
            print(f"    → Gemini returned for valid_date_string: {parsed}")
            if parsed.get("error") != "invalid_date":
                dt = parsed["date"]
                print(f"    → Storing creation_date = {dt}")
                update_user_slot(user_id, "creation_date", dt)
            else:
                print("    → Gemini says date is invalid.")
        else:
            print("    → No date pattern found in message.")

    # Reload slots
    state = get_user_state(user_id)
    slots = state["slots"]
    intent = slots["intent_type"]

    # --- 5) update_action ---
    if intent == "mise à jour" and slots.get("update_action") is None:
        print("    → update_action is missing and intent is 'mise à jour'; calling Gemini…")
        parsed = ask_gemini("choose_update_action", user_input)
        print(f"    → Gemini returned for choose_update_action: {parsed}")
        action = parsed.get("update_action", "").strip()
        for ua in UPDATE_ACTIONS:
            if action.lower() == ua.lower():
                print(f"    → Storing update_action = {ua!r}")
                update_user_slot(user_id, "update_action", ua)
                break
        if get_user_state(user_id)["slots"].get("update_action") is None:
            print("    → Gemini’s update_action not recognized.")


# ────────────────────────────────────────────────────────────────────────────────
# In your _extract_slots_from_free_form helper:
# ────────────────────────────────────────────────────────────────────────────────
def _extract_slots_from_free_form(user_id: str, user_input: str):
    state = get_user_state(user_id)
    slots = state["slots"]
    intent = slots["intent_type"]
    normalized = user_input.strip()

    # --- 1) intent_type — only if missing (None). unchanged. ---
    if intent is None:
        print("    → intent_type is missing. Calling Gemini…")
        parsed = ask_gemini("classify_intent", user_input)
        print(f"    → Gemini classify_intent returned: {parsed}")
        found_intent = parsed.get("intent_type")
        if found_intent in ["création", "mise à jour"]:
            print(f"    → Storing intent_type = {found_intent!r}")
            update_user_slot(user_id, "intent_type", found_intent)
            intent = found_intent
        else:
            print("    → Gemini did not return 'création' or 'mise à jour'. Leaving intent_type = None (unknown) and stopping.")
            return  # We do NOT proceed further; next turn user will be asked again.

    # Reload slots
    slots = get_user_state(user_id)["slots"]
    intent = slots["intent_type"]

    # --- 2) type_ent — only if missing and intent is valid. Always use Gemini’s 'match_type_ent' ---
    if intent in ["création", "mise à jour"] and slots["type_ent"] is None:
        print("    → type_ent is missing; calling Gemini for 'match_type_ent'…")
        parsed = ask_gemini("match_type_ent", user_input)
        print(f"    → Gemini returned for match_type_ent: {parsed}")
        chosen = parsed.get("type_ent", "").strip()

        # Check it against our master list (CREATION_TYPES + MISE_A_JOUR_TYPES)
        all_valid = CREATION_TYPES + MISE_A_JOUR_TYPES
        for vt in all_valid:
            if chosen.lower() == vt.lower():
                print(f"    → Storing type_ent = {vt!r}")
                update_user_slot(user_id, "type_ent", vt)
                break

        if slots["type_ent"] is None:
            print("    → Gemini’s match_type_ent not recognized in the master list.")

    # Reload slots
    slots = get_user_state(user_id)["slots"]
    intent = slots["intent_type"]
    choice = slots["needs_documents_or_penalty"]

    # --- 3) needs_documents_or_penalty — only if missing (unchanged) ---
    if slots["needs_documents_or_penalty"] is None:
        print("    → needs_documents_or_penalty is missing; calling Gemini…")
        parsed = ask_gemini("one_of_documents_or_penalty", user_input)
        print(f"    → Gemini returned for one_of_documents_or_penalty: {parsed}")
        doc_choice = parsed.get("choice", "").strip()
        if doc_choice in ["documents", "amende"]:
            print(f"    → Storing needs_documents_or_penalty = {doc_choice}")
            update_user_slot(user_id, "needs_documents_or_penalty", doc_choice)
        else:
            print("    → Gemini did not return 'documents' or 'amende'")

    # Reload slots
    slots = get_user_state(user_id)["slots"]
    intent = slots["intent_type"]
    choice = slots["needs_documents_or_penalty"]

    # --- 4) creation_date — only if 'amende' and missing (unchanged) ---
    if intent == "création" and choice == "amende" and slots["creation_date"] is None:
        print("    → creation_date is missing and choice is 'amende'; looking for date pattern…")
        date_match = re.search(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", user_input)
        if date_match:
            candidate = date_match.group(1)
            print(f"    → Found date pattern '{candidate}'; validating via Gemini…")
            parsed = ask_gemini("valid_date_string", candidate)
            print(f"    → Gemini returned for valid_date_string: {parsed}")
            if parsed.get("error") != "invalid_date":
                dt = parsed["date"]
                print(f"    → Storing creation_date = {dt}")
                update_user_slot(user_id, "creation_date", dt)
            else:
                print("    → Gemini says date is invalid.")
        else:
            print("    → No date pattern found in message.")

    # Reload slots
    slots = get_user_state(user_id)["slots"]
    intent = slots["intent_type"]

    # --- 5) update_action — only if intent == 'mise à jour' and missing (unchanged) ---
    if intent == "mise à jour" and slots["update_action"] is None:
        print("    → update_action is missing and intent is 'mise à jour'; calling Gemini…")
        parsed = ask_gemini("choose_update_action", user_input)
        print(f"    → Gemini returned for choose_update_action: {parsed}")
        action = parsed.get("update_action", "").strip()
        for ua in UPDATE_ACTIONS:
            if action.lower() == ua.lower():
                print(f"    → Storing update_action = {ua!r}")
                update_user_slot(user_id, "update_action", ua)
                break
        if slots["update_action"] is None:
            print("    → Gemini’s update_action not recognized.")
def _find_next_missing_slot(slots: dict) -> str or None:
    print("    [_find_next_missing_slot] Called with slots =", slots)
    print("    [_find_next_missing_slot] Current FLOW (type={}): {}".format(type(FLOW), FLOW))

    for idx, slot_def in enumerate(FLOW):
        print(f"      → FLOW[{idx}] is {slot_def!r} (type={type(slot_def)})")
        try:
            sk = slot_def["slot_key"]
        except Exception as e:
            print(f"        !!! ERROR: slot_def does not have 'slot_key': {e}")
            # Re‐raise so we still see the stack trace:
            raise

        cond = slot_def.get("conditional_on")
        if cond:
            if slots.get(cond["slot_key"]) != cond["equals"]:
                print(f"    → Skipping '{sk}' (condition not met: {cond})")
                continue
        if sk == "intent_type" and slots.get(sk) in [None, "unknown"]:
            print(f"    → Next missing slot: {sk}")
            return sk
        if slots.get(sk) is None:
            print(f"    → Next missing slot: {sk}")
            return sk

    print("    → No missing slots found.")
    return None

def _compute_final_answer_using_scraped_data(slots: dict) -> str:
    """
    (Unchanged) Once all slots are valid, look up scraped_data.json and return the answer.
    """
    intent = slots["intent_type"]
    type_ent = slots["type_ent"]
    choice = slots["needs_documents_or_penalty"]

    print(f"    [_compute_final_answer_using_scraped_data] intent={intent}, type_ent={type_ent}, choice={choice}")

    # 1) Find matching scraped_data entry
    matched_entry = None
    for entry in SCRAPED:
        if (
            entry["type_ent"].lower().strip() == type_ent.lower().strip()
            and entry["procedure"].lower().strip() == intent.lower().strip()
        ):
            matched_entry = entry
            break

    if not matched_entry:
        return (
            f"Désolé, je n'ai pas trouvé d'informations pour le type d'entité « {type_ent} » "
            f"et la procédure « {intent} »."
        )

    content = matched_entry["json_contents"][0]

    # 2) Documents branch
    if choice == "documents":
        docs_list = content.get("documents_demandes", [])
        if not docs_list:
            return (
                f"Désolé, je n'ai pas trouvé la liste des documents requis pour une {type_ent} en cas de {intent}."
            )
        docs_str = ", ".join(docs_list)
        return (
            f"Voici les documents requis pour une {type_ent} en cas de {intent} :\n{docs_str}"
        )

    # 3) Penalty branch
    creation_date_str = slots["creation_date"]
    try:
        dt_created = datetime.strptime(creation_date_str, "%d/%m/%Y")
    except ValueError:
        return (
            "La date fournie n'est pas valide (JJ/MM/AAAA). Merci de recommencer."
        )

    delais_text = matched_entry.get("delais", "")
    delay_days = 30
    if "15 jours" in delais_text:
        delay_days = 15
    elif "30 jours" in delais_text:
        delay_days = 30

    redevance_text = matched_entry.get("redevance", "")
    fee_match = re.search(r"(\d+)\s*dinars", redevance_text)
    if fee_match:
        base_fee = int(fee_match.group(1))
    else:
        tnd_match = re.search(r"(\d+)\s*TND", redevance_text)
        base_fee = int(tnd_match.group(1)) if tnd_match else 0

    date_due = dt_created + timedelta(days=delay_days)
    today = datetime.today()

    if today > date_due:
        days_overdue = (today - date_due).days
        daily_rate = 5
        fine = days_overdue * daily_rate
        return (
            f"La création date du {creation_date_str}. Tu as dépassé le délai de {delay_days} jours. "
            f"Tu es en retard de {days_overdue} jours. L’amende s’élève à {fine} TND.\n"
            f"(Détail pénalités : {content['observations'][0]})"
        )
    else:
        return (
            f"La création date du {creation_date_str}. Tu es dans le délai de {delay_days} jours. "
            f"Le tarif normal est de {base_fee} TND.\n"
            f"(Délai légal : {delais_text})"
        )
