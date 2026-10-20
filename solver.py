"""Deterministic solvers for the DSO 429 hourly-quiz question templates.

Each solver parses the numbers out of the question and computes the exact
answer; the option closest to that value is picked. A question no solver
recognises (or whose answer matches no option) raises Unsolved.
"""

import math
import re
from datetime import datetime, timedelta

NUM = r"(-?[\d,]*\.?\d+)"


class Unsolved(Exception):
    pass


def num(s):
    return float(s.replace(",", "").replace("$", "").replace("%", "").strip())


def parse_option(s):
    s = s.strip()
    try:
        return datetime.strptime(s, "%d %B %Y")
    except ValueError:
        pass
    m = re.search(r"-?[\d,]*\.?\d+", s.replace("$", ""))
    if not m:
        raise Unsolved(f"cannot parse option {s!r}")
    return num(m.group())


SOLVERS = []


def solver(pattern):
    def wrap(fn):
        SOLVERS.append((re.compile(pattern, re.I | re.S), fn))
        return fn
    return wrap


@solver(r"\$" + NUM + r" grows at " + NUM + r"% compounded (annually|semi-annually|quarterly|monthly|daily).*?after " + NUM + r" years?")
def compound(m, t):
    p, r, freq, y = num(m[1]), num(m[2]) / 100, m[3].lower(), num(m[4])
    n = {"annually": 1, "semi-annually": 2, "quarterly": 4, "monthly": 12, "daily": 365}[freq]
    return p * (1 + r / n) ** (n * y)


@solver(r"\$" + NUM + r" in revenue against \$" + NUM + r" in cost of goods sold.*gross margin")
def gross_margin(m, t):
    rev, cogs = num(m[1]), num(m[2])
    return (rev - cogs) / rev * 100


@solver(r"series runs ([\d.,\s-]+?)\. If the pattern continues")
def series(m, t):
    xs = [num(x) for x in re.split(r",\s*", m[1].strip())]
    d = [b - a for a, b in zip(xs, xs[1:])]
    if all(abs(x - d[0]) < 1e-9 for x in d):
        return xs[-1] + d[0]
    rs = [b / a for a, b in zip(xs, xs[1:]) if a]
    if len(rs) == len(xs) - 1 and all(abs(x - rs[0]) < 1e-9 for x in rs):
        return xs[-1] * rs[0]
    dd = [b - a for a, b in zip(d, d[1:])]
    if dd and all(abs(x - dd[0]) < 1e-9 for x in dd):
        return xs[-1] + d[-1] + dd[0]
    raise Unsolved("unknown series pattern")


@solver(r"listed at \$" + NUM + r" is discounted by " + NUM + r"%.*sale price")
def discount(m, t):
    return num(m[1]) * (1 - num(m[2]) / 100)


@solver(r"moved from \$?" + NUM + r" to \$?" + NUM + r".*percentage change")
def pct_change(m, t):
    a, b = num(m[1]), num(m[2])
    return (b - a) / a * 100


@solver(r"signed on (\d{1,2} \w+ \d{4}) has an? " + NUM + r"-day settlement period")
def settle(m, t):
    return datetime.strptime(m[1], "%d %B %Y") + timedelta(days=int(num(m[2])))


@solver(r"Fixed costs are \$" + NUM + r"\. Each unit sells for \$" + NUM + r" with a variable cost of \$" + NUM)
def breakeven(m, t):
    f, p, v = num(m[1]), num(m[2]), num(m[3])
    return f / (p - v)


@solver(r"\$" + NUM + r" .*? split between \w+ \w+ in the ratio " + NUM + r":" + NUM + r"\. What does the (first|second) \w+ receive")
def ratio(m, t):
    total, a, b = num(m[1]), num(m[2]), num(m[3])
    return total * (a if m[4].lower() == "first" else b) / (a + b)


@solver(r"had " + NUM + r" orders averaging \$" + NUM + r"; region B had " + NUM + r" orders averaging \$" + NUM)
def weighted_avg(m, t):
    n1, a1, n2, a2 = map(num, (m[1], m[2], m[3], m[4]))
    return (n1 * a1 + n2 * a2) / (n1 + n2)


@solver(r"\$" + NUM + r" is converted to euros at " + NUM + r" euros per US dollar")
def fx(m, t):
    return num(m[1]) * num(m[2])


@solver(r"holds (.+?)\. If one is drawn at random, what is the probability it is an? (\w+) ticket")
def probability(m, t):
    parts = {k.lower(): num(v) for v, k in re.findall(NUM + r" (\w+) tickets?", m[1])}
    want = m[2].lower()
    if want not in parts:
        raise Unsolved("ticket category not found")
    return parts[want] / sum(parts.values()) * 100


@solver(r"sells " + NUM + r" units at \$" + NUM + r" each.*total revenue")
def revenue(m, t):
    return num(m[1]) * num(m[2])


def solve_value(text):
    for pat, fn in SOLVERS:
        m = pat.search(text)
        if m:
            return fn.__name__, fn(m, text)
    raise Unsolved("no matching template")


def pick(value, options):
    """Letter of the option closest to value, and whether it is a confident match."""
    parsed = [parse_option(o) for o in options]
    if isinstance(value, datetime):
        diffs = [abs((p - value).days) if isinstance(p, datetime) else 1e18 for p in parsed]
        ok = min(diffs) == 0
    else:
        diffs = [abs(p - value) if not isinstance(p, datetime) else 1e18 for p in parsed]
        ok = min(diffs) <= max(0.51, abs(value) * 0.002)
    best = min(range(4), key=lambda i: diffs[i])
    return "ABCD"[best], ok


def solve(text, options):
    name, value = solve_value(text)
    letter, ok = pick(value, options)
    if not ok:
        raise Unsolved(f"{name}: computed {value} matches no option {options}")
    return letter
