# MARK EDITOR

A simple Markdown editor which is based on the Python implementation of [John Gruber’s Markdown](https://daringfireball.net/projects/markdown/), [PyMdown Extensions](https://facelessuser.github.io/pymdown-extensions/), and some [add-ons](#add-ons).

The editor's name in the [title bar](#title-bar) is "Mark Editor".

The editor consists of a [menu bar](#menus) at the top, two parallel [panels](#panels) (the left one is the editing panel, the right one is the quick view panel) and a [status bar](#status-bar) at the bottom. The user can decrease (zoom out) or increase (zoom in) the text size in the quick view panel. Content in the quick view panel is refreshed after each action. Fonts for the editor's interface and panels are defined in the [fonts section](#fonts).

The editor can save files in its own Markdown (.md) format and export them to plain text (.txt) and PDF (.pdf) formats.

See [functions](#functions) for details. [How it works?](#how-it-works)

The technologies used are defined in the [code base section](#code-base). 

**The application was created in `OpenCode` (model　`DeepSeek V4 Flash Free`).**

## CODE BASE {#code-base}

Primarily, the editor is written as a single file using Python 3 (3.13+), Tkinter, and Markdown – see requirements.txt.

Then, the Python file with all its libraries is compiled into 1) a single executable file (for GNU/Linux) and 2) an AppImage. See [creating the application](#creating-the-application) for details.

## FUNCTIONS {#functions}

The main functions of the editor:

- select all text;

- edit (cut/copy/paste);

- delete lines (blocks of text);

- undo/redo operations;

- find and replace text;

- format text (bold, italic, underline, strikethrough, subscript, superscript, inline code, marked text);

- add links and footnotes;

- label parts of text as headings, paragraphs, ordered or unordered lists, blockquotes, comments, etc.;

- add blocks of code;

- add tables;

- add links to images;

- add horizontal rules;

- insert furigana in Japanese texts;

- clear formatting;

- do some typographic replacements;

- create new files, save files (including 'Save As' action using a new file name), open existing files, reopen files (close without saving and open them again);

- export files to other formats (plain text and PDF);

- use commands from menus or shortcuts for operations.

## TITLE BAR {#title-bar}

The title bar at the very top of the application window matches the following template: {Mark Editor} - {symbol of editing}{file name}:

- If the file already exists, the {file name} field displays the actual file name.

- A new file that has not yet been saved is displayed in the {file name} field as 'New File'.

- If the file has been edited but not yet saved, the {symbol of editing} field is displayed as '*'; if the file with the latest changes is saved, the {symbol of editing} field is blank.

## MENUS {#menus}

The menu bar includes the following menus: [File](#file-menu), [Edit](#edit-menu), [Format](#format-menu), [Paragraph](#paragraph-menu), [View](#view-menu), and [Help](#help-menu). Commands in each menu are divided with separators. Commands also have their own shortcuts.

### File {#file-menu}

- New File (Ctrl+N) - creates a new blank file; if the existing file is open and the latest changes have not been saved yet, this command opens a dialog box ("Save the opened file?" "Yes/No") before closing this file and then creates a new one.

- separator

- Open (Ctrl+O) - opens an existing file from disk.

- Reopen (Ctrl+Shift+O) - closes the file opened in the program after asking about saving changes via a dialog box ('Save the opened file?' -> 'Yes/No') and reopens it.

- separator

- Save (Ctrl+S) - saves the file opened in the program to disk.

- Save As (Ctrl+Shift+S) - saves the file opened in the program to disk with a different name.

- Convert (Ctrl+E) - opens a dialog box to save a file in another format:
  
  * Plain text file (.txt) - clears all formatting from the document and saves the file as plain text (Unix/Linux text file format, UTF-8);
  
  * PDF file (.pdf) - converts a file to PDF using Pandoc and saves it;

- Quit (Ctrl+Q) - exit the application (asking about saving any changes via a dialog box).

### Edit {#edit-menu}

- Undo (Ctrl+Z) - reverses the last action, reverting to the previous state;

- Redo (Ctrl+Shift+Z) - reverses the Undo command, reapplying the previously removed action;

- separator

- Cut (Ctrl+X) - cuts the selected part of text and places it in the system clipboard;

- Copy (Ctrl+C) - copies the selected part of text to the system clipboard;

- Paste (Ctrl+V) - pastes the part of text from the system clipboard;

- separator

- Find (Ctrl+F) - scans the document for a specific word, phrase, or pattern (patterns use regex format, which is enabled by a checkbox in the search dialog box);

- Replace (Ctrl+R) - scans for the target text, highlights the first match, and gives manual control. The user can press the 'Replace' button in the replace dialog box to change just that single instance, or 'Find Next' to skip it and move to the next occurrence;

- Replace All (Ctrl+Shift+R) - instantly changes every matching occurrence of the target text across the entire document or selected part of text with a single click in the replace all dialog box;

- separator

- Select All (Ctrl+A) - selects the entire document;

- Remove Selection (Ctrl+Shift+A);

- Line Up (Ctrl+Arrow Up) - moves the line (block of text, paragraph, etc. - see [panels](#panels) for details) under the cursor to a position before the preceding one;

- Line Down (Ctrl+Arrow Down) - moves the line (block of text, paragraph, etc.) currently under the cursor to a position after the next line.

- Delete Line (Ctrl+Y) - deletes the current line (block of text, paragraph, etc.) - the line under the cursor;

### Format {#format-menu}

- Bold (Ctrl+B) - makes selected text bold, adding 2 asterisks before and after a word or phrase, e.g., **bold text**;

- Italic (Ctrl+I) - makes selected text italic, adding 1 asterisk before and after a word or phrase, e.g., *italic text*;

- Underline (Ctrl+U) - makes selected text underlined using double carets (^^) before and after the characters, e.g., ^^underlined text^^, which is rendered as <u>underlined text</u> (use this extension from PyMdown Extensions: `markdown.Markdown(extensions=['pymdownx.caret'])`);

- Strikethrough (Ctrl+D) - uses double tilde symbols (~~) before and after the selected text to strikethrough it, e.g., ~~the strikethrough~~, which is rendered as <del>The strikethrough</del> (use this extension from PyMdown Extensions: `markdown.Markdown(extensions=['pymdownx.tilde'])`);

- separator

- Superscript (Ctrl+Shift+P) - creates a superscript (to position one or more characters slightly above the normal line of type) using carets (^) before and after the characters, e.g., H^2^ is rendered as H<sup>2</sup> (use this extension from PyMdown Extensions: `markdown.Markdown(extensions=['pymdownx.caret'])`);

- Subscript (Ctrl+Shift+B) - creates a subscript (to position one or more characters slightly below the normal line of type) using the tilde before and after the characters, e.g., H~2~O, which is rendered as H<sub>2</sub>O (use this extension from PyMdown Extensions: `markdown.Markdown(extensions=['pymdownx.tilde'])`);

- Inline Code (Ctrl+K) - marks selected text as inline code by wrapping it with backticks (`...`), e.g., `inline code`;

- Mark (Ctrl+Shift+M) - highlights text in a special (yellow) color by surrounding it with double equal signs (==), e.g., ==marked text==, which is rendered as <mark>marked text</mark> (use this extension from PyMdown Extensions: `markdown.Markdown(extensions=['pymdownx.mark'])`);

- separator

- Header ID (Ctrl+H) - adds a space and a custom ID to the end of the heading, enclosing the custom ID in curly braces, e.g.: `# Heading {#id}`;

- Header Link (Ctrl+Shift+H) - opens a dialog box to insert a link to the header with ID using the hyperlink pattern where the header ID is the URL (with a number sign (#) followed by the custom heading ID), e.g., [link](#id);

- Hyperlink (Ctrl+L) - opens a dialog box to create a link by enclosing the link text (selected text) in brackets ([...]) and then following it immediately with the URL in parentheses ((...)) (e.g., [Text](https://foo.com));

- Footnote (Ctrl+Shift+T) - creates a footnote using a dialog box to enter a Footnote Reference/Name inline in the text, and a Footnote Definition - a new line at the end of the document (both references and names are marked like [^text], and definitions are preceded by [^text]: , e.g.:

Footnotes: a reference[^1] and a name[^word].

[^1]: This is a footnote definition.

[^word]: A footnote with the name "word".

Footnotes are created using Python-Markdown: `markdown.Markdown(extensions=['footnotes'])`.

- separator

- Furigana (Ctrl+Shift+U) - adds [Furigana](#furigana) symbols to Japanese kanji with a special dialog box;

- Date and Time (Ctrl+Shift+D) - opens a dialog box to insert the system [date and/or time](#date-and-time);

- Special Mark (Ctrl+Shift+L) - inserts a backslash (\) directly at the cursor position to mark special formatting symbols (like *, _, #, or >) as plain text;

- separator

- Clear Formatting (Ctrl+Shift+F) - strips away all applied text styles (such as bold, italic, etc.), removes all text block marks (such as headings, code blocks, and blockquotes), and removes other elements (such as image links and horizontal rules).

### Paragraph {#paragraph-menu}

- Heading 1 (Alt+Ctrl+1) - marks the line (the block of text) under the cursor as a first-level heading using (#);

- Heading 2 (Alt+Ctrl+2) - marks the line (the block of text) under the cursor as a second-level heading using (##);

- Heading 3 (Alt+Ctrl+3) - marks the line (the block of text) under the cursor as a third-level heading using (###);

- Heading 4 (Alt+Ctrl+4) - marks the line (the block of text) under the cursor as a fourth-level heading using (####);

- Heading 5 (Alt+Ctrl+5) - marks the line (the block of text) under the cursor as a fifth-level heading using (#####);

- Heading 6 (Alt+Ctrl+6) - marks the line (the block of text) under the cursor as a sixth-level heading using (######);

- separator

- Paragraph (Alt+Ctrl+0) - creates a new paragraph or marks the line (the block of text) under the cursor as a paragraph using a blank line before it;

- Ordered List (Ctrl+G) - creates an ordered (numbered by 1., 2., 3., etc.) list item or marks the line as an ordered list item;

- Unordered List (Ctrl+Shift+G) - creates an unordered (bulleted by *) list item or marks the line as an unordered list item;

- separator

- Code Block (Ctrl+Shift+K) - creates fenced code blocks by placing 3 backticks (```) before and after the line, opens a dialog box to add a name of the programming language after the first 3 backticks, e.g.:

```python
print('Hello, World!')
```

- Blockquote (Ctrl+Shift+Q) - creates a new blockquote or marks the line as a blockquote by adding (>) in front of the line;

- Table (Ctrl+T) - displays a dialog box to create a table (asks for the number of columns and rows) using the vertical line (|) to separate each column, and uses three or more dashes (---) to create each column's header, a vertical line should also be added at either end of the row, e.g.:

Header 1 | Header 2 | Header 3
-------- | -------- | --------
Cell 1-1 | Cell 1-2 | Cell 1-3
Cell 2-1 | Cell 2-2 | Cell 2-3
Cell 3-1 | Cell 3-2 | Cell 3-3

Tables are defined using the syntax established in [PHP Markdown Extra](http://www.michelf.com/projects/php-markdown/extra/#table). They are rendered using TableExtension from Python-Markdown: `markdown.markdown(text, extensions=[TableExtension(use_align_attribute=True)])`

<table>
  <thead>
    <tr>
      <th>Header 1</th>
      <th>Header 2</th>
      <th>Header 3</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Cell 1-1</td>
      <td>Cell 1-2</td>
      <td>Cell 1-3</td>
    </tr>
    <tr>
      <td>Cell 2-1</td>
      <td>Cell 2-2</td>
      <td>Cell 2-3</td>
    </tr>
    <tr>
      <td>Cell 3-1</td>
      <td>Cell 3-2</td>
      <td>Cell 3-3</td>
    </tr>
  </tbody>
</table>

- Image (Ctrl+Shift+I) - adds a link to the image (an exclamation mark (!), followed by alt text in brackets, and the path or URL to the image in parentheses), e.g., ![Alt text](/path/to/file/or/URL/image.png "Optional title"), using a special dialog box;

- separator

- Line Break (Ctrl+\) - treats a newline in a block of text as a hard break by adding two spaces and a newline (`  \n`), which is rendered as `<br />`;

- Horizontal Rule (Ctrl+_) - creates a horizontal rule - a new line with (***);

- separator

- Add Indent (Tab) - adds an indentation (2 spaces by default);

- Remove Indent (Shift+Tab) - removes the indentation of the line under the cursor;

- separator

- Comment (Ctrl+M) - creates a comment block or marks the line as a comment by using HTML comment tag `<!-- ... -->`, e.g. <!-- Comments --> (hidden in quick view panel).

### View {#view-menu}

- Zoom In (Ctrl++) - increases the font size in the quick view panel by 2 pt;

- Zoom Out (Ctrl+-) - decreases the font size in the quick view panel by 2 pt;

- separator

- Refresh (Ctrl+Shift+E) - updates the document display in the quick view panel, synchronizing it with the text in the editing panel.

### Help {#help-menu}

- Markdown - opens the link [John Gruber’s Markdown](https://daringfireball.net/projects/markdown/) in the system browser.

- About Editor - shows a window with the text 'Mark Editor, version 0.1 (2026.07)' and the button 'Close'.

## PANELS {#panels}

Both panels are equal in size. The editing panel where the user enters text is on the left; the quick view panel displaying the document in Markdown format is on the right. The text in both panels changes synchronously.

Thanks to PyMdown Extensions, the quick view panel automatically renders some character combinations (e.g., (c) or (C), (r) or (R), (tm) or (TM), and +-) as typographic symbols (©, ®, ™, and ±) - use SmartSymbols: `markdown.Markdown(extensions=['pymdownx.smartsymbols'])`.

Images are displayed using Pillow library (if installed), otherwise the image name and path are shown as a placeholder.

## STATUS BAR {#status-bar}

The column/character position of the cursor in the editing panel appears on the right side of the bottom status bar.

## FONTS {#fonts}

Each font definition includes a category (Sans, Serif, or Mono), a user typeface, a Liberation font, and a general typeface. The editor tries each in order and uses the first one found on the system.

| Usage          | Category | User typeface    | Liberation font      | General typeface |
|----------------|----------|------------------|----------------------|------------------|
| Interface      | Sans     | Noto Sans        | Liberation Sans      | Arial            |
| Editor panel   | Mono     | Fira Code 14 pt  | Liberation Mono      | Courier 14 pt    |
| Quick view     |          |                  |                      |                  |
| └ Headings     | Sans     | Noto Sans (bold) | Liberation Sans      | Arial            |
| └ Body text    | Serif    | Noto Serif 14 pt | Liberation Serif     | Times 14 pt      |
| └ Code/table   | Mono     | Fira Code 13 pt  | Liberation Mono      | Courier 13 pt    |

Heading font sizes are: H1 24 pt, H2 22 pt, H3 20 pt, H4 18 pt, H5 16 pt, H6 14 pt, all bold.

Zoom in/out increases or decreases the font size in the quick view panel by 2 pt.

## ADD-ONS {#add-ons}

### Pillow {#pillow}

[Pillow](https://python-pillow.org/) library is used to display images in the quick view panel and to support image rendering in PDF export. If Pillow is not installed, images are shown as text placeholders with their filename and path.

### Furigana {#furigana}

Furigana is a Japanese reading aid consisting of smaller kana printed above either kanji or other characters to indicate their pronunciation. It is one type of ruby text and the pattern is <ruby>漢字<rt>かんじ</rt></ruby>.

## Date and Time {#date-and-time}

Insert the system date and/or time: the dialog box shows options to insert the date and time, the date only, or the time only.

## CREATING THE APPLICATION {#creating-the-application}

1. First, the code is created for an editor window with two panels and a status bar.

2. Then, the code is written for each command in the menu, one after the other. After writing the code for a command, it is tested, and only if the tests pass successfully is the code for the next command implemented.

3. After successful tests, the finished Python 3 file is compiled with all its libraries into a single executable file for GNU/Linux and a portable AppImage (using the Makefile).

The result is shown to the user.

## HOW IT WORKS {#how-it-works}

See Test_Page in [Markdown](./test_page/Test_Page.md), [PDF](./test_page/Test_Page.pdf) and [TXT](./test_page/Test_Page.txt).