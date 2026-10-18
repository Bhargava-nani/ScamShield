"""Small, bounded, in-process rate limiter for Flask endpoints.

For multi-worker or public production deployments, enforce rate limits at
the reverse proxy/API gateway too. This limiter does not trust forwarded-IP
headers supplied by clients.
"""

from collections import deque
from functools import wraps
from math import ceil
from threading import Lock
from time import monotonic

from flask import jsonify, request


def rate_limit(limit=20, window_seconds=60, max_clients=5000):
    """Allow at most `limit` requests per client during each time window."""
    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or limit < 1
        or isinstance(window_seconds, bool)
        or not isinstance(window_seconds, (int, float))
        or window_seconds <= 0
        or isinstance(max_clients, bool)
        or not isinstance(max_clients, int)
        or max_clients < 1
    ):
        raise ValueError("Invalid rate-limit configuration.")

    requests_by_client = {}
    lock = Lock()

    def decorate(view_function):
        @wraps(view_function)
        def wrapped(*args, **kwargs):
            now = monotonic()
            client = request.remote_addr or "unknown"

            with lock:
                timestamps = requests_by_client.get(client)

                if timestamps is None:
                    if len(requests_by_client) >= max_clients:
                        # Remove expired clients before accepting a new key.
                        expired_clients = [
                            key for key, values in requests_by_client.items()
                            if not values or now - values[-1] >= window_seconds
                        ]
                        for key in expired_clients:
                            requests_by_client.pop(key, None)

                    if len(requests_by_client) >= max_clients:
                        response = jsonify({
                            "error": "Request capacity is temporarily limited. Try again shortly."
                        })
                        response.status_code = 429
                        response.headers["Retry-After"] = str(
                            max(1, ceil(window_seconds))
                        )
                        return response

                    timestamps = deque()
                    requests_by_client[client] = timestamps

                while timestamps and now - timestamps[0] >= window_seconds:
                    timestamps.popleft()

                if len(timestamps) >= limit:
                    retry_after = max(
                        1,
                        ceil(window_seconds - (now - timestamps[0])),
                    )
                    response = jsonify({
                        "error": "Too many requests. Please wait before trying again."
                    })
                    response.status_code = 429
                    response.headers["Retry-After"] = str(retry_after)
                    return response

                timestamps.append(now)

            return view_function(*args, **kwargs)

        return wrapped

    return decorate
