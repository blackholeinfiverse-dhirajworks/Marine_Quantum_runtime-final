# src/invoke_runtime.py
# Central runtime invocation surface.
#
# PUBLIC API:
#   invoke_runtime(module_name: str, payload: dict) -> dict
#
# Supported modules:
#   signal             → src/signal/signal_generator.run()
#   quantum_pipeline   → src/quantum/execution.run()
#   distributed_qapp   → src/runtime/distributed_qapp_runner.run()
#   operational_monitor → src/monitoring/operational_drift_monitor.run()
#
# Each module exposes: run(payload) -> structured_result
# This file is the SOLE gateway between caller and module.

SUPPORTED_MODULES = [
    "signal",
    "quantum_pipeline",
    "distributed_qapp",
    "operational_monitor",
]


def invoke_runtime(module_name: str, payload: dict) -> dict:
    """
    Invoke a runtime module by name with a payload.

    Args:
        module_name : str  — one of SUPPORTED_MODULES
        payload     : dict — module-specific input

    Returns:
        dict with keys: module, status, result, error
    """
    if module_name not in SUPPORTED_MODULES:
        return {
            "module":  module_name,
            "status":  "MODULE_NOT_FOUND",
            "result":  None,
            "error":   f"Unknown module '{module_name}'. Supported: {SUPPORTED_MODULES}",
        }

    try:
        if module_name == "signal":
            from src.signal.signal_generator import run
            return run(payload)

        elif module_name == "quantum_pipeline":
            from src.quantum.execution import run
            return run(payload)

        elif module_name == "distributed_qapp":
            from src.runtime.distributed_qapp_runner import run
            return run(payload)

        elif module_name == "operational_monitor":
            from src.monitoring.operational_drift_monitor import run
            return run(payload)

    except ImportError as exc:
        return {
            "module":  module_name,
            "status":  "IMPORT_ERROR",
            "result":  None,
            "error":   str(exc),
        }
    except Exception as exc:
        return {
            "module":  module_name,
            "status":  "RUNTIME_ERROR",
            "result":  None,
            "error":   str(exc),
        }


def list_modules() -> list:
    return list(SUPPORTED_MODULES)


def module_status() -> dict:
    status = {}
    for mod in SUPPORTED_MODULES:
        try:
            if mod == "signal":
                from src.signal.signal_generator import run
            elif mod == "quantum_pipeline":
                from src.quantum.execution import run
            elif mod == "distributed_qapp":
                from src.runtime.distributed_qapp_runner import run
            elif mod == "operational_monitor":
                from src.monitoring.operational_drift_monitor import run
            status[mod] = "AVAILABLE"
        except ImportError as e:
            status[mod] = f"IMPORT_ERROR: {e}"
        except Exception as e:
            status[mod] = f"ERROR: {e}"
    return status
