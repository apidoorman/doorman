import json
import sys
from pathlib import Path

REGRESSION_THRESHOLD = 0.10

def load_summary(path: Path):
    with path.open('r', encoding='utf-8') as f:
        return json.load(f)

def extract_metrics(summary: dict):
    m = summary.get('metrics', {})
    http = m.get('http_req_duration', {}).get('values', {})
    http_reqs = m.get('http_reqs', {}).get('values', {})
    p50 = float(http.get('p(50)', 0.0))
    p95 = float(http.get('p(95)', 0.0))
    p99 = float(http.get('p(99)', 0.0))
    rps = float(http_reqs.get('rate', 0.0))
    return {
        'p50': p50,
        'p95': p95,
        'p99': p99,
        'rps': rps,
    }

def main():
    if len(sys.argv) < 3:
        print('Usage: compare_perf.py <current_summary.json> <baseline_summary.json>')
        sys.exit(2)
    current = Path(sys.argv[1])
    baseline = Path(sys.argv[2])
    if not current.exists():
        print(f'Current summary not found: {current}')
        sys.exit(2)
    if not baseline.exists():
        print(f'Baseline summary not found: {baseline}')
        sys.exit(2)

    cur = load_summary(current)
    base = load_summary(baseline)
    curm = extract_metrics(cur)
    basem = extract_metrics(base)

    print('Baseline metrics:')
    print(f"  p50={basem['p50']:.2f}ms  p95={basem['p95']:.2f}ms  p99={basem['p99']:.2f}ms  rps={basem['rps']:.2f}")
    print('Current metrics:')
    print(f"  p50={curm['p50']:.2f}ms  p95={curm['p95']:.2f}ms  p99={curm['p99']:.2f}ms  rps={curm['rps']:.2f}")

    failures = []
    for q in ('p50', 'p95', 'p99'):
        base_v = basem[q]
        cur_v = curm[q]
        if base_v > 0:
            allowed = base_v * (1.0 + REGRESSION_THRESHOLD)
            if cur_v > allowed:
                failures.append(f"{q} regression: {cur_v:.2f}ms > {allowed:.2f}ms (baseline {base_v:.2f}ms)")

    base_rps = basem['rps']
    cur_rps = curm['rps']
    if base_rps > 0:
        allowed_rps = base_rps * (1.0 - REGRESSION_THRESHOLD)
        if cur_rps < allowed_rps:
            failures.append(f'RPS regression: {cur_rps:.2f} < {allowed_rps:.2f} (baseline {base_rps:.2f})')

    try:
        cur_stats = (current.parent / 'perf-stats.json')
        base_stats = (baseline.parent / 'perf-stats.json')
        if cur_stats.exists() and base_stats.exists():
            cstats = load_summary(cur_stats)
            bstats = load_summary(base_stats)
            for key in ('cpu_percent', 'loop_lag_ms_p95'):
                if key in cstats and key in bstats:
                    print(f"{key}: baseline={bstats[key]} current={cstats[key]}")

    except Exception:
        pass

    if failures:
        print('Perf regression detected:')
        for f in failures:
            print(f'- {f}')
        sys.exit(1)
    print('Performance within regression thresholds.')

if __name__ == '__main__':
    main()
