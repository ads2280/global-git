# 🌍 global-git

> Because why should English speakers have all the fun? (Spoiler: they shouldn't)

Finally, you can use Git commands in Spanish, French, Japanese, and even British English without your computer yelling at you in American. 

## ¿Qué es esto?

global-git is a wrapper that lets you use Git commands in multiple languages. That's it. That's the repo. We could've made it more complicated, but why?

Want to `git cometer` instead of `git commit`? Now you can. Feel like doing a `git empujar` instead of `git push`? Go wild. Prefer to `git honour` your changes in proper British English? Absolutely smashing, old chap.

Your monolingual coworkers will be confused. Your multilingual coworkers will be impressed. Your British coworkers will finally feel seen.

## Why though?

Why not? Also:
- Makes your git history more interesting
- Confuses your coworkers in the best way
- Proves that programming doesn't have to be English-only
- Born from procrastination and "actually down" energy


## Installation

Option 1: from source
```bash
pip install .
# or editable
pip install -e .
```

Option 2: from a clone
```bash
git clone <this repo>
cd global-git
pip install .
```

During install, we add your Python scripts directory to your shell PATH (best-effort) so the `git` shim runs before the system git. Set `GLOBAL_GIT_NO_PATH=1` to opt out.

## Uso (Usage)

Before using, run `gitglobal` to see the most useful commands to get started.

### CLI Reference

The dedicated `gitglobal` helper lets you explore and control language support:

- `gitglobal status` - show the currently active languages.
- `gitglobal languages` — list every language and highlight the active ones.
- `gitglobal show` — display the command/flag mappings for the currently active languages.
- `gitglobal switch LANGUAGE` — activate a language.
- `gitglobal all` — enable every available language.
- `gitglobal --help` — help command for gitglobal.

Instead of this:
```bash
git commit -m "fix: typo in readme"
git push origin main
```

Do this:
```bash
git cometer -m "arreglo: error en readme"
git empujar origin principal
```

Or this (British English):
```bash
git honour -m "fix: typo in readme"
git dispatch origin main
```

## Comandos Disponibles (Available Commands)

### Supported Languages

- 🇪🇸 **Spanish (es)**: `git cometer`, `git empujar`, `git jalar`
- 🇫🇷 **French (fr)**: `git valider`, `git pousser`, `git tirer`
- 🇩🇪 **German (de)**: `git committen`, `git schieben`, `git ziehen`
- 🇵🇹 **Portuguese (pt)**: `git confirmar`, `git enviar`, `git puxar`
- 🇷🇺 **Russian (ru)**: `git закоммитить`, `git отправить`, `git получить`
- 🇯🇵 **Japanese (ja)**: `git コミット`, `git プッシュ`, `git プル`
- 🇬🇧 **British English (en-gb)**: `git honour`, `git dispatch`, `git requisition`

### Example Commands

**git cometer** / **git honour** → `git commit` - Commit with international flair

**git empujar** / **git dispatch** → `git push` - Push it properly

**git jalar** / **git requisition** → `git pull` - Pull with panache

**git rama** / **git bough** → `git branch` - Branch in style

**git añadir** / **git append** → `git add` - Add files eloquently

**git estado** / **git enquire** → `git status` - Check your status politely

**git fusionar** / **git amalgamate** → `git merge` - Merge with sophistication

*And many more! Check default_config.yaml for the full list.*

### Flags too

Flags are translated when possible:

- `--ayuda` → `--help` (Spanish)
- `--assistance` → `--help` (British)
- `--loquacious` → `--verbose` (British, naturally)
- `--compel` → `--force` (British)
- Values like `--color=always` keep their value when translated

You can disable translation for a command by setting `GLOBAL_GIT_BYPASS=1` in the environment.

## Inspiración

Anika

## Contributing

PRs welcome! Want to add more languages, commands, or make git even more delightfully verbose in British English? Go for it!

No gatekeeping here—whether you're a native speaker or just learning, all contributions are válidas.


