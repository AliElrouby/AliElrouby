# Setup — AliElrouby / Neural Atlas

This directory is a **GitHub profile repository**. The project is built for the account `AliElrouby`.

## Install

1. Sign in to GitHub, and open https://github.com/new.
2. Create a **public** repository named **`AliElrouby`**. If it already exists, use it instead of creating another.
3. Keep the file structure intact. Upload `README.md`, `assets/`, `config/`, and the hidden `.github/workflows/` folder to the root of that repository. A local Git clone and `git push` is the easiest way to preserve hidden folders.
4. On GitHub, open **Actions → Update 3D contribution city → Run workflow**.
5. Run **Actions → Update contribution snake → Run workflow** as well.
6. Check that the Actions runs succeeded and the output branches `output-3d-contrib` and `output` were created.
7. Refresh https://github.com/AliElrouby. The city and snake images appear only after their corresponding workflows publish the first assets. Future updates are scheduled daily.

## If actions cannot push

Go to the profile repository's **Settings → Actions → General → Workflow permissions** and check that GitHub Actions has permission to write repository contents. The workflow includes `permissions: contents: write`, but repository or organization policy can still restrict it.

## If the 3D city or snake looks broken

- Check the **Actions** tab for errors, especially `GITHUB_TOKEN` permission errors.
- Confirm the published URLs exist:
  - `https://raw.githubusercontent.com/AliElrouby/AliElrouby/output-3d-contrib/atlas-city.svg`
  - `https://raw.githubusercontent.com/AliElrouby/AliElrouby/output/snake-dark.svg`
- Allow GitHub's image cache some time to refresh after publication.
- Make sure both workflow files remain under `.github/workflows/` in the *default branch*.

## Customize the colors

- Header and network map: `assets/*.svg` (editable vector graphics)
- Isometric contribution city: `config/atlas-city.json` (`contribColors`, `radarColor`, `backgroundColor`, etc.)
- Snake: `.github/workflows/snake.yml` (query-string `color_snake` and `color_dots` options)
- GitHub stat cards and activity graph: URL query parameters in `README.md`

## Notes

- GitHub contribution counts and third-party statistics come from the user's real public activity. The downloaded package contains no fabricated numbers.
- The city and snake are **not** pre-generated from live data in this package. Running the Actions workflows creates them.
- Some third-party SVG services may have periodic rate limits. Statistics are illustrative metrics, not a full representation of engineering ability.
- The About, experience, skills, and featured work sections are based on the provided CV. If a project repository becomes public later, link it manually without inventing the URL.

## Components

- Custom Neural Atlas header / technical map / footer: created for this profile
- Contribution city: https://github.com/yoshi389111/github-profile-3d-contrib
- Snake: https://github.com/Platane/snk
- Stats: https://github.com/stats-organization/github-stats-extended
- Activity graph: https://github.com/Ashutosh00710/github-readme-activity-graph
- Typing animation: https://github.com/DenverCoder1/readme-typing-svg
