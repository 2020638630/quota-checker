# Local runtime data

This directory stores local configuration and runtime history.

The JSON files are intentionally excluded from the public repository because
they may contain credentials, quota history, UI preferences, or other local
runtime state.

After cloning, initialize the local quota configuration with:

```text
python quota.py --init
```

The desktop pet and widget will use safe defaults until local configuration
and credentials are provided.

To select the pet's movement animation, add `move_style` to the ignored local
`ui.json` file. Supported values are `walk`, `run`, `ride`, and `duo`; missing
or invalid values use `walk`.

```json
{
  "auto_spawn": false,
  "move_style": "walk"
}
```
