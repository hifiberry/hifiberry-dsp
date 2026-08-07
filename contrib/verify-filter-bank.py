#!/usr/bin/env python3
"""
Verify that filter writes actually reached DSP memory.

A 200 response from the REST API and a correct dspsettings.json prove only
that the server *thinks* it wrote the filters. This reads the DSP memory back
and compares it against the coefficients the server reported, which is the
only check that catches a half-applied bank (hifiberry-os#626).

Runs ON the device against localhost:13141 -- that listener has no auth
gateway in front of it. Standard library only, so it needs nothing installed.

    scp contrib/verify-filter-bank.py matuschd@beocreate.local:/tmp/
    ssh matuschd@beocreate.local 'python3 /tmp/verify-filter-bank.py fill --bank customFilterRegisterBankLeft'

Memory layout: write_biquad() writes from the highest address down, so the
five ascending cells of a slot read back as [b2, b1, b0, -a2, -a1], all
normalised by a0.
"""

import argparse
import json
import sys
import threading
import urllib.error
import urllib.request

BASE_URL = "http://localhost:13141"
CELLS_PER_SLOT = 5
# 8.24 fixed point: LSB is ~5.96e-8, so anything above 1e-6 is a real mismatch.
TOLERANCE = 1e-6
TRANSPARENT = {"a0": 1.0, "a1": 0.0, "a2": 0.0, "b0": 1.0, "b1": 0.0, "b2": 0.0}


def request(method, path, payload=None, timeout=30):
    url = BASE_URL + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data:
        req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return e.code, json.loads(body)
        except ValueError:
            return e.code, {"error": body}


def bank_layout(bank_key):
    """Resolve a bank's base address and slot count from /metadata ('329/80')."""
    status, metadata = request('GET', '/metadata')
    if status != 200:
        raise SystemExit(f"could not read metadata: HTTP {status}")
    if bank_key not in metadata:
        raise SystemExit(f"no such bank in metadata: {bank_key}")
    base, _, cells = str(metadata[bank_key]).partition('/')
    sample_rate = metadata.get('_system', {}).get('sampleRate', 48000)
    return int(base), int(cells) // CELLS_PER_SLOT, sample_rate


def expected_cells(coefficients):
    """Server-reported coefficients -> the five cells, in ascending address order."""
    a0 = float(coefficients['a0'])
    if a0 == 0:
        raise ValueError("a0 is zero, cannot normalise")
    return [
        float(coefficients['b2']) / a0,
        float(coefficients['b1']) / a0,
        float(coefficients['b0']) / a0,
        -float(coefficients['a2']) / a0,
        -float(coefficients['a1']) / a0,
    ]


def read_slot(base_address, offset):
    address = base_address + offset * CELLS_PER_SLOT
    status, body = request('GET', f'/memory/{address}/{CELLS_PER_SLOT}?format=float')
    if status != 200:
        raise SystemExit(f"memory read failed at {address}: HTTP {status} {body}")
    return body['values']


def a_filter(offset):
    """A distinct filter per slot, so a swapped or skipped slot is detectable."""
    return {"type": "PeakingEq", "f": 100 + offset * 137, "db": -3.0 - offset * 0.1, "q": 1.0}


def write_bank_individually(bank_key, base_address, slots, sample_rate):
    reported = {}
    for offset in range(slots):
        status, body = request('POST', '/biquad', {
            "address": bank_key, "offset": offset,
            "sampleRate": sample_rate, "filter": a_filter(offset)})
        if status != 200:
            raise SystemExit(f"write failed at offset {offset}: HTTP {status} {body}")
        reported[offset] = body['coefficients']
    return reported


def write_bank_bulk(bank_key, base_address, slots, sample_rate):
    status, body = request('POST', '/filters/bank', {
        "address": bank_key, "sampleRate": sample_rate,
        "filters": [{"offset": o, "filter": a_filter(o)} for o in range(slots)]})
    if status == 404:
        raise SystemExit("this device has no POST /filters/bank endpoint")
    if status != 200:
        raise SystemExit(f"bank write failed: HTTP {status} {body}")
    return {entry['offset']: entry['coefficients'] for entry in body['results']}


def verify(bank_key, base_address, slots, reported):
    """Compare DSP memory against what the server said it wrote."""
    failures = []
    for offset in range(slots):
        actual = read_slot(base_address, offset)
        if offset not in reported:
            failures.append(f"offset {offset}: server never reported writing this slot")
            continue
        wanted = expected_cells(reported[offset])
        for cell, (got, want) in enumerate(zip(actual, wanted)):
            if abs(got - want) > TOLERANCE:
                failures.append(
                    f"offset {offset} cell {cell}: DSP has {got!r}, server wrote {want!r}")
        if actual == [0.0, 0.0, 1.0, 0.0, 0.0] and wanted != [0.0, 0.0, 1.0, 0.0, 0.0]:
            failures.append(f"offset {offset}: slot is still a transparent pass-through")
    return failures


