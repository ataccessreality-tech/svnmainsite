# SVN ShivaJyothi Group website

Complete editable website with a prebuilt production site in `dist/`.
Includes the latest leadership profiles and supplied photographs.

## Upload to GitHub

1. Extract this ZIP.
2. Create a private GitHub repository, for example `svn-shivajyothi-website`.
3. Upload the contents of the extracted `SVN-Website` folder, including `dist`, to the repository. Upload the extracted files, not the ZIP itself.
4. Commit the files. You can upload in batches if GitHub requests it.

## Build and check

Requires Python 3. Node.js is used by the asset validator to check JavaScript.
No npm dependencies are required.

```sh
python3 build.py
python3 tools/validate.py
python3 tools/check_assets.py
```

## Preview locally

```sh
python3 -m http.server 8000 --directory dist
```

Open http://localhost:8000. Use a local server because links are root-relative.

## Hosting

Publish the contents of `dist/` on a static web host. The prebuilt files do not require a build step. Source templates are in `src/`, content in `data/`, and images/styles/scripts in `assets/`.

Canonical URLs currently use https://svnshivajyothigroup.com. For another domain, build with `python3 build.py --site-url https://your-domain.example` and update the default site URL in `data/facts.json`.

This package excludes the private review hosting configuration and credentials. It does not deploy anything automatically. Legal draft pages retain their noindex setting. GA4 and CRM integrations are unconfigured; enquiries use the existing WhatsApp fallback. Pending district/location and legal facts still need owner confirmation. Automated build and asset checks pass; a complete visual browser review has not been performed.

Source revision: 2203c7035e94e3819ef526dc84afe67174b11131.
