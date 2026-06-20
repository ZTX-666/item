Contacts are stored in:

  contacts.xlsx   (primary — edit this file in Excel)

First row must be the English headers (exactly):

  abbrev | name | name_zh | title | company | aliases | signature_image

- One data row per person. "abbrev" is required; leave other cells blank if not used.
- "aliases": comma or Chinese comma separated in a single cell.
- "signature_image": full path or path relative to the skill folder (same folder as SKILL.md).

If you still have the old contacts.json, the first run of the CLI or Word script will
import it into contacts.xlsx, save contacts.json.bak, and remove contacts.json.
