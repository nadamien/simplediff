import os
import time
import difflib
import tkinter as tk
from tkinter import filedialog, messagebox

# We'll use tkinterdnd2 for drag & drop
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    raise ImportError("Please install tkinterdnd2:\n  pip install tkinterdnd2")

# For rendering HTML in a Tkinter window
try:
    from tkinterweb import HtmlFrame
except ImportError:
    raise ImportError("Please install tkinterweb:\n  pip install tkinterweb")


class ClickableHtmlDiff(difflib.HtmlDiff):
    """
    Subclass of HtmlDiff that:
    - Doesn't escape lines
    - Adds row-level onclick events for toggling highlight
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rownum = 0

    def _dump_div(self, f, lcols, rcols, lid, rid):
        """Overridden to insert an onclick for each row in the table."""
        f.write(f'<tr id="line{self._rownum}" onclick="toggleLineColor(\'line{self._rownum}\')">')
        self._rownum += 1

        template = '<td class="diff_%s">%s</td>\n'
        for col in lcols:
            tag = self._determine_tag(col)
            self._write_line(f, template % (tag, col))
        for col in rcols:
            tag = self._determine_tag(col)
            self._write_line(f, template % (tag, col))

        f.write('</tr>\n')

    def _determine_tag(self, text):
        """If the text includes 'class="diff_add"', 'class="diff_sub"', 'class="diff_chg', label entire cell."""
        low = text.lower()
        if 'class="diff_add"' in low:
            return 'add'
        elif 'class="diff_sub"' in low:
            return 'sub'
        elif 'class="diff_chg"' in low:
            return 'chg'
        else:
            return 'none'


class FancyDragDropDiff(TkinterDnD.Tk):
    """
    A diff tool with:
      - Large drag-and-drop areas for 2 files
      - "Browse" buttons
      - Thin label in the middle showing "No changes detected" (green) or "Changes found" (dark orange)
      - A toggle button to switch between word-wise substring diff vs. inline diff
      - Another toggle to show/hide whitespace by replacing spaces with a bold marker
      - Maximized on startup, resizable=False on Windows
    """
    def __init__(self):
        super().__init__()
        self.title("PWDIFF 1.0")

        # Attempt to start maximized & disable resizing
        self.state("zoomed")
        self.resizable(True, True)

        # Store file paths, diff, toggles
        self.file1_path = ""
        self.file2_path = ""
        self.diff_html_snippet = ""
        self.diff_full_html = ""

        # Toggles
        self.diff_mode = "word"  # "word" or "inline"
        self.show_whitespace = False  # Show/hide whitespace

        # For zoom
        self.zoom_percent = 100

        self.build_gui()

    def build_gui(self):
        # Title
        title_label = tk.Label(
            self, text="PWDIFF Ver 1.0 [M3T4L1C]",
            font=("Segoe UI", 24, "bold")
        )
        title_label.pack(pady=(10,5))

        # Legend
        legend_frame = tk.Frame(self)
        legend_frame.pack(pady=5)

        tk.Label(legend_frame, text="Legend:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=(0, 10))
        self._make_legend_item(legend_frame, "#CCFFFF", "Added lines")
        self._make_legend_item(legend_frame, "#FFCCCC", "Removed lines")
        self._make_legend_item(legend_frame, "#FFF200", "Changed substring")

        # We'll use a grid for the left file area, the middle thin label, and the right file area
        file_frame = tk.Frame(self)
        file_frame.pack(pady=5, padx=10, fill=tk.X)

        # ============ LEFT FILE FRAME ============
        self.left_file_frame = tk.Frame(file_frame, bd=2, relief=tk.GROOVE, padx=10, pady=10)
        self.left_file_frame.grid(row=0, column=0, sticky="nsew", padx=5)

        # Large drag area
        self.drag_label1 = tk.Label(self.left_file_frame, text="DRAG FILE 1 HERE",
                                    width=50, height=8, bd=2, relief="sunken",
                                    bg="#f9f9f9", fg="#666", font=("Arial", 10, "bold"))
        self.drag_label1.pack(pady=5)
        self.drag_label1.drop_target_register(DND_FILES)
        self.drag_label1.dnd_bind("<<Drop>>", self.on_file1_drop)

        # "Browse" button
        self.browse1_btn = tk.Button(
            self.left_file_frame, text="Browse File 1",
            bg="#1e90ff", fg="white", width=15, font=("Arial", 10, "bold"),
            command=self.browse_file1
        )
        self.browse1_btn.pack(pady=(0,5))

        # Info labels for file 1
        self.file1_info = tk.Label(self.left_file_frame, text="(File 1 info will appear here)",
                                   fg="#444", justify=tk.LEFT)
        self.file1_info.pack()

        # ============ MIDDLE THIN LABEL FOR STATUS ============
        self.status_middle_label = tk.Label(file_frame, text="No changes yet", font=("Arial", 10, "bold"),
                                            fg="#999", width=20, relief=tk.FLAT)
        self.status_middle_label.grid(row=0, column=1, padx=(10,10))

        # ============ RIGHT FILE FRAME ============
        self.right_file_frame = tk.Frame(file_frame, bd=2, relief=tk.GROOVE, padx=10, pady=10)
        self.right_file_frame.grid(row=0, column=2, sticky="nsew", padx=5)

        self.drag_label2 = tk.Label(self.right_file_frame, text="DRAG FILE 2 HERE",
                                    width=50, height=8, bd=2, relief="sunken",
                                    bg="#f9f9f9", fg="#666", font=("Arial", 10, "bold"))
        self.drag_label2.pack(pady=5)
        self.drag_label2.drop_target_register(DND_FILES)
        self.drag_label2.dnd_bind("<<Drop>>", self.on_file2_drop)

        self.browse2_btn = tk.Button(
            self.right_file_frame, text="Browse File 2",
            bg="#1e90ff", fg="white", width=15, font=("Arial", 10, "bold"),
            command=self.browse_file2
        )
        self.browse2_btn.pack(pady=(0,5))

        self.file2_info = tk.Label(self.right_file_frame, text="(File 2 info will appear here)",
                                   fg="#444", justify=tk.LEFT)
        self.file2_info.pack()

        file_frame.columnconfigure(0, weight=1)
        file_frame.columnconfigure(2, weight=1)

        # Buttons for Compare, Clear, Export
        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=5)

        self.compare_btn = tk.Button(
            btn_frame, text="Compare", bg="#28a745", fg="white",
            font=("Arial", 10, "bold"), width=12, command=self.compare_files
        )
        self.compare_btn.pack(side=tk.LEFT, padx=5)

        self.clear_btn = tk.Button(
            btn_frame, text="Clear", bg="#f0ad4e", fg="black",
            font=("Arial", 10, "bold"), width=12, command=self.clear_diff
        )
        self.clear_btn.pack(side=tk.LEFT, padx=5)

        self.export_btn = tk.Button(
            btn_frame, text="Export", bg="#6f42c1", fg="white",
            font=("Arial", 10, "bold"), width=12, state=tk.DISABLED, command=self.export_diff
        )
        self.export_btn.pack(side=tk.LEFT, padx=5)

        # Toggle Buttons
        toggle_frame = tk.Frame(self)
        toggle_frame.pack(pady=5)

        # Button to toggle diff mode (word or inline)
        self.diff_mode_btn = tk.Button(toggle_frame, text="Toggle Diff Mode (Word→Inline)",
                                       bg="#FFC107", fg="black", font=("Arial", 10, "bold"),
                                       width=25, command=self.toggle_diff_mode)
        self.diff_mode_btn.pack(side=tk.LEFT, padx=5)

        # Button to show/hide whitespace
        self.whitespace_btn = tk.Button(toggle_frame, text="Show Whitespace",
                                        bg="#FFC107", fg="black", font=("Arial", 10, "bold"),
                                        width=25, command=self.toggle_whitespace)
        self.whitespace_btn.pack(side=tk.LEFT, padx=5)

        # Zoom Slider
        zoom_frame = tk.Frame(self)
        zoom_frame.pack(pady=(5,0))
        tk.Label(zoom_frame, text="Zoom:", font=("Arial", 10, "bold")).pack(side=tk.LEFT)

        self.zoom_scale = tk.Scale(zoom_frame, from_=50, to=200, orient=tk.HORIZONTAL, length=250,
                                   command=self.on_zoom_change)
        self.zoom_scale.set(self.zoom_percent)
        self.zoom_scale.pack(side=tk.LEFT, padx=10)

        # HTML Diff Display
        self.html_display = HtmlFrame(self, horizontal_scrollbar="auto")
        self.html_display.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # ---------------- Legend Helper ----------------
    def _make_legend_item(self, parent, bg_color, label_text):
        f = tk.Frame(parent)
        f.pack(side=tk.LEFT, padx=10)
        box = tk.Label(f, width=2, height=1, bg=bg_color)
        box.pack(side=tk.LEFT)
        tk.Label(f, text=label_text).pack(side=tk.LEFT, padx=5)

    # ---------------- Drag & Drop Handlers ----------------
    def on_file1_drop(self, event):
        files = self._parse_dnd_files(event.data)
        if files:
            self.load_file1(files[0])

    def on_file2_drop(self, event):
        files = self._parse_dnd_files(event.data)
        if files:
            self.load_file2(files[0])

    def _parse_dnd_files(self, data):
        raw = data.strip()
        if raw.startswith('{') and raw.endswith('}'):
            raw = raw[1:-1]
        parts = raw.split('} {')
        cleaned = [p.strip('{}') for p in parts]
        return cleaned

    # ---------------- Browse Buttons ----------------
    def browse_file1(self):
        path = filedialog.askopenfilename(title="Select File 1")
        if path:
            self.load_file1(path)

    def browse_file2(self):
        path = filedialog.askopenfilename(title="Select File 2")
        if path:
            self.load_file2(path)

    def load_file1(self, path):
        if not os.path.isfile(path):
            return
        self.file1_path = path
        self.display_file_info(1, path)
        self.drag_label1.config(text="Loaded: " + os.path.basename(path))

    def load_file2(self, path):
        if not os.path.isfile(path):
            return
        self.file2_path = path
        self.display_file_info(2, path)
        self.drag_label2.config(text="Loaded: " + os.path.basename(path))

    def display_file_info(self, which, path):
        """
        Show full path, size, and last modified in the file info label.
        """
        size_bytes = os.path.getsize(path)
        mod_time = time.ctime(os.path.getmtime(path))
        info_text = f"Full Path: {path}\nSize: {size_bytes} bytes\nLast Modified: {mod_time}"

        if which == 1:
            self.file1_info.config(text=info_text, fg="#000")
        else:
            self.file2_info.config(text=info_text, fg="#000")

    # ---------------- Compare Logic ----------------
    def compare_files(self):
        """Reads both files, optionally modifies whitespace, builds either word or inline diff."""
        if not (os.path.isfile(self.file1_path) and os.path.isfile(self.file2_path)):
            messagebox.showerror("Error", "Please select two valid files.")
            return

        try:
            with open(self.file1_path, "r", encoding="utf-8", errors="replace") as f1:
                text1 = f1.readlines()
            with open(self.file2_path, "r", encoding="utf-8", errors="replace") as f2:
                text2 = f2.readlines()

            # If user toggles show_whitespace, we highlight them. Let's replace spaces with a bold marker "**" for instance
            # or you can replace with any symbol. We'll do a simple approach:
            if self.show_whitespace:
                text1 = [line.replace(" ", "**") for line in text1]
                text2 = [line.replace(" ", "**") for line in text2]

            # Check if identical
            # (Note: we do .splitlines() vs. .readlines()—some differences in trailing newlines, but let's keep it simple.)
            stripped1 = [l.rstrip('\n') for l in text1]
            stripped2 = [l.rstrip('\n') for l in text2]
            if stripped1 == stripped2:
                self.status_middle_label.config(text="No changes detected", fg="green")
            else:
                self.status_middle_label.config(text="Changes found", fg="#FF8C00")

            # Build the snippet
            if self.diff_mode == "word":
                # partial substring highlight side-by-side
                differ = ClickableHtmlDiff(wrapcolumn=80, linejunk=None, charjunk=None)
                snippet = differ.make_table(
                    text1, text2,
                    fromdesc=self.file1_path,
                    todesc=self.file2_path,
                    context=False, numlines=0
                )
            else:
                # "inline" approach - let's do HtmlDiff make_file with context
                differ = ClickableHtmlDiff(wrapcolumn=80)
                snippet = differ.make_file(
                    text1, text2,
                    fromdesc=self.file1_path,
                    todesc=self.file2_path,
                    context=True, numlines=3
                )

            self.diff_html_snippet = snippet
            self.build_final_html()
            self.html_display.load_html(self.diff_full_html)
            self.export_btn.config(state=tk.NORMAL)

        except Exception as e:
            messagebox.showerror("Compare Error", str(e))

    def build_final_html(self):
        """Wrap snippet with CSS & JS for row highlight toggling."""
        # We'll strip out any <html> or <body> from snippet if it has them (especially inline mode).
        s = self.diff_html_snippet
        s = s.replace("<!DOCTYPE html>", "")
        s = s.replace("<html>", "").replace("</html>", "")
        s = s.replace("<head>", "").replace("</head>", "")
        s = s.replace("<body>", "").replace("</body>", "")

        css = f"""
        <style>
        body {{
          font-family: Consolas, monospace;
          font-size: {self.zoom_percent}%;
          margin: 10px;
        }}
        table.diff {{
          width: 100%;
          border-collapse: collapse;
        }}
        table.diff th {{
          background-color: #eee;
          padding: 6px;
          border: 1px solid #ccc;
          color: #000;
        }}
        table.diff td {{
          border: 1px solid #ccc;
          padding: 4px;
          vertical-align: top;
        }}
        .diff_header {{
          background-color: #ccc; 
          color: #000;
        }}
        .diff_next {{
          background-color: #ccc; 
          color: #000;
        }}
        .diff_add {{
          background-color: #CCFFFF; 
        }}
        .diff_sub {{
          background-color: #FFCCCC; 
          font-weight: bold;
          text-decoration: underline red;
        }}
        .diff_chg {{
          background-color: #FFF200; 
          font-weight: bold;
          text-decoration: underline #666600;
        }}
        span.diff_chg {{
          background-color: #FFF200 !important;
          font-weight: bold;
          text-decoration: underline #666600;
        }}
        .highlighted {{
          background-color: #FFFF88 !important;
        }}
        </style>
        <script>
        function toggleLineColor(rowId) {{
          var row = document.getElementById(rowId);
          if (row && row.classList.contains('highlighted')) {{
            row.classList.remove('highlighted');
          }} else if (row) {{
            row.classList.add('highlighted');
          }}
        }}
        </script>
        """
        self.diff_full_html = (
            "<html><head>"
            f"{css}"
            "</head><body>"
            f"{s}"
            "</body></html>"
        )

    # ---------------- Clear + Export ----------------
    def clear_diff(self):
        self.file1_path = ""
        self.file2_path = ""
        self.drag_label1.config(text="DRAG FILE 1 HERE")
        self.drag_label2.config(text="DRAG FILE 2 HERE")
        self.file1_info.config(text="(File 1 info will appear here)", fg="#444")
        self.file2_info.config(text="(File 2 info will appear here)", fg="#444")
        self.diff_html_snippet = ""
        self.diff_full_html = ""
        # Reset middle label
        self.status_middle_label.config(text="No changes yet", fg="#999")
        self.html_display.load_html("")
        self.export_btn.config(state=tk.DISABLED)

    def export_diff(self):
        if not self.diff_full_html:
            return
        outpath = filedialog.asksaveasfilename(
            defaultextension=".html",
            filetypes=[("HTML files", "*.html"), ("All files", "*.*")]
        )
        if outpath:
            try:
                with open(outpath, "w", encoding="utf-8") as f:
                    f.write(self.diff_full_html)
                messagebox.showinfo("Export Successful", f"Diff saved to:\n{outpath}")
            except Exception as e:
                messagebox.showerror("Export Error", str(e))

    # ---------------- Zoom Slider ----------------
    def on_zoom_change(self, val):
        self.zoom_percent = int(float(val))
        if self.diff_html_snippet:
            self.build_final_html()
            self.html_display.load_html(self.diff_full_html)

    # ---------------- Toggle Diff Mode ----------------
    def toggle_diff_mode(self):
        """Toggle between word-wise (substring highlight) and inline (make_file) diff modes."""
        if self.diff_mode == "word":
            self.diff_mode = "inline"
            self.diff_mode_btn.config(text="Toggle Diff Mode (Inline→Word)")
        else:
            self.diff_mode = "word"
            self.diff_mode_btn.config(text="Toggle Diff Mode (Word→Inline)")

        # Re-compare if both files loaded
        if self.file1_path and self.file2_path:
            self.compare_files()

    # ---------------- Toggle Show Whitespace ----------------
    def toggle_whitespace(self):
        """
        Toggle self.show_whitespace. If True, we replace ' ' with '**' in compare_files.
        Then re-run compare if both files loaded.
        """
        self.show_whitespace = not self.show_whitespace
        if self.show_whitespace:
            self.whitespace_btn.config(text="Hide Whitespace")
        else:
            self.whitespace_btn.config(text="Show Whitespace")

        if self.file1_path and self.file2_path:
            self.compare_files()


if __name__ == "__main__":
    app = FancyDragDropDiff()
    app.mainloop()
