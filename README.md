# Amazon Catalog Auditor

**Instant catalog health audits for Amazon sellers**

Upload your Amazon Category Listing Report and get a full audit of your catalog — missing attributes, policy violations, content quality issues, and more. Available as a web app and CLI.

## Features

- **5 Audit Checks** — Critical, recommended, and insight-level checks mapped to Amazon's catalog rules
- **SKU-Level Breakdown** — Every issue traced to a specific SKU and flat file column
- **CSV Export** — Download results for offline analysis
- **Privacy First** — Your catalog data is processed securely and never shared

## Audit Checks

### Critical
- **Missing Required Attributes** — Fields Amazon requires to keep your listing active and buyable
- **Prohibited Characters** — Illegal characters in titles, bullets, and descriptions that trigger policy violations

### Recommended
- **Missing Recommended Attributes** — Optional attributes that impact search ranking, filter visibility, and conversion
- **Title Policy Violations** — Titles exceeding 200 characters or containing prohibited characters

### Insights
- **Bullets Content Quality** — Evaluates bullet point length, specificity, structure, and audience targeting

## Web App

The web app provides a visual dashboard with:
- Catalog completeness score
- Issue distribution by severity
- SKU summary table with drill-down
- Full report unlock via Stripe checkout
- Report delivery via email

## CLI Usage

```bash
# Run all catalog checks
catalog scan my-catalog.xlsx

# Run a specific check
catalog check missing-attributes my-catalog.xlsx

# Export results as CSV
catalog scan my-catalog.xlsx --format csv --output audit.csv

# List available queries
catalog list-queries my-catalog.xlsx
```

## How to Get Your CLR

1. Go to **Amazon Seller Central** → **Catalog** → **Category Listing Report**
2. Click **Generate Report**
3. Download the `.xlsm` or `.xlsx` file
4. Upload it to the web app or run the CLI

## Requirements

- Python 3.7+
- openpyxl
- click
- rich
- Flask (web app)

## License

MIT License — Free to use, modify, and distribute.

Originally built by Brett Wilson ([@BWB03](https://github.com/BWB03)).

Developed and maintained by **Online Seller Solutions** — [onlinesellersolutions.com](https://onlinesellersolutions.com)

---

&copy; 2026 Online Seller Solutions. All rights reserved.
