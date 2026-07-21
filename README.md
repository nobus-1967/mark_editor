# MARK EDITOR

![mark_editor](./images/mark_editor.png)

A simple Markdown editor which is based on the Python implementation of [John Gruber’s Markdown](https://daringfireball.net/projects/markdown/), [PyMdown Extensions](https://facelessuser.github.io/pymdown-extensions/), and some add-ons.

The editor's name is "Mark Editor".

The editor consists of a menu bar at the top, two parallel panels (the left one is the editing panel, the right one is the quick view panel) and a status bar at the bottom. The user can decrease (zoom out) or increase (zoom in) the text size in the quick view panel. Content in the quick view panel is refreshed after each action.

The editor can save files in its own Markdown (.md) format and export them to plain text (.txt) and PDF (.pdf) formats.

See Functions section for details.

The technologies used are defined in the Code Base section.

**The application was created in `OpenCode` (model `DeepSeek V4 Flash Free`).**

## CODE BASE

Primarily, the editor is written as a single file using Python 3 (3.13+), Tkinter, and Markdown – see requirements.txt. [ttkbootstrap](https://github.com/israel-dryer/ttkbootstrap) is used as a modern theming extension for Tkinter.

Then, the Python file with all its libraries is compiled into 1) a single executable file (for GNU/Linux) and 2) an AppImage.

## FUNCTIONS

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

- toggle modern light and dark themes (you can also change themes, see the [list of ttkbootstrap themes](./ttkbootstrap-themes.md));

- use commands from menus or shortcuts for operations.

## ADD-ONS

### Pillow

The [Pillow](https://python-pillow.org/) library is used to display images in the quick view panel and to support image rendering in PDF export. If Pillow is not installed, images are shown as text placeholders with their filename and path.

### Furigana

Furigana is a Japanese reading aid consisting of smaller kana printed above either kanji or other characters to indicate their pronunciation. It is one type of ruby text and the pattern is <ruby>漢字<rt>かんじ</rt></ruby>.

## DATE AND TIME

Insert the system date and/or time: the dialog box shows options to insert the date and time, the date only, or the time only.

## HOW IT WORKS

See Test_Page in [Markdown](./test_page/Test_Page.md), [PDF](./test_page/Test_Page.pdf) and [TXT](./test_page/Test_Page.txt).