# src/contracts/versioning.py
from dataclasses import dataclass
CURRENT_CONTRACT_VERSION="qapp-v1.0"; CURRENT_ENGINE_VERSION="2.0"; CURRENT_RUNTIME_VERSION="1.0.0"
@dataclass(frozen=True)
class ContractVersion:
    major:int; minor:int; patch:int; label:str=""
    @staticmethod
    def parse(v):
        try:
            clean=v.lstrip("v").lstrip("qapp-v"); parts=clean.split(".")
            return ContractVersion(major=int(parts[0]) if len(parts)>0 else 0,minor=int(parts[1]) if len(parts)>1 else 0,patch=int(parts[2]) if len(parts)>2 else 0,label=v)
        except: return ContractVersion(0,0,0,v)
    def is_compatible_with(self,other): return self.major==other.major
    def __str__(self): return self.label or f"{self.major}.{self.minor}.{self.patch}"
def check_version_compatibility(producer,consumer):
    p=ContractVersion.parse(producer); c=ContractVersion.parse(consumer)
    compatible=p.is_compatible_with(c)
    return {"compatible":compatible,"producer_version":producer,"consumer_version":consumer,"reason":"Major versions match" if compatible else f"Major version mismatch: {p.major} vs {c.major}"}
def get_version_manifest():
    return {"contract_version":CURRENT_CONTRACT_VERSION,"engine_version":CURRENT_ENGINE_VERSION,"runtime_version":CURRENT_RUNTIME_VERSION,"schema":"engine_event_v2.0"}
