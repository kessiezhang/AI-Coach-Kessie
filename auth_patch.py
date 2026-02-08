"""
Patch for Authlib FrameworkIntegration when session is None (Streamlit/Tornado).
Streamlit passes session=None; base FrameworkIntegration does session[key]=... which fails.
"""
import json
import time

from authlib.integrations.base_client import framework_integration

def _patched_set_state_data(self, session, state, data):
    key = f"_state_{self.name}_{state}"
    now = time.time()
    if self.cache:
        self.cache.set(key, json.dumps({"data": data}), self.expires_in)
        if session is not None:
            session[key] = {"exp": now + self.expires_in}
    else:
        if session is not None:
            session[key] = {"data": data, "exp": now + self.expires_in}


def _patched_get_state_data(self, session, state):
    key = f"_state_{self.name}_{state}"
    if session is not None:
        session_data = session.get(key)
    else:
        session_data = None
    if not session_data and self.cache:
        cached = self.cache.get(key)
        if cached:
            try:
                session_data = json.loads(cached)
            except (TypeError, ValueError):
                pass
    elif not session_data:
        return None
    if session_data:
        return session_data.get("data")
    return None


def _patched_clear_state_data(self, session, state):
    key = f"_state_{self.name}_{state}"
    if self.cache:
        self.cache.delete(key)
    if session is not None:
        session.pop(key, None)
        self._clear_session_state(session)


def apply():
    framework_integration.FrameworkIntegration.set_state_data = _patched_set_state_data
    framework_integration.FrameworkIntegration.get_state_data = _patched_get_state_data
    framework_integration.FrameworkIntegration.clear_state_data = _patched_clear_state_data
