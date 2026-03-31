import pandas as pd
from pathlib import Path
import os


def load_env():
    if Path('.env').exists():
        for line in Path('.env').read_text().splitlines():
            if '=' in line:
                k, v = line.split('=', 1)
                os.environ[k.strip()] = v.strip()


def run_pipeline(weapons, armor, loadouts, output_dir, use_bungie=False):
    load_env()

    df_w = pd.read_csv(weapons)
    df_a = pd.read_csv(armor)

    df = pd.concat([df_w, df_a], ignore_index=True).fillna("")

    output_dir.mkdir(exist_ok=True)

    # Basic report
    (output_dir / "manifest_summary.md").write_text(
        f"# Summary\n\nTotal Items: {len(df)}\n"
    )

    # Simple owned exotic detection
    if 'Rarity' in df.columns:
        exotics = df[df['Rarity'].str.lower() == 'exotic']
        (output_dir / "Owned Meta.md").write_text(
            "# Owned Exotics\n\n" + "\n".join(f"- {x}" for x in exotics['Name'])
        )

    # Placeholder Bungie usage
    if use_bungie:
        key = os.getenv("BUNGIE_API_KEY")
        (output_dir / "bungie_status.md").write_text(
            f"Bungie API Enabled: {'YES' if key else 'NO KEY'}"
        )
