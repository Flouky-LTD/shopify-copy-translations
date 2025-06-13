# Shopify Theme Translation Copier

A Python script to efficiently copy translations between Shopify themes. This tool helps migrate theme-specific translations including JSON templates, section groups, shared data sections, and locale content from a source theme to a destination theme.

## Features

- **Bulk Operations**: Efficiently handles large translation sets with batched GraphQL operations
- **Multiple Resource Types**: Copies translations for:
  - Online Store Theme
  - Theme Section Groups
  - JSON Templates
  - Settings Data Sections
  - Locale Content
- **Performance Optimized**:
  - Batched GraphQL fetches (250 IDs per query)
  - 100-item mutation batches for writes
- **Detailed Logging Options**:
  - Verbose mode for per-resource details
  - Key/value inspection
  - Performance timing metrics
  - Dry-run simulation

## Prerequisites

- Python 3.x
- `requests` library
- Shopify Admin API access token
- Source and destination theme IDs

## Installation

1. Ensure Python 3.x is installed
2. Install required package:
```bash
pip install requests
```

## Usage

```bash
python copy_translations.py --shop YOUR_SHOP.myshopify.com \
                          --source-theme-id SOURCE_THEME_ID \
                          --dest-theme-id DESTINATION_THEME_ID \
                          [--token YOUR_ADMIN_TOKEN] \
                          [--locales en,fr,es] \
                          [--dry-run] \
                          [--verbose] \
                          [--show-keys] \
                          [--timing]
```

### Required Arguments

- `--shop`: Your Shopify shop domain (e.g., your-store.myshopify.com)
- `--source-theme-id`: ID of the theme to copy translations from
- `--dest-theme-id`: ID of the theme to copy translations to
- `--token`: Shopify Admin API token (can also be set via SHOPIFY_ADMIN_TOKEN environment variable)

### Optional Arguments

- `--locales`: Comma-separated list of locales to copy (defaults to all shop locales)
- `--dry-run`: Simulate the copy operation without making changes
- `--verbose`: Show detailed progress for each resource
- `--show-keys`: Display all key/value pairs being copied (implies --verbose)
- `--timing`: Show timing information for each locale

## Examples

Copy all translations between themes:
```bash
python copy_translations.py --shop my-store.myshopify.com \
                          --source-theme-id 123456789 \
                          --dest-theme-id 987654321
```

Copy specific locales with verbose output:
```bash
python copy_translations.py --shop my-store.myshopify.com \
                          --source-theme-id 123456789 \
                          --dest-theme-id 987654321 \
                          --locales en,fr \
                          --verbose
```

Test run without making changes:
```bash
python copy_translations.py --shop my-store.myshopify.com \
                          --source-theme-id 123456789 \
                          --dest-theme-id 987654321 \
                          --dry-run \
                          --show-keys
```

## Performance Notes

- The script uses batched operations to optimize performance
- GraphQL queries are limited to 250 IDs per request
- Translation registrations are batched in groups of 100
- For large themes, the process may take several minutes

## Error Handling

- The script will exit with an error if:
  - No Admin API token is provided
  - GraphQL queries return errors
  - Invalid theme IDs are provided
- All errors are logged with detailed messages

## Contributing

Feel free to submit issues and enhancement requests!
