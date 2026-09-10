# src/monitoring/persistence.py
import hashlib, json
from typing import List
_EVENT_LOG=[]; _LOG_HASH="0"*64
def _sha256(d): return hashlib.sha256(d.encode()).hexdigest()
def append_event(event):
    global _LOG_HASH
    canonical=json.dumps(event,sort_keys=True,separators=(",",":")
    ); entry_hash=_sha256(f"{_LOG_HASH}:{canonical}"); _EVENT_LOG.append({**event,"_entry_hash":entry_hash}); _LOG_HASH=entry_hash; return entry_hash
def get_log(): return list(_EVENT_LOG)
def get_log_hash(): return _LOG_HASH
def get_event_count(): return len(_EVENT_LOG)
def clear_log():
    global _LOG_HASH; _EVENT_LOG.clear(); _LOG_HASH="0"*64
def log_summary():
    states={}
    for e in _EVENT_LOG:
        s=e.get("transition",{}).get("next","UNKNOWN"); states[s]=states.get(s,0)+1
    return {"total_events":len(_EVENT_LOG),"log_hash":_LOG_HASH,"state_counts":states}
