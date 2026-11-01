# Install and use OpenBound

OpenBound is for authors, developers and researchers preparing private work for a public audience. Install the complete `skills/openbound/` unit: `SKILL.md`, host metadata, seven references and three scripts. Python 3.10+, Git and POSIX are required for the tools; Windows is unsupported. Read [license status](../LICENSE-STATUS.md) before reuse.

## Codex installation

With Codex's bundled Skill installer available:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-installer/scripts/install-skill-from-github.py" \
  --repo IndelibleVivi/openbound \
  --path skills/openbound \
  --name openbound \
  --ref main \
  --method download
```

For a reproducible installation, replace `main` with a reviewed commit or tag. For another Agent Skills host, follow its installation instructions using the complete unit; copying only `SKILL.md` omits the methods and tools.

Start a fresh host session, then request:

```text
Use $openbound to prepare this private project for publication.
Preserve its mature behavior and produce a complete, verified public candidate.
Complete external delivery only within my existing authorization.
```

You can also ask to extract an independent component, develop research notes into a blueprint, or update an existing public work. The outcome is the actual requested work and appropriate evidence, not only a scan or plan. Explain the intended audience and public promises when they are known.

## Updates and discovery

Before updating, identify the installed source/version and local changes. Preserve any changes and use the host's supported update procedure. If the installer refuses an existing target, inspect it rather than deleting an unknown directory or forcing an overwrite. Keep recovery copies outside active Skill discovery directories.

After installation or update, refresh the host as required and verify explicit invocation in a new session. Host metadata permitting implicit invocation does not prove that the host loaded the Skill. To check natural discovery, use a separate new session and request public preparation without naming OpenBound. An ordinary public README typo fix without a private boundary should remain a normal development task.

Source verification, installation, discovery and observed implicit activation are separate states. See [current state](current-state.md) and [validation](validation.md) for reported observations.

## Inspect the source locally

```bash
git clone https://github.com/IndelibleVivi/openbound.git
cd openbound
python3 -B tools/validate.py
```

This checks structure, links, deterministic tests and relocated CLI entry points. It does not install the Skill or establish host activation. Optional Skill-authoring validation is `skill-validate skills/openbound` when that local utility is available. Tool arguments, recovery and execution boundaries are documented in [the tool contract](../skills/openbound/references/continuation-and-tools.md).
