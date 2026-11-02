# Static dashboard deployment

The existing public dashboard is [GovernAI on Netlify](https://governai-poojan-desai.netlify.app).
It displays sanitized synthetic snapshots. Publishing it does not execute AWS,
Snowflake, dbt, an ingestion API or a live monitoring service.

The production build emits browser assets to `dist/client`. Netlify uses that
directory; `dist/server` is the separate Sites worker and is not uploaded to
Netlify. Never deploy the repository root, `.local`, credentials or runtime data.

## Verify and deploy to the existing site

```sh
npm ci
npm test
netlify deploy --prod --no-build --dir dist/client \
  --site 9f123626-4f7f-4f0a-8595-0e9aee773406
```

This requires an already authorized Netlify account. The explicit site ID keeps
the deployment attached to the existing GovernAI site; do not create another site.
The site currently uses manual deployments rather than a connected repository.
No account or site security settings need to change.

The build writes `version.json` containing only the source commit, project name
and build timestamp. Compare the live [version record](https://governai-poojan-desai.netlify.app/version.json)
with the commit and the local build before reporting a release. Also confirm the
live JavaScript/CSS assets match the build and the Control evidence screen is
available. A successful GitHub push is separate from a successful deployment.

## Evidence refresh

`npm run demo` regenerates the synthetic local pipeline snapshot; `npm run
controls` executes the seven isolated procedures and refreshes their sanitized
report/checksum. Inspect and commit these artifacts before building a release.
Neither command performs live cloud operations. Historical snapshots remain
labeled as historical rather than implying continuous monitoring.
