import time, functools

def log_node(node_name: str):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(state, *args, **kwargs):
            start = time.time()
            result = fn(state, *args, **kwargs)
            elapsed_ms = round((time.time() - start) * 1000, 1)

            entry = {"node": node_name, "latency_ms": elapsed_ms}
            for key, val in result.items():
                if isinstance(val, list):
                    entry[f"{key}_count"] = len(val)

            result["debug_log"] = [entry]
            return result
        return wrapper
    return decorator