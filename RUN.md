# Refreshing the data after adding a new game link

Follow these steps whenever you add one or more links to `game_links.csv`.
The scraper is **incremental** — it only fetches games it hasn't already done,
so re-running is safe and cheap.

Run everything from the project root:

```bash
cd /Users/sbmsoikot/FifaWC26AnalyseThis
```

---

## Step 1 — (first time only) install dependencies

> **One-time.** Skip if already done. **Check first:**
> ```bash
> python3 -c "import pandas, pyarrow; print('deps OK')"
> ```
> If that prints `deps OK`, jump to Step 2. Otherwise install:

```bash
pip3 install -r requirements.txt
```

> 💡 To keep this isolated from other Python projects, you can use a virtualenv:
> ```bash
> python3 -m venv .venv && source .venv/bin/activate   # one-time
> pip install -r requirements.txt                       # one-time
> ```
> (The web-app backend has its own venv under `backend/.venv` — see
> [README.md §4](README.md#4-setup--one-time-vs-repeated-commands).)

---

## Step 2 — confirm your new link is in the file

```bash
cat game_links.csv
```

You should see the new line, e.g. `.../gameId/760417`. Each line just needs to
contain `gameId/<number>`; order and a header row don't matter.

---

## Step 3 — scrape only the new game(s)

```bash
python3 scrape_wc26.py
```

What to expect in the output:

- A line like `processing 1 game(s): 760417`
- Then `[760417] <TeamA> vs <TeamB> — NN players, NNN stat fields`
- Then `master rebuilt: ... rows across N games`

If a game has **not been played yet**, ESPN has no player stats and you'll see
an error line for that id — it is marked so it retries next run. Just re-run
Step 3 once the match has finished.

---

## Step 4 — verify it landed

```bash
python3 - <<'PY'
import pandas as pd
df = pd.read_parquet("data/all_players_stats.parquet")
print("games:", sorted(df.game_id.unique()))
print("rows :", len(df))
PY
```

The new `gameId` should appear in the list and the row count should have grown.

---

## Step 5 — refresh the analysis notebook

Open `analysis.ipynb` and run all cells (Kernel ▸ Restart & Run All), **or**
re-execute it from the command line:

```bash
jupyter nbconvert --to notebook --execute --inplace analysis.ipynb
```

All leaderboards and tables now include the new match.

---

## Handy variations (optional)

| Goal | Command |
|---|---|
| Re-scrape **one** specific game (overwrite it) | `python3 scrape_wc26.py --game 760417` |
| Re-scrape **everything** from scratch | `python3 scrape_wc26.py --force` |
| Also keep players who didn't play | `python3 scrape_wc26.py --include-dnp` |
| Auto-poll the csv every 60s for new links | `python3 scrape_wc26.py --watch 60` (Ctrl-C to stop) |
| See what's been processed so far | `cat data/processed_games.json` |
| Check the run log | `tail -n 30 scrape.log` |

---

### TL;DR — the normal refresh is just two commands

```bash
python3 scrape_wc26.py
jupyter nbconvert --to notebook --execute --inplace analysis.ipynb
```
