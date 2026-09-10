# src/quantum/algorithm.py
import math, random
NUM_QUBITS=6; NUM_LAYERS=2
def simulate_circuit_classically(normalized_angles, seed=42):
    rng=random.Random(seed); angles=list(normalized_angles.values())
    dominant_weight=sum(angles)/(math.pi*NUM_QUBITS)
    dominant_state="".join(str(int(a>math.pi/2)) for a in angles)
    states=[dominant_state]
    for _ in range(7):
        flipped=list(dominant_state); idx=rng.randint(0,NUM_QUBITS-1)
        flipped[idx]="1" if flipped[idx]=="0" else "0"; states.append("".join(flipped))
    weights=[dominant_weight]+[rng.uniform(0.02,0.15) for _ in range(7)]
    total=sum(weights); dist={s:round(w/total,6) for s,w in zip(states,weights)}
    dist[dominant_state]=round(1.0-sum(v for k,v in dist.items() if k!=dominant_state),6)
    return {"measurement_distribution":dist,"dominant_state":dominant_state,"shots_used":4096,"seed":seed,"simulation_type":"classical_deterministic_stub"}
