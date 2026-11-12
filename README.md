# 📝 Notely

School notes without the Obsidian-sized learning curve. One page, three
words: **write, see, find**. Markdown when you want it, buttons when you
don't, and a **Guide tab** that explains every structure with a
copy-paste example.

## Run it

Double-click **`start.bat`** → opens `http://127.0.0.1:8565/`.

## The two tabs

| Tab | What it does |
|---|---|
| **Notes** | Sidebar with search + note list, editor with a Write / Split / Read toggle, one-click formatting toolbar, autosave |
| **Guide & explain** | The explainer: every markdown structure shown as *plain text → rendered result* side by side, with a **Copy** button. Plus one-click templates (Cornell notes, flashcards, exam prep) |

## What's in it

- **Real files** — every note is a `.md` file in `notely/notes/` (like an
  Obsidian vault). Copy them, back them up, open them anywhere. Deleted
  notes go to `notely/trash/` (recoverable).
- **Autosave** (0.8 s after you stop typing) + `Ctrl+S` manual save
- **Split view** — type on the left, live formatted preview on the right
- **Toolbar** — H1/H2/H3, bold, italic, highlight, strikethrough, inline
  code, lists, checkboxes, callout box, table, code block, divider, link
- **Markdown supported**: headings, bold/italic, `==highlight==`,
  `~~strike~~`, `code`, fenced code blocks, bullet/numbered/task lists,
  callouts (`>`), tables, links, images (drop a file into `notes/` and
  reference it by name), horizontal rules
- **Search inside notes** — the sidebar search matches titles *and* content
- **Keyboard**: `Ctrl+S` save · `Ctrl+N` new note · `Ctrl+B` bold ·
  `Ctrl+I` italic
- **Offline mirror** — if the server dies mid-edit your last change is kept
  in the browser and restored on next open
- **Download .md** exports the open note as a file

## How notes are named

The **title field** is the filename. Rename the title → the `.md` file is
renamed (old one goes to `trash/`).

## Files

| File | Role |
|---|---|
| `index.html` | the whole app (UI + markdown renderer + autosave) |
| `bridge.py` | tiny local server — vault read/write, binds 127.0.0.1 |
| `start.bat` | launches the server hidden + opens the browser |
| `notes/` | your vault (real `.md` files) |
| `trash/` | deleted notes (just move a file back to restore) |

## Roadmap

- Tag/`[[wikilink]]` connections between notes
- Image paste directly into the editor
- Panels backlinks ("which notes link here")
- Export whole vault to PDF/HTML
