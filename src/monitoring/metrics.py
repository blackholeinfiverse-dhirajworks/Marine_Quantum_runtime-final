# src/monitoring/metrics.py
import hashlib, json
from dataclasses import dataclass
@dataclass
class RuntimeMetrics:
    total_signal_events:int=0; total_converged:int=0; total_suspended:int=0
    total_diverged:int=0; total_validation_errors:int=0; total_drift_events:int=0
    total_propagations:int=0; consensus_checks:int=0; divergence_count:int=0
    @property
    def convergence_rate(self):
        t=self.total_converged+self.total_suspended+self.total_diverged
        return round(self.total_converged/t,4) if t>0 else 0.0
    def to_dict(self): return {"total_signal_events":self.total_signal_events,"total_converged":self.total_converged,"total_suspended":self.total_suspended,"total_diverged":self.total_diverged,"total_validation_errors":self.total_validation_errors,"total_drift_events":self.total_drift_events,"convergence_rate":self.convergence_rate}