def report(bank_key, slots, failures):
    if failures:
        print(f"FAIL {bank_key}: {len(failures)} mismatch(es) across {slots} slots")
        for line in failures:
            print(f"  {line}")
        return 1
    print(f"OK   {bank_key}: all {slots} slots match DSP memory")
    return 0


def cmd_fill(args):
    base_address, slots, sample_rate = bank_layout(args.bank)
    writer = write_bank_bulk if args.bulk else write_bank_individually
    reported = writer(args.bank, base_address, slots, sample_rate)
    return report(args.bank, slots, verify(args.bank, base_address, slots, reported))


def cmd_read(args):
    base_address, slots, _ = bank_layout(args.bank)
    for offset in range(slots):
        values = read_slot(base_address, offset)
        marker = "transparent" if values == [0.0, 0.0, 1.0, 0.0, 0.0] else ""
        print(f"{args.bank}[{offset:2d}] @ {base_address + offset * CELLS_PER_SLOT}: {values} {marker}")
    return 0


def cmd_soak(args):
    base_address, slots, sample_rate = bank_layout(args.bank)
    errors = []
    reported = {}
    lock = threading.Lock()

    def worker():
        try:
            written = (write_bank_bulk if args.bulk else write_bank_individually)(
                args.bank, base_address, slots, sample_rate)
            with lock:
                reported.update(written)
        except SystemExit as e:
            with lock:
                errors.append(str(e))

    threads = [threading.Thread(target=worker) for _ in range(args.threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    if errors:
        print(f"FAIL {args.bank}: {len(errors)} writer(s) errored")
        for line in errors:
            print(f"  {line}")
        return 1

    # Every writer sends identical filters, so any surviving slot must match.
    return report(args.bank, slots, verify(args.bank, base_address, slots, reported))


def cmd_compare(args):
    """
    Verify a bank pair that something else wrote -- the web UI, typically.

    Without the server's reported coefficients there is nothing to compare a
    single bank against, but the two symptoms of #626 are both visible from
    the memory alone: the channels disagree, or slots were left transparent.
    """
    if len(args.bank) != 2:
        raise SystemExit("compare needs exactly two --bank arguments")

    banks = []
    for bank_key in args.bank:
        base_address, slots, _ = bank_layout(bank_key)
        banks.append((bank_key, [read_slot(base_address, o) for o in range(slots)]))

    (left_key, left), (right_key, right) = banks
    failures = []

    if len(left) != len(right):
        failures.append(f"{left_key} has {len(left)} slots, {right_key} has {len(right)}")

    for offset, (l_cells, r_cells) in enumerate(zip(left, right)):
        for cell, (l, r) in enumerate(zip(l_cells, r_cells)):
            if abs(l - r) > TOLERANCE:
                failures.append(
                    f"offset {offset} cell {cell}: {left_key}={l!r} but {right_key}={r!r}")

    transparent = [o for o, cells in enumerate(left) if cells == [0.0, 0.0, 1.0, 0.0, 0.0]]
    filled = len(left) - len(transparent)
    if filled < args.expect_slots:
        failures.append(
            f"only {filled} of {len(left)} slots are filled, expected at least "
            f"{args.expect_slots} (transparent at offsets {transparent})")

    if failures:
        print(f"FAIL {left_key} vs {right_key}: {len(failures)} problem(s)")
        for line in failures:
            print(f"  {line}")
        return 1
    print(f"OK   {left_key} and {right_key} are identical, {filled} slots filled")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)

    for name, handler in (('fill', cmd_fill), ('read', cmd_read), ('soak', cmd_soak)):
        p = sub.add_parser(name)
        p.add_argument('--bank', required=True, help='bank metadata key')
        p.set_defaults(handler=handler)
        if name != 'read':
            p.add_argument('--bulk', action='store_true',
                           help='use POST /filters/bank instead of one POST /biquad per slot')
        if name == 'soak':
            p.add_argument('--threads', type=int, default=4)

    compare = sub.add_parser('compare')
    compare.add_argument('--bank', required=True, action='append',
                         help='bank metadata key; pass twice')
    compare.add_argument('--expect-slots', type=int, default=1,
                         help='minimum number of non-transparent slots expected')
    compare.set_defaults(handler=cmd_compare)

    args = parser.parse_args()
    try:
        return args.handler(args)
    except SystemExit as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
