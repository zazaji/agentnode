# Document Plugin

Install `agentnode[documents]`.

## XLSX
- read workbook/sheet/range;
- set a rectangular range;
- create workbooks;
- append rows;
- save using temporary file + replace.

## DOCX
- extract paragraphs and tables;
- create a document;
- replace text inside runs/cells with expected-count protection.

## PDF
- extract page text;
- merge PDFs.

All paths pass through FileManager's allowed-root check. Document operations use separate `document.read` / `document.write` scopes.
