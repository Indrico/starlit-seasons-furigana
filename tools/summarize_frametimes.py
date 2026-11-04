"""Summarize PresentMon --v1_metrics CSVs without exposing raw process data."""
import argparse
import csv
import json
import math
from pathlib import Path


def summarize(path):
    with Path(path).open(newline='', encoding='utf-8-sig') as stream:
        rows = list(csv.DictReader(stream))
    values = sorted(float(row['msBetweenPresents']) for row in rows
                    if float(row['msBetweenPresents']) > 0)
    if not values:
        raise ValueError(f'No positive frame intervals: {path}')
    def percentile(p):
        return round(values[max(0, math.ceil(len(values) * p) - 1)], 3)
    return {'capture': Path(path).name, 'frames': len(values),
            'p50_ms': percentile(.5), 'p95_ms': percentile(.95),
            'p99_ms': percentile(.99), 'max_ms': round(values[-1], 3),
            'over_33ms': sum(value > 1000 / 30 for value in values),
            'over_50ms': sum(value > 50 for value in values)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('captures', nargs='+', type=Path)
    args = parser.parse_args()
    print(json.dumps([summarize(path) for path in args.captures], indent=2))
