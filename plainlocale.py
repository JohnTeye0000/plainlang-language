"""
plainlocale -- write PlainLang in your own language.

A locale file maps each of PlainLang's keywords to a word in another language. This module
translates program text between English and a locale, *before* the program is tokenized, so
every engine, the checker, the formatter and the language server work in any language
without knowing about it.

    plain translate --lang fr program.plang           # French -> English, to stdout
    plain translate --lang fr --to fr program.plang   # English -> French
    plain run --lang fr program.plang                 # run a program written in French
    plain locale check locales/demo-fr.json           # is this locale file complete and sound?
    plain locale template > locales/mylang.json       # start a new language

Only keywords are translated. Comments, text in quotes, and your own variable and function
names are never touched (words inside {braces} in a text *are*: they're code). Error messages
stay in English for now; they are shown against the translated program.

Honest scope: a locale is only as good as the person who wrote it. The files shipped here are
demonstrations of the mechanism, not reviewed translations; a real locale should be written or
checked by native speakers (see locales/README.md).
"""

import json
import os
import re
import sys

import plainlang as pl

HERE = os.path.dirname(os.path.abspath(__file__))
LOCALES_DIR = os.path.join(HERE, "locales")
FORMAT = "plainlang-locale"

# A local keyword is one Unicode word: starts with a letter or '_', then letters/digits/'_'.
_WORD = re.compile(r"^[^\W\d]\w*$")
_SCAN = re.compile(r'(#[^\n]*)|("[^"]*")|([^\W\d]\w*)|(.|\n)', re.DOTALL)


class LocaleError(Exception):
    """A locale file is unusable, or a program can't be translated. Message is user-facing."""


class Locale:
    def __init__(self, code, name, words, notes=""):
        self.code = code
        self.name = name
        self.words = dict(words)                       # english keyword -> local word
        self.notes = notes
        self.to_en = {w.lower(): k for k, w in self.words.items() if w}
        self.from_en = {k: w.lower() for k, w in self.words.items() if w}


def problems(locale):
    """Everything wrong with a locale, as a list of readable strings (empty = sound)."""
    out = []
    missing = sorted(k for k in pl.KEYWORDS if not locale.words.get(k))
    if missing:
        out.append(f"missing {len(missing)} keyword(s): {', '.join(missing)}")
    unknown = sorted(k for k in locale.words if k not in pl.KEYWORDS)
    if unknown:
        out.append(f"not PlainLang keywords: {', '.join(unknown)}")
    seen = {}
    for k in sorted(locale.words):
        w = locale.words[k]
        if not w:
            continue
        if not _WORD.match(w):
            out.append(f"'{k}' -> {w!r} must be a single word (letters, digits, '_'; no spaces; not starting with a digit)")
            continue
        low = w.lower()
        if low in seen:
            out.append(f"'{seen[low]}' and '{k}' both use the word {w!r}, so a program couldn't tell them apart")
        seen[low] = k
        if low in pl.KEYWORDS and low != k:
            out.append(f"'{k}' -> {w!r} is also the English keyword '{low}', which would change its meaning")
    return out


def load_locale(source):
    """A Locale from a path, a bare code like 'fr' (looked up in locales/), or a dict."""
    if isinstance(source, dict):
        data, label = source, "locale"
    else:
        path = source if os.path.exists(source) else os.path.join(LOCALES_DIR, f"{source}.json")
        # a bare code like 'fr' means the shipped demo-fr.json
        if not os.path.exists(path):
            path = os.path.join(LOCALES_DIR, f"demo-{source}.json")
        if not os.path.exists(path):
            raise LocaleError(f"I couldn't find a locale called '{source}' (looked for {source}, locales/{source}.json "
                              f"and locales/demo-{source}.json).")
        label = path
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise LocaleError(f"'{path}' isn't valid JSON.")
    if not isinstance(data, dict) or data.get("format") != FORMAT or not isinstance(data.get("words"), dict):
        raise LocaleError(f"'{label}' isn't a PlainLang locale file (expected format '{FORMAT}' and a 'words' table).")
    return Locale(data.get("code", ""), data.get("name", ""), data["words"], data.get("notes", ""))


