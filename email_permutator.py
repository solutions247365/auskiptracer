#!/usr/bin/env python3
"""
Email permutator: builds every likely email address from a person's
first, middle and last name, nicknames, birth year, birth day and
(optionally) random numbers, then can verify them most-likely-first.
See README.md for the full details.

Usage:
    python email_permutator.py                 # interactive prompts
    python email_permutator.py -o emails.txt   # also save results to a file
    python email_permutator.py --verify --provider zerobounce
        # check addresses most-likely-first; API key read from
        # the EMAIL_VERIFY_API_KEY environment variable
"""

import argparse
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

DOMAINS = [
    "gmail.com",
    "outlook.com",
    "hotmail.com",
    "proton.me",
    "protonmail.com",
    "icloud.com",
]

SEPARATORS = ["", ".", "-", "_"]

# Gmail usernames may only contain letters, digits and periods.
GMAIL_ALLOWED = re.compile(r"^[a-z0-9.]+$")


# Letters that don't break down into a plain letter + accent.
SPECIAL_LETTERS = str.maketrans({
    "ß": "ss", "æ": "ae", "œ": "oe", "ø": "o", "ł": "l",
    "đ": "d", "ð": "d", "þ": "th", "ı": "i",
})


def clean(value, keep=""):
    """Lowercase, turn accented letters into plain ones (é -> e), and strip
    anything else that can't go in an email local part. Characters in keep
    (e.g. ".-_") are left in."""
    value = value.strip().lower().translate(SPECIAL_LETTERS)
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(rf"[^a-z0-9{re.escape(keep)}]", "", value)


def ask(prompt, required=False):
    while True:
        value = input(prompt).strip()
        if value or not required:
            return value
        print("  This field is required.")


def ask_yes_no(prompt):
    """Ask a y/n question. Pressing Enter on its own counts as yes."""
    while True:
        value = input(f"{prompt} (y/n): ").strip().lower()
        if value in ("", "y", "yes"):
            return True
        if value in ("n", "no"):
            return False
        print("  Please type y or n.")


def choose_domains(allow_all=True):
    """Ask whether to use every provider, or which ones to include. With
    allow_all off, skip the "all" shortcut and make the user pick."""
    print()
    if not allow_all:
        print("Random numbers are on, so pick which provider(s) to search:")
    elif ask_yes_no("Search all email providers?"):
        return list(DOMAINS)
    while True:
        chosen = [d for d in DOMAINS if ask_yes_no(f"  {d}?")]
        if chosen:
            return chosen
        print("  Pick at least one provider.\n")


def number_suffixes(year, day, digits=0):
    """Number endings as (suffix, rank) pairs; a lower rank is more likely.

    YYYY and YY first, then the birth day, then (optionally) random numbers
    that aren't a date at all: digits=2 adds 1-99, digits=3 adds 100-999
    only (the 1-99 range is left out to keep the list smaller).
    """
    suffixes = []
    if len(year) == 4:
        suffixes.append((year, 1))       # 1993
    if year:
        suffixes.append((year[-2:], 1))  # 93
    if day:
        suffixes.append((day.zfill(2), 3))  # 07
        suffixes.append((day, 3))           # 7
    if digits == 2:
        suffixes += [(str(n), 4) for n in range(1, 100)]
    elif digits == 3:
        suffixes += [(str(n), 4) for n in range(100, 1000)]

    ranked = {}
    for suffix, rank in suffixes:  # dedupe, keeping the first (most likely) rank
        ranked.setdefault(suffix, rank)
    return list(ranked.items())


def local_parts(first, last, nicknames, suffixes, middle=""):
    """Yield (username, likelihood score) pairs; a lower score is more likely.

    The score is only used to decide what order to verify addresses in.
    """
    # Full given names with how likely each is: first name, then nicknames.
    names = [(first, 0)] + [(n, 2) for n in nicknames]
    # Initials only ever go in front of the last name (c + cullen).
    initials = [(first[0], 1)] + [(n[0], 3) for n in nicknames]

    # Name forms as tuples of parts: given/initial + last, then reversed
    # full names (last + given). Reversed order is less common.
    candidates = [((g, last), s) for g, s in names + initials]
    candidates += [((last, g), s + 3) for g, s in names]

    # With a middle name, also given/initial + middle initial + last
    # (charles.a.cullen, c.a.cullen), and the full middle name less often.
    if middle:
        middles = [(middle[0], 1)]
        if len(middle) > 1:
            middles.append((middle, 3))
        candidates += [((g, m, last), s + ms) for g, s in names + initials
                       for m, ms in middles]

    # Drop duplicates (e.g. a nickname with the same initial), keeping the
    # most likely score for each.
    best = {}
    for parts, s in candidates:
        if parts not in best or s < best[parts]:
            best[parts] = s
    forms = list(best.items())

    # 1. Names only, the same separator between every part
    for parts, form_score in forms:
        for sep in SEPARATORS:
            yield sep.join(parts), form_score + SEP_SCORE[sep]

    # 2. Names + each number ending, every separator between the names
    #    and every separator between the names and the number
    for suffix, rank in suffixes:
        for parts, form_score in forms:
            for name_sep in SEPARATORS:
                for date_sep in SEPARATORS:
                    # A separator before the number (cullen.93) is rarer than none.
                    date_sep_score = 0 if date_sep == "" else 1 + SEP_SCORE[date_sep]
                    score = form_score + rank + SEP_SCORE[name_sep] + date_sep_score
                    yield f"{name_sep.join(parts)}{date_sep}{suffix}", score


