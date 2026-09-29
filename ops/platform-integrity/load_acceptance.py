#!/usr/bin/env python3
"""Read-only native mTLS load acceptance. Failure responses never count as normal throughput."""

import argparse
import concurrent.futures
import json
import math
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def percentile(samples, fraction):
    return sorted(samples)[max(0, math.ceil(len(samples) * fraction) - 1)] if samples else None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, newurl):
        raise urllib.error.HTTPError(newurl, code, "redirect forbidden", headers, response)


def measure(base, subject, context, *, seconds=600, rps=5):
    if base != "https://127.0.0.1:18101":
        raise ValueError("only the isolated native test listener on 127.0.0.1:18101 is accepted")
    if (
        type(seconds) is not int or type(rps) is not int
        or not (1 <= seconds <= 600 and 1 <= rps <= 20)
    ):
        raise ValueError("bounded load profile required")
    expected = seconds * rps
    metadata, health, failures = [], [], []

    admissions = threading.BoundedSemaphore(10)

    def request(index, scheduled):
        kind = "health" if index % 5 == 0 else "metadata"
        path = (
            "/healthz" if kind == "health"
            else "/internal/v1/evidence/" + urllib.parse.quote(subject, safe="")
        )
        try:
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=context),
                NoRedirect(),
            )
            with opener.open(base + path, timeout=3) as response:
                data = bytearray()
                while len(data) <= 1024**2:
                    if time.monotonic() - scheduled >= 3:
                        raise TimeoutError("total request deadline")
                    chunk = response.read1(min(65536, 1024**2 + 1 - len(data)))
                    if not chunk:
                        break
                    data.extend(chunk)
                if len(data) > 1024**2 or response.status != 200:
                    raise ValueError("response contract failed")
                body = json.loads(data)
                valid = (
                    body.get("alive") is True if kind == "health"
                    else body.get("verdict") in {"ELIGIBLE", "ELIGIBLE_WITH_EXCEPTIONS"}
                )
                if not valid:
                    raise ValueError("normal-path subject is not eligible")
            return kind, (time.monotonic() - scheduled) * 1000, None
        except Exception as error:
            return kind, (time.monotonic() - scheduled) * 1000, type(error).__name__
        finally:
            admissions.release()

    started = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        pending = []
        for index in range(expected):
            scheduled = started + index / rps
            time.sleep(max(0, scheduled - time.monotonic()))
            if admissions.acquire(blocking=False):
                pending.append(pool.submit(request, index, scheduled))
            else:
                kind = "health" if index % 5 == 0 else "metadata"
                failures.append({"kind": kind, "error": "LoadGeneratorSaturated"})
        for future in pending:
            kind, elapsed, error = future.result()
            if error:
                failures.append({"kind": kind, "error": error})
            elif kind == "health":
                health.append(elapsed)
            else:
                metadata.append(elapsed)
    duration = time.monotonic() - started
    normal = not failures and len(metadata) + len(health) == expected and duration <= seconds + 3
    passed = (
        normal and metadata and health
        and percentile(metadata, .95) <= 250 and percentile(health, .95) <= 100
    )
    return {"state": "MEASURED_PASS" if passed else "BLOCKED", "requests": expected,
            "successes": len(metadata) + len(health), "failures": failures,
            "metadataP95Ms": percentile(metadata, .95), "healthP95Ms": percentile(health, .95),
            "durationSeconds": duration, "profileComplete": seconds == 600 and rps == 5,
            "nativeProviderAndRssAcceptanceRequired": True}




def observe_resources(pid, observation, stop, *, sampler=None, interval=1.0):
    """Sample the listener's process tree until ``stop`` is set. Returns the count of samples."""
    from docsuri_ops.adapters.backup import ProcessTreeSampler  # noqa: F401  (import guard)

    sampler = sampler or ProcessTreeSampler()
    taken = 0
    while stop is None or not stop.is_set():
        try:
            observation.observe(sampler.sample(pid).total_rss_bytes(), pid=pid)
            taken += 1
        except Exception:
            observation.sample_failures += 1
        if stop is not None and stop.wait(interval):
            break
        elif stop is None:
            time.sleep(interval)
    return taken


def combine(result, rss, side_effects, *, dependency_observed):
    """A latency pass alone is not acceptance."""
    from docsuri_ops.load_observation import LoadVerdict

    verdict = LoadVerdict(
        latency_state=result["state"],
        profile_complete=bool(result["profileComplete"]),
        rss=rss,
        side_effects=side_effects,
        dependency_observed=dependency_observed,
    )
    payload = dict(result)
    payload.pop("nativeProviderAndRssAcceptanceRequired", None)
    payload["acceptance"] = verdict.as_dict()
    return payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="https://127.0.0.1:18101")
    parser.add_argument("--subject", required=True)
    parser.add_argument("--ca", required=True)
    parser.add_argument("--certificate", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seconds", type=int, default=600)
    parser.add_argument("--rps", type=int, default=5)
    parser.add_argument("--listener-pid", type=int,
                        help="PID of the native listener, to observe its process-tree RSS")
    parser.add_argument("--rss-budget-mib", type=int, default=512)
    parser.add_argument("--lru-budget-mib", type=int, default=64)
    parser.add_argument("--dependency-state",
                        help="JSON snapshot of read-side state taken after the run")
    parser.add_argument("--dependency-state-before")
    args = parser.parse_args()
    context = ssl.create_default_context(cafile=args.ca)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(args.certificate, args.key)

    from docsuri_ops.load_observation import RssBudget, RssObservation, verify_no_side_effects

    rss = RssObservation(budget=RssBudget(
        total_bytes=args.rss_budget_mib << 20, lru_bytes=args.lru_budget_mib << 20))

    stop = threading.Event()
    watcher = None
    if args.listener_pid is not None:
        watcher = threading.Thread(
            target=observe_resources,
            args=(args.listener_pid, rss, stop), daemon=True,
        )
        watcher.start()

    try:
        result = measure(args.url, args.subject, context,
                         seconds=args.seconds, rps=args.rps)
    finally:
        stop.set()
        if watcher is not None:
            watcher.join(timeout=5)

    side_effects = {"state": "INCOMPLETE", "reason": "no_probe_supplied"}
    dependency_observed = False
    if args.dependency_state:
        class _JsonProbe:
            def __init__(self, path):
                self.path = Path(path)

            def counts(self):
                return json.loads(self.path.read_text())

        probe = _JsonProbe(args.dependency_state)
        before = (json.loads(Path(args.dependency_state_before).read_text())
                  if args.dependency_state_before else None)
        side_effects = verify_no_side_effects(probe, before=before)
        dependency_observed = True

    payload = combine(result, rss, side_effects, dependency_observed=dependency_observed)
    with args.output.open("x") as output:
        json.dump(payload, output, indent=2)
    print(json.dumps(payload, indent=2))
    return 0 if payload["acceptance"]["state"] == "ACCEPTED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
