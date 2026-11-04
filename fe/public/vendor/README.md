# Vendored third-party files

| File | Source | Version | SHA-256 |
|---|---|---|---|
| `alpine-csp-3.14.9.min.js` | `https://cdn.jsdelivr.net/npm/@alpinejs/csp@3.14.9/dist/cdn.min.js` | 3.14.9 | `820bc9503874024057da244dc30c21301548329eb9a00e7937e91c4d3908b273` |

The CSP build is used because the standard Alpine build needs `'unsafe-eval'`. Vendoring keeps the page working offline and avoids a third-party script origin. To upgrade, download the new version, update the file name in `index.html`, and record the new hash here.