def template():
    """An empty locale: every keyword present, every value blank, ready to be filled in."""
    return {
        "format": FORMAT,
        "code": "",
        "name": "",
        "notes": "Fill in each value with ONE word in your language. Keep the keys (English) exactly as they are.",
        "words": {k: "" for k in sorted(pl.KEYWORDS)},
    }


def _map_words(code, fn):
    """Rewrite the words in a piece of program text; strings and comments are skipped, except
    for the {code} inside a string, which is translated like any other code."""
    out = []
    for m in _SCAN.finditer(code):
        comment, string, word, other = m.groups()
        if comment is not None:
            out.append(comment)
        elif string is not None:
            out.append(_map_string(string, fn))
        elif word is not None:
            out.append(fn(word))
        else:
            out.append(other)
    return "".join(out)


def _map_string(literal, fn):
    body = literal[1:-1]
    out, i, n = [], 0, len(body)
    while i < n:
        c = body[i]
        if c in "{}" and i + 1 < n and body[i + 1] == c:        # {{ and }} are literal braces
            out.append(body[i:i + 2]); i += 2
        elif c == "{":
            j = body.find("}", i + 1)
            if j == -1:
                out.append(body[i:]); break
            out.append("{" + _map_words(body[i + 1:j], fn) + "}"); i = j + 1
        else:
            out.append(c); i += 1
    return '"' + "".join(out) + '"'


def to_english(source, locale):
    """Program text in `locale` -> English PlainLang. Words that aren't local keywords
    (variable names, and any English keyword you leave in) pass through unchanged."""
    return _map_words(source, lambda w: locale.to_en.get(w.lower(), w))


def to_locale(source, locale):
    """English PlainLang -> program text in `locale`. Refuses if one of the program's own names
    is also a word of the locale (it would silently turn into a keyword when read back)."""
    clash = []

    def convert(word):
        low = word.lower()
        if low in pl.KEYWORDS:
            return locale.from_en.get(low, word)
        if low in locale.to_en:
            clash.append(word)
        return word

    result = _map_words(source, convert)
    if clash:
        raise LocaleError("These names in the program are also words of the locale, so translating would change "
                          f"their meaning: {', '.join(sorted(set(clash)))}. Rename them first.")
    return result


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]
    try:
        if cmd == "template":
            print(json.dumps(template(), indent=2, ensure_ascii=False))
            return 0
        if cmd == "check":
            loc = load_locale(rest[0])
            found = problems(loc)
            if found:
                print(f"{rest[0]} has {len(found)} problem(s):")
                for p in found:
                    print("  -", p)
                return 1
            print(f"{rest[0]}: sound — all {len(pl.KEYWORDS)} keywords translated, no collisions.")
            return 0
        if cmd == "translate":
            lang = to = path = None
            i = 0
            while i < len(rest):
                if rest[i] == "--lang" and i + 1 < len(rest):
                    lang = rest[i + 1]; i += 2
                elif rest[i] == "--to" and i + 1 < len(rest):
                    to = rest[i + 1]; i += 2
                else:
                    path = rest[i]; i += 1
            if not lang or not path:
                print("usage: plain translate --lang CODE [--to CODE] program.plang")
                return 2
            with open(path, encoding="utf-8") as f:
                text = f.read()
            loc = load_locale(lang)
            try:
                sys.stdout.reconfigure(encoding="utf-8")
            except (AttributeError, ValueError):
                pass
            sys.stdout.write(to_locale(text, load_locale(to)) if to else to_english(text, loc))
            return 0
        print(f"plainlocale: unknown command '{cmd}'. Try: template, check, translate.")
        return 2
    except LocaleError as e:
        print(f"\n  Oops! {e}")
        return 2
    except FileNotFoundError as e:
        print(f"\n  Oops! I couldn't find '{e.filename}'.")
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
