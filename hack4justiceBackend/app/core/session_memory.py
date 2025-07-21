# app/core/session_memory.py

user_sessions = {}

def get_user_state(user_id: str) -> dict:
    """
    Initialize or retrieve the session for user_id:
      {
        "slots": {
          "intent_type": None,
          "type_ent": None,
          "needs_documents_or_penalty": None,
          "creation_date": None,
          "update_action": None      # ← add this line
        },
        "awaiting_slot": None
      }
    """
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            "slots": {
                "intent_type": None,
                "type_ent": None,
                "needs_documents_or_penalty": None,
                "creation_date": None,
                "update_action": None
            },
            "awaiting_slot": None
        }
    return user_sessions[user_id]

def update_user_slot(user_id: str, slot_key: str, slot_value):
    """
    Store slot_value in the user’s session and clear awaiting_slot.
    """
    state = get_user_state(user_id)
    state["slots"][slot_key] = slot_value
    state["awaiting_slot"] = None

def set_awaiting_slot(user_id: str, slot_key: str):
    """Mark that we just asked a question about slot_key."""
    state = get_user_state(user_id)
    state["awaiting_slot"] = slot_key

def reset_session(user_id: str):
    """Delete the user’s session so they start fresh next time."""
    if user_id in user_sessions:
        del user_sessions[user_id]
