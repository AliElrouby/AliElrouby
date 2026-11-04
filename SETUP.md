# Setup — AliElrouby / Neural Atlas

This directory is a **GitHub profile repository**. The project is built for the account `AliElrouby`.

## Install

1. Sign in to GitHub, and open https://github.com/new.
2. Create a **public** repository named **`AliElrouby`**. If it already exists, use it instead of creating another.
3. Keep the file structure intact: `README.md`, `assets/`, `config/`, `scripts/`, and the hidden `.github/workflows/` folder at the root of that repository. A local Git clone and `git push` is the easiest way to preserve hidden folders.
4. On GitHub, open **Actions → Update 3D contribution city → Run workflow**.
5. Run **Actions → Update Retro Arcade snake (all time) → Run workflow** as well (it also runs automatically whenever the snake script or workflow changes on `main`).
6. Check that the Actions runs succeeded, that the `output-3d-contrib` branch exists, and that `assets/arcade-snake.svg` was refreshed on `main`.
7. Refresh https://github.com/AliElrouby. The city updates daily; the snake updates every Monday.

## If actions cannot push

Go to the profile repository's **Settings → Actions → General → Workflow permissions** and check that GitHub Actions has permission to write repository contents. The workflows include `permissions: contents: write`, but repository or organization policy can still restrict it.

## If the 3D city or snake looks broken

- Check the **Actions** tab for errors, especially `GITHUB_TOKEN` permission errors.
- Confirm the published files exist:
  - `https://raw.githubusercontent.com/AliElrouby/AliElrouby/output-3d-contrib/atlas-city.svg`
  - `https://github.com/AliElrouby/AliElrouby/blob/main/assets/arcade-snake.svg`
- Allow GitHub's image cache some time to refresh after publication.
- Make sure both workflow files remain under `.github/workflows/` in the *default branch*.

## Preview the snake locally

```bash
python scripts/generate_arcade_snake.py --demo --output /tmp/arcade-snake.svg
```

`--demo` uses clearly labelled synthetic data. `--since YYYY-MM-DD` and `--date YYYY-MM-DD` override the start and end dates; without `--since` the grid starts on the day of the first push (first commit), falling back to the first active day. Real data needs a `GITHUB_TOKEN` environment variable (provided automatically in Actions).

## Customize the colors

- Header and network map: `assets/*.svg` (editable vector graphics)
- Isometric contribution city: `config/atlas-city.json` (`contribColors`, `radarColor`, `backgroundColor`, etc.)
- Snake: palette constants at the top of `scripts/generate_arcade_snake.py` (`LEVELS`, `SNAKE_BODY`, `LIME`, `VIOLET`, `COPPER`) and its speed (`STEPS_PER_SECOND`)
- GitHub stat cards: URL query parameters in `README.md`

## Notes

- GitHub contribution counts and third-party statistics come from the user's real public activity. The repository contains no fabricated numbers.
- The snake shows a single grid covering every week since the first push. Cells are big while the history is short and shrink as the years add up, so it always fits on one line.
- Some third-party SVG services may have periodic rate limits. Statistics are illustrative metrics, not a full representation of engineering ability.
- The About, experience, skills, and featured work sections are based on the provided CV. If a project repository becomes public later, link it manually without inventing the URL.

## Components

- Custom Neural Atlas header / technical map: created for this profile
- Retro Arcade contribution snake: `scripts/generate_arcade_snake.py` (standard-library Python + GitHub GraphQL)
- Contribution city: https://github.com/yoshi389111/github-profile-3d-contrib
- Stats: https://github.com/stats-organization/github-stats-extended
- Typing animation: https://github.com/DenverCoder1/readme-typing-svg