# How unusual each separator is (plain and dotted are the most common).
SEP_SCORE = {"": 0, ".": 0, "_": 1, "-": 2}


def pattern_parts(pattern, suffixes):
    """Yield (username, score) for one known username start, e.g. "j.smith"
    gives j.smith, j.smith1993, j.smith93, j.smith1 ... j.smith99.
    The number goes straight after the pattern, so type "j.smith_" to get
    j.smith_42 instead."""
    yield pattern, 0
    for suffix, rank in suffixes:
        yield f"{pattern}{suffix}", rank


def build_emails(first, last, nicknames, year, day, domains=DOMAINS, digits=0,
                 pattern="", middle=""):
    """Return a list of (email, score) in generation order, no duplicates.
    If pattern is given, only that username start is used instead of every
    name combination."""
    suffixes = number_suffixes(year, day, digits)
    if pattern:
        parts = pattern_parts(pattern, suffixes)
    else:
        parts = local_parts(first, last, nicknames, suffixes, middle)
    seen = set()
    emails = []
    for local, score in parts:
        for domain in domains:
            if domain == "gmail.com" and not GMAIL_ALLOWED.match(local):
                continue
            email = f"{local}@{domain}"
            if email not in seen:
                seen.add(email)
                emails.append((email, score))
    return emails


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

API_KEY_ENV = "EMAIL_VERIFY_API_KEY"
# Saved results live next to this script, whichever folder you run it from.
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "verify_cache.json")

# Tie-breaker when two addresses have the same score: check the providers
# that give the most reliable answers first.
DOMAIN_ORDER = {d: i for i, d in enumerate([
    "gmail.com", "icloud.com", "outlook.com", "hotmail.com",
    "proton.me", "protonmail.com",
])}


def _get_json(url, params, headers=None):
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(f"{url}?{query}", headers=headers or {})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def check_zerobounce(email, key):
    data = _get_json("https://api.zerobounce.net/v2/validate",
                     {"api_key": key, "email": email, "ip_address": ""})
    if "error" in data:
        raise RuntimeError(data["error"])
    return {"valid": "valid", "invalid": "invalid"}.get(data.get("status"), "unknown"), data.get("status")


def check_neverbounce(email, key):
    data = _get_json("https://api.neverbounce.com/v4/single/check",
                     {"key": key, "email": email})
    if data.get("status") != "success":
        raise RuntimeError(data.get("message", data.get("status")))
    return {"valid": "valid", "invalid": "invalid"}.get(data.get("result"), "unknown"), data.get("result")


def check_kickbox(email, key):
    data = _get_json("https://api.kickbox.com/v2/verify",
                     {"email": email, "apikey": key})
    if not data.get("success"):
        raise RuntimeError(data.get("message", "request failed"))
    result = data.get("result")
    return {"deliverable": "valid", "undeliverable": "invalid"}.get(result, "unknown"), result


def check_hunter(email, key):
    data = _get_json("https://api.hunter.io/v2/email-verifier",
                     {"email": email}, headers={"X-API-KEY": key})
    if "errors" in data:
        raise RuntimeError(data["errors"][0].get("details", "request failed"))
    status = data["data"].get("status")
    return {"valid": "valid", "invalid": "invalid"}.get(status, "unknown"), status


PROVIDERS = {
    "zerobounce": check_zerobounce,
    "neverbounce": check_neverbounce,
    "kickbox": check_kickbox,
    "hunter": check_hunter,
}


def load_cache():
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, sort_keys=True)


