# auskiptracer

A command-line skip tracing tool. Give it the full name of the person you're
tracing and any phone numbers you have. It then builds every likely personal
email address from their name and birth details and (optionally) checks them
with an email verification service, most likely address first.

Everything is pinned to a **profile** for that person: name at the top, then
every phone number and every confirmed email, printed on one page at the end.

Example: from **Jane A. Smith**, nickname **Janie**, born the **7th** in **1990**, it builds
addresses like `jane.smith90@gmail.com`, `j.a.smith@outlook.com` and
`janie_smith1990@icloud.com`.

---

## Requirements

- Python 3.8 or newer
- No extra packages. It only uses the standard library.
- For verification only: an API key from a verification service (ZeroBounce by default)

## Quick start

```powershell
git clone https://github.com/<your-username>/auskiptracer.git
cd auskiptracer
python email_permutator.py
```

Answer the questions, and the full list is printed. To also save it to a file:

```powershell
python email_permutator.py -o emails.txt
```

To check the addresses with ZeroBounce (see [Verification](#verification)):

```powershell
python email_permutator.py --verify
```

---

## The questions

The script asks one question at a time. Press **Enter** to skip anything optional.

| # | Question | Required | Notes |
|---|---|---|---|
| 1 | Who has skipped that needs tracing? | yes | Full name, e.g. `Jane Anne Smith`. The split into first / middle / last is shown so you can correct it. |
| 2 | Do you have their digits? | no | Phone number(s), see [Phone numbers](#phone-numbers) |
| 3 | Nickname(s) | no | Put commas between several, e.g. `Janie, JJ` |
| 4 | Birth year | no | 4 digits (`1990`) or 2 (`90`) |
| 5 | Birth day of month | no | e.g. `7` |
| 6 | Random numbers | no | `0` = none, `2` = 1–99, `3` = 100–999 (Enter = 0) |
| 7 | Pattern | no | One known username start, e.g. `j.smith` (see [Pattern](#pattern-mode)) |
| 8 | Providers | yes | "Search all?" or pick one by one. If random numbers are on, you must pick. |

If a profile with the same name already exists, it's shown and you're asked
whether it's the same person. Say **y** to add to it, **n** to open a new one.

### Phone numbers

Type as many as you have, separated by commas or spaces. Spaces inside a
number are fine too:

| You type | Saved as |
|---|---|
| `0412 345 678, 0498765432` | `0412 345 678`, `0498 765 432` |
| `0412345678 0498765432` | `0412 345 678`, `0498 765 432` |
| `+61 412 345 678` | `0412 345 678` |
| `0412 345 678 02 9876 5432` | `0412 345 678`, `02 9876 5432` |

Australian `+61` numbers are stored in the local `0` form so the same number
is never saved twice. Other international numbers keep their `+`.

For y/n questions, pressing **Enter** on its own means **yes**.

### How names are cleaned

Everything is made lowercase and turned into characters that can go in an email address:

| You type | Becomes |
|---|---|
| `Jane` | `jane` |
| `O'Brien Smith` | `obriensmith` |
| `Mary-Jane` | `maryjane` |
| `José`, `Zoë`, `Müller` | `jose`, `zoe`, `muller` |
| `Straße`, `Søren`, `Łukasz` | `strasse`, `soren`, `lukasz` |

---

## What gets generated

### 1. Name forms

| Form | Example |
|---|---|
| First + last | `janesmith` |
| First initial + last | `jsmith` |
| First + middle initial + last | `jane.a.smith` |
| First initial + middle initial + last | `j.a.smith` |
| Nickname + last | `janiesmith` |
| Nickname + middle initial + last | `janie.a.smith` |
| Last + first | `smithjane` |
| Last + nickname | `smithjanie` |
| First + **full** middle name + last | `jane.anne.smith` (only if you type the full middle name) |

Rules:
- Initials only ever go **in front** (`jsmith`), never at the end, so there's no `smithj` or `janes`.
- If a nickname starts with the same letter as the first name, the duplicate initial version is only made once.

### 2. Separators

Each name form is made with each of these between the parts:

| Separator | Example |
|---|---|
| none | `janesmith` |
| `.` | `jane.smith` |
| `_` | `jane_smith` |
| `-` | `jane-smith` |

The separator before a number can be different from the one between the
names, e.g. `jane.smith_90`.

**Gmail only allows dots**, so `_` and `-` versions are never made for Gmail.

### 3. Number endings

Every name form is also made with each of these on the end:

| Ending | Example | When |
|---|---|---|
| Birth year (YYYY) | `janesmith1990` | if a year is given |
| Birth year (YY) | `janesmith90` | if a year is given |
| Birth day | `janesmith07`, `janesmith7` | if a day is given |
| Random 1–99 | `janesmith42` | if you chose `2` |
| Random 100–999 | `janesmith777` | if you chose `3`; the 1–99 range is left out |

A full birthdate like `07061990` is never used.

### 4. Providers

| Provider |
|---|
| gmail.com |
| outlook.com |
| hotmail.com |
| proton.me |
| protonmail.com |
| icloud.com |

Outlook and Hotmail are both Microsoft, and proton.me and protonmail.com are both
Proton. If you know it's "a Microsoft one" or "a Proton one", pick both in that pair.

Yahoo is deliberately left out: it accepts every address, so it can't be verified.

### Pattern mode

If you already know how the username starts, type it at the **Pattern** question.
All the name combinations are skipped and only that start is used, with the number endings added straight after:

| Pattern typed | Makes |
|---|---|
| `j.smith` | `j.smith`, `j.smith1990`, `j.smith90`, `j.smith7`, `j.smith42` … |
| `j.smith_` | `j.smith_`, `j.smith_1990`, `j.smith_42` … |

This is the best way to use random numbers, because it keeps the list small.

---

## How big the list gets

Exact counts for the Jane A. Smith / Janie / 7th / 1990 example:

| Setup | Addresses |
|---|---|
| No random numbers, all 6 providers | 2,864 |
| No random numbers, Gmail only | 144 |
| No random numbers, Outlook only | 544 |
| Random 1–99, Outlook only | 12,960 |
| Random 100–999, Outlook only | 115,744 |
| Pattern `j.smith`, no random numbers, Outlook | 5 |
| Pattern `j.smith` + 1–99, Outlook | 102 |
| Pattern `j.smith` + 100–999, Outlook | 905 |

Making a big list is fine. Verifying one is expensive, so narrow it down first.

---

## Verification

Verification asks an email verification service whether each address actually
exists, without sending any email.

### Setting up your API key

1. Sign up at [zerobounce.net](https://www.zerobounce.net). The free plan gives 100 checks a month.
2. Copy your key from **API → API Keys**.
3. Save it on your computer (never paste it into the code or share it):

   **This PowerShell window only:**
   ```powershell
   $env:EMAIL_VERIFY_API_KEY = "your-key-here"
   ```

   **Permanently for your Windows user** (open a *new* PowerShell window afterwards):
   ```powershell
   setx EMAIL_VERIFY_API_KEY "your-key-here"
   ```

If you see `Set your API key first`, the window was opened before the key was
saved. Open a new window, or load the saved key into the current one:

```powershell
$env:EMAIL_VERIFY_API_KEY = [Environment]::GetEnvironmentVariable("EMAIL_VERIFY_API_KEY", "User")
```

### How a verify run works

**Step 1: saved results (free).** Every address checked before is stored in
`verify_cache.json` next to the script. These are looked at first, and no
credits are used. If that already finds enough valid addresses, the run stops
there.

**Step 2: new addresses (paid).** Only addresses that have never been checked
are sent to the service, **most likely first**:

1. Plain name forms: `janesmith`, `jane.smith`
2. First initial: `jsmith`, `j.smith`
3. Middle initial and birth year: `jane.a.smith`, `janesmith1990`, `janesmith90`
4. Nicknames, birth day, reversed names
5. `_` and `-` versions and separators before numbers
6. Random numbers last

When two addresses are equally likely, providers are checked in this order:
Gmail, iCloud, Outlook, Hotmail, proton.me, protonmail.com.

A run stops when either:
- **5 valid addresses** have been found, or
- **50 paid checks** have been used.

Only a `valid` result counts as found. Results like `catch-all` or `unknown`
are shown but not counted, because the service couldn't confirm them.

Every valid address found is pinned to the person's profile.

---

## The profile board

At the end of every run the whole profile is printed:

```
========================================
  JANE ANNE SMITH
  profile #1, opened 2026-09-27
========================================
  |
  +-- Phone numbers (2)
  |     +-- 0412 345 678
  |     `-- 02 9876 5432
  |
  `-- Emails (5)
        +-- jane.smith@gmail.com  (valid, zerobounce)
        +-- janesmith@gmail.com  (valid, zerobounce)
        +-- jsmith@icloud.com  (valid, zerobounce)
        +-- j.smith@icloud.com  (valid, zerobounce)
        `-- jane.smith@icloud.com  (valid, zerobounce)
```

To look at a saved profile without running anything:

```powershell
python email_permutator.py --board "Jane Smith"
```

Profiles are kept in `profiles.db`, separate from `verify_cache.json`. The
cache is every address ever checked, for anyone. A profile is one person and
only what's been confirmed for them.

### Cost

ZeroBounce charges roughly $0.008 per check, about $8 per 1,000. The free plan
covers 100 checks a month. An address is never paid for twice, because it's
saved after the first check.

---

## Command-line options

| Option | Default | What it does |
|---|---|---|
| `-o FILE`, `--output FILE` | — | Also save the full list to a text file |
| `--verify` | off | Check the addresses with a verification service |
| `--provider NAME` | `zerobounce` | Which service your key is for: `zerobounce`, `neverbounce`, `kickbox` or `hunter` |
| `--max N` | `50` | Maximum paid checks per run |
| `--stop N` | `5` | Stop after this many valid addresses are found |
| `--all` | off | Never stop early; keep checking until `--max` is reached |
| `--board NAME` | — | Just print the saved profile(s) for that name and exit |

Examples:

```powershell
# Just list the addresses
python email_permutator.py

# List them and save to a file
python email_permutator.py -o emails.txt

# Verify, allowing up to 100 paid checks
python email_permutator.py --verify --max 100

# Verify with a pattern + random numbers (about 900 checks for 100-999)
python email_permutator.py --verify --max 1000

# Use a Hunter.io key instead of ZeroBounce
python email_permutator.py --verify --provider hunter
```

---

## Files

| File | What it is |
|---|---|
| `email_permutator.py` | The script |
| `profiles.db` | Saved profiles: names, phone numbers and confirmed emails (created on the first run). It holds real personal details, so `.gitignore` keeps it out of git. |
| `verify_cache.json` | Saved verification results (created on the first `--verify` run). Delete it to start fresh. It holds real addresses, so `.gitignore` keeps it out of git. |
| `.gitignore` | Keeps saved results, generated lists and Python cache files out of git |
| `README.md` | This file |

---

## Limitations

- **Accept-all servers:** some providers accept any address for a while, so the
  service returns `catch-all` or `unknown`. These aren't counted as found.
- **Random numbers:** if the number has nothing to do with a date (like `42` or `777`),
  finding it relies on the random-number option, which is expensive without a pattern and one provider.
- **Other providers:** addresses on other providers (AOL, GMX, work or school domains, etc.) aren't generated.
- **Paid-service results:** a `valid` result means the mailbox exists, not that it's
  still actively used by that person.

## Responsible use

Only look up addresses you have a legitimate reason to find, such as your own
old accounts or people who would expect to hear from you. Don't use it to
track down someone who doesn't want to be contacted. Verification services can
also suspend keys that are used for bulk guessing.
