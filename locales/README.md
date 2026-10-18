# Writing PlainLang in your language

PlainLang's keywords (`say`, `if`, `repeat`, `end`, …) can be replaced with words from another
language, so a learner can write `kyerɛ`, `sɛ`, `bio` instead of memorising English. This folder
holds the language files, and the tools to make and check your own.

> **The honest part.** A locale is only as good as the person who wrote it. The one file shipped
> here, `demo-fr.json`, is a **demonstration** of the mechanism, not a reviewed translation.
> **There is deliberately no Twi, Ga, Ewe or Dagbani file yet**: a machine (or a non-speaker)
> guessing keywords for children would produce confident-looking mistakes. Those files should be
> written by people who speak the language, ideally with some learners in the room.

## Making a new language

1. **Start from the blank template** (every keyword, every value empty):

   ```bash
   python plain.py locale template > locales/tw.json
   ```

2. **Fill it in.** Open the file and give each English keyword (the key — don't change it) a word
   in your language (the value). Also set `"code"` (e.g. `"tw"`), `"name"`, and use `"notes"` to
   credit who wrote and checked it.

3. **Check it.** The checker finds every mistake it can:

   ```bash
   python plain.py locale check locales/tw.json
   ```

   It reports keywords you forgot, values that aren't a single word, two keywords given the same
   word, and a word that is *also* a different English keyword (which would silently change what a
   program means).

4. **Try it on real programs.** Translate an example into your language and run it:

   ```bash
   python plain.py translate --lang tw --to tw demo.plang > demo-tw.plang
   python plain.py run --lang tw demo-tw.plang
   ```

5. **Read it aloud.** PlainLang's whole idea is code that can be read aloud. Read a translated
   program out loud to someone who speaks the language. If it sounds strained, change the words
   until it doesn't — that matters more than a perfect dictionary translation.

## Choosing good words

- **One word per keyword.** `at least` is *two* keywords, `at` and `least`; translate each so that
  the sentence still reads naturally (`is at least 5`).
- **Use the word learners already say.** For `end`, the word a teacher uses to say "that's the end
  of the block" beats a formal term.
- **Keep related words related** (`forward`/`backward`, `smallest`/`largest`).
- **Avoid words you'd want for variable names** (like `age` or `name`), because a locale word can
  never be used as a name in a program.
- **Pick one spelling.** Keywords match whatever capital letters are used, but not alternate
  spellings or tone marks, so decide.

## What works today, and what doesn't yet

| Works | Not yet |
|---|---|
| Every command: `plain run`, `check`, `vm`, `wasm`, `spec` accept `--lang` | The browser playground (it only reads English for now) |
| Keywords in any script, including non-Latin letters | Error messages are still in English (shown against the translated program) |
| Comments, text in quotes, and your own names are never touched | Lesson text and the documentation are English only |
| `{code}` inside a text is translated like any other code | Variable and function names must still be written with A–Z, digits and `_` (so no `ɔ`, `ɛ`, `ŋ` in names yet) |

## How it works (so you can trust it)

Translation happens on the program text *before* anything else reads it, so there is one
translator and every engine is unchanged. It only ever replaces whole keywords outside comments
and quoted text. A program survives English → your language → English **exactly**; that is tested
on hundreds of generated programs (`test_locale.py`).