def verify(emails, provider, key, max_checks, stop_after):
    """Check addresses most-likely-first, stopping once stop_after valid
    addresses are found (0 = never stop early).

    Step 1 looks through every saved result in the cache (free).
    Step 2 only pays for addresses that have never been checked before."""
    check = PROVIDERS[provider]
    cache = load_cache()
    ordered = [e for e, _ in sorted(emails, key=lambda e: (e[1], DOMAIN_ORDER[e[0].split("@")[1]]))]

    def done():
        return stop_after and len(found) >= stop_after

    found, paid_checks = [], 0

    # Step 1: saved results, no credits used
    cached = [e for e in ordered if e in cache]
    print(f"\nStep 1: checking {len(cached)} saved result(s) from {CACHE_FILE} (free)...\n")
    for email in cached:
        verdict, detail = cache[email]["verdict"], cache[email]["detail"]
        print(f"  {verdict.upper():8} {email}  ({detail}, saved)")
        if verdict == "valid":
            found.append(email)
            if done():
                break

    # Step 2: new addresses, paid checks
    if not done():
        print(f"\nStep 2: checking new addresses with {provider} "
              f"(most likely first, max {max_checks} paid checks)...\n")
        for email in (e for e in ordered if e not in cache):
            if paid_checks >= max_checks:
                print(f"\nReached the limit of {max_checks} checks (raise it with --max).")
                break
            try:
                verdict, detail = check(email, key)
            except urllib.error.HTTPError as e:
                sys.exit(f"API error {e.code}: {e.read().decode(errors='replace')[:200]}")
            except (urllib.error.URLError, RuntimeError) as e:
                sys.exit(f"API error: {e}")
            paid_checks += 1
            cache[email] = {"verdict": verdict, "detail": detail, "provider": provider}
            save_cache(cache)
            time.sleep(0.2)  # stay well under provider rate limits

            print(f"  {verdict.upper():8} {email}  ({detail}, checked)")
            if verdict == "valid":
                found.append(email)
                if done():
                    break

    if done():
        print(f"\nFound {stop_after} valid addresses, stopping.")
    print(f"\n{paid_checks} paid checks used.")
    if found:
        print("Valid address(es) found:")
        for email in found:
            print(f"  {email}")
    else:
        print("No confirmed valid address found in the addresses checked.")


def main():
    parser = argparse.ArgumentParser(description="Generate email address permutations.")
    parser.add_argument("-o", "--output", help="also write the list to this file")
    parser.add_argument("--verify", action="store_true",
                        help=f"check addresses with a verification API (key in ${API_KEY_ENV})")
    parser.add_argument("--provider", choices=PROVIDERS, default="zerobounce",
                        help="which verification service your API key is for (default: zerobounce)")
    parser.add_argument("--max", type=int, default=25,
                        help="maximum paid checks per run (default: 25)")
    parser.add_argument("--stop", type=int, default=3,
                        help="stop after this many valid addresses are found (default: 3)")
    parser.add_argument("--all", action="store_true",
                        help="never stop early; keep checking up to the --max limit")
    args = parser.parse_args()

    key = os.environ.get(API_KEY_ENV, "").strip()
    if args.verify and not key:
        sys.exit(f"Set your API key first, e.g. in PowerShell:  $env:{API_KEY_ENV} = \"your-key\"")

    print("Email permutator - press Enter to skip optional fields.\n")
    first = clean(ask("First name: ", required=True))
    middle = clean(ask("Middle name or initial (optional): "))
    last = clean(ask("Last name: ", required=True))
    nicks_raw = ask("Nickname(s), comma separated (optional): ")
    year = clean(ask("Birth year, e.g. 1993 (optional): "))
    day = clean(ask("Birth day of month, e.g. 13 (optional): "))

    nicknames = [n for n in (clean(x) for x in nicks_raw.split(",")) if n and n != first]
    nicknames = list(dict.fromkeys(nicknames))

    if year and len(year) not in (2, 4):
        sys.exit("Birth year must be 2 or 4 digits.")

    print()
    print("Random numbers after the name (not a date)?")
    print("  0 = none   2 = two digits, 1-99   3 = three digits, 100-999 only")
    while True:
        digits = ask("Choose 0, 2 or 3 (Enter = 0): ") or "0"
        if digits in ("0", "2", "3"):
            digits = int(digits)
            break
        print("  Please type 0, 2 or 3.")

    print()
    print("Only want one username pattern? Type the part before the number,")
    print("e.g. j.smith (gives j.smith42) or j.smith_ (gives j.smith_42).")
    pattern = clean(ask("Pattern, or press Enter to try every name combination: "), keep=".-_")

    # Random numbers multiply the list, so make the user choose providers.
    domains = choose_domains(allow_all=not digits)

    emails = build_emails(first, last, nicknames, year, day, domains, digits, pattern, middle)

    print()
    if not args.verify:
        for email, _ in emails:
            print(email)
    print(f"{len(emails)} addresses generated.")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write("\n".join(email for email, _ in emails) + "\n")
        print(f"Saved to {args.output}")

    if args.verify:
        verify(emails, args.provider, key, args.max, 0 if args.all else args.stop)


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
