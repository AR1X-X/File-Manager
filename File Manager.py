# Created by : @oAmricao
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os, shutil, datetime, threading, subprocess, sys, string, fnmatch, zipfile, csv, queue

BG, PANEL, PANEL_2 = "#05080f", "#0d1524", "#131f33"
ACCENT, ACCENT_D = "#ff8c32", "#e2571b"
RED, YELLOW, GREEN, CYAN = "#ff5c5c", "#ffd166", "#39ff8b", "#4dd6ff"
TEXT, MUTED, BORDER = "#e8ecf4", "#5a6478", "#223050"

try:
    from send2trash import send2trash
    HAS_TRASH = True
except Exception:
    HAS_TRASH = False

ICONS = {".txt": "📄", ".pdf": "📕", ".doc": "📘", ".docx": "📘", ".py": "🐍", ".html": "🌐", ".css": "🎨", ".js": "📜", ".jpg": "🖼", ".jpeg": "🖼", ".png": "🖼", ".gif": "🖼", ".mp3": "🎵", ".mp4": "🎬", ".zip": "🗜", ".rar": "🗜", ".exe": "⚙️", ".xlsx": "📊", ".json": "🗃"}

SEARCH_PLACEHOLDER = "جست‌وجو در این پوشه..."

def fmt_size(n):
    try:
        n = float(n)
        for unit in ("B", "KB", "MB", "GB"):
            if n < 1024 or unit == "GB":
                return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
            n /= 1024
    except Exception:
        return "؟"

def icon_for(name, is_dir):
    if is_dir:
        return "📁"
    return ICONS.get(os.path.splitext(name)[1].lower(), "📄")

def is_hidden_path(full, name):
    if name.startswith("."):
        return True
    if os.name == "nt":
        try:
            import ctypes
            a = ctypes.windll.kernel32.GetFileAttributesW(str(full))
            if a != -1 and (a & 2):
                return True
        except Exception:
            pass
    return False

def drive_free_str(p):
    try:
        u = shutil.disk_usage(p)
        f = u.free
        if f >= 1024**3:
            return f"{f/1024**3:.0f}G آزاد"
        elif f >= 1024**2:
            return f"{f/1024**2:.0f}M آزاد"
        else:
            return fmt_size(f)
    except Exception:
        return ""

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("File Manager v4.0")
        self.geometry("1060x680")
        self.minsize(860, 540)
        self.configure(bg=BG)
        self.current = os.path.expanduser("~")
        self.clipboard = None
        self.back_stack = []
        self.all_entries = []
        self.sort_key = "name"
        self.sort_rev = False
        self.in_scan = False
        self.scan_map = {}
        self.scan_all = []
        self.scan_stop = False
        self.copy_stop = False
        self.drives_listbox = None
        self.show_hidden = tk.BooleanVar(value=False)
        self.tabs = [self.current]
        self.tab_index = 0
        self._closing = False
        self._job_poll = None
        self.ui_queue = queue.Queue()
        self._build_titlebar()
        self._build_toolbar()
        self._build_toolbar2()
        self._build_body()
        self._build_statusbar()
        self._bind_shortcuts()
        self._refresh_drive_box()
        self.load_dir(self.current, push=False)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._poll_ui)

    # ---------- helpers ----------

    def _ui_call(self, fn):
        """صف‌کردن فراخوانی UI از تردهای پس‌زمینه — اجرا فقط روی ترد اصلی (جلوگیری از RuntimeError)"""
        try:
            self.ui_queue.put(fn)
        except Exception:
            pass

    def _poll_ui(self):
        try:
            while True:
                try:
                    fn = self.ui_queue.get_nowait()
                except queue.Empty:
                    break
                try:
                    fn()
                except Exception:
                    pass
        except Exception:
            pass
        if not self._closing:
            try:
                self._job_poll = self.after(100, self._poll_ui)
            except Exception:
                pass

    def _on_close(self):
        self._closing = True
        try:
            if self._job_poll is not None:
                self.after_cancel(self._job_poll)
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass

    def _clear_tree(self):
        """پاک‌سازی امن جدول — روی جدول خالی خطا نمی‌دهد"""
        try:
            kids = self.tree.get_children()
            if kids:
                self.tree.delete(*kids)
        except Exception:
            pass

    # ---------- UI building ----------

    def _build_titlebar(self):
        bar = tk.Frame(self, bg=PANEL, height=44)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        for c in (RED, YELLOW, GREEN):
            tk.Label(bar, text="", width=2, bg=c).pack(side="left", padx=4, pady=12)
        tk.Label(bar, text="🗂 FILE MANAGER", font=("Consolas", 13, "bold"), bg=PANEL, fg=ACCENT).pack(side="left", padx=12)
        tk.Label(bar, text="v4.0 · full · scan · trash · tabs", font=("Consolas", 9), bg=PANEL, fg=MUTED).pack(side="left", padx=8)
        self.title_path = tk.Label(bar, text="", font=("Tahoma", 9), bg=PANEL, fg=CYAN)
        self.title_path.pack(side="right", padx=14)

    def _build_toolbar(self):
        bar = tk.Frame(self, bg=PANEL, height=52)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        def btn(text, cmd, fg=TEXT, bg_c=PANEL_2):
            return tk.Button(bar, text=text, relief="flat", bd=0, cursor="hand2", bg=bg_c, fg=fg, activebackground=ACCENT, activeforeground="#1a1005", font=("Tahoma", 10), padx=10, pady=6, command=cmd)
        btn("‹ برگشت", self.go_back).pack(side="left", padx=(10, 2), pady=8)
        btn("⬆ بالا", self.go_up).pack(side="left", padx=2, pady=8)
        btn("🏠 خانه", lambda: self.load_dir(os.path.expanduser("~"))).pack(side="left", padx=2, pady=8)
        btn("🔄 تازه‌سازی", self.refresh).pack(side="left", padx=2, pady=8)
        btn("➕ پوشه", self.new_folder, fg="#1a1005", bg_c=ACCENT).pack(side="left", padx=(10, 2), pady=8)
        btn("✏️ تغییرنام", self.rename_item).pack(side="left", padx=2, pady=8)
        btn("📋 کپی", self.copy_item).pack(side="left", padx=2, pady=8)
        btn("✂️ برش", self.cut_item).pack(side="left", padx=2, pady=8)
        btn("📥 چسباندن", self.paste_item).pack(side="left", padx=2, pady=8)
        btn("🗑 حذف", self.delete_item, fg=RED).pack(side="left", padx=2, pady=8)
        self.search_var = tk.StringVar()
        se = tk.Entry(bar, textvariable=self.search_var, bg=PANEL_2, fg=TEXT, insertbackground=ACCENT, relief="flat", font=("Tahoma", 10), highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT, justify="right")
        se.pack(side="right", padx=10, pady=8, ipadx=8, ipady=4)
        se.insert(0, SEARCH_PLACEHOLDER)
        # فقط پلاس‌هولدر پاک شود، نه متن واقعی کاربر
        se.bind("<FocusIn>", lambda e: se.delete(0, "end") if se.get() == SEARCH_PLACEHOLDER else None)
        se.bind("<KeyRelease>", lambda e: self.apply_filter_sort())

    def _build_toolbar2(self):
        bar2 = tk.Frame(self, bg=BG, height=36)
        bar2.pack(fill="x", padx=8, pady=(4, 0))
        def b2(text, cmd, fg=TEXT):
            return tk.Button(bar2, text=text, relief="flat", bd=0, cursor="hand2", bg=PANEL, fg=fg, activebackground=ACCENT, activeforeground="#1a1005", font=("Tahoma", 9), padx=8, pady=4, command=cmd)
        b2("📄 فایل جدید", self.new_file).pack(side="left", padx=2)
        b2("🗜 زیپ", self.zip_selected).pack(side="left", padx=2)
        b2("📦 آنزیپ", self.unzip_selected).pack(side="left", padx=2)
        b2("📋 کپی مسیر", self.copy_path).pack(side="left", padx=2)
        b2("🔍 مشخصات", self.show_properties).pack(side="left", padx=2)
        b2("💾 خروجی اسکن", self.export_scan).pack(side="left", padx=2)
        b2("⏹ توقف", self.cancel_all, fg=YELLOW).pack(side="left", padx=2)
        tk.Checkbutton(bar2, text="نمایش مخفی", variable=self.show_hidden, command=self.refresh, bg=BG, fg=MUTED, selectcolor=PANEL, activebackground=BG, activeforeground=ACCENT, font=("Tahoma", 9)).pack(side="right", padx=8)
        tk.Label(bar2, text="چندتایی: Shift/Ctrl + کلیک | Ctrl+C/X/V | F2/F5", font=("Tahoma", 8), bg=BG, fg=MUTED).pack(side="right", padx=6)

    def _build_body(self):
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True)
        side = tk.Frame(body, bg=PANEL, width=200)
        side.pack(side="right", fill="y", padx=(8, 0), pady=8)
        side.pack_propagate(False)
        tk.Label(side, text="⚡ مسیرهای سریع", font=("Tahoma", 10, "bold"), bg=PANEL, fg=ACCENT).pack(pady=(12, 6))
        home = os.path.expanduser("~")
        if os.name == "nt":
            places = [("🏠 خانه", home), ("🖥 دسکتاپ", os.path.join(home, "Desktop")), ("📥 دانلودها", os.path.join(home, "Downloads")), ("📃 اسناد", os.path.join(home, "Documents")), ("🖼 تصاویر", os.path.join(home, "Pictures")), ("💽 درایو C", "C:\\"), ("💽 درایو D", "D:\\")]
        else:
            places = [("🏠 خانه", home), ("🖥 دسکتاپ", os.path.join(home, "Desktop")), ("📥 دانلودها", os.path.join(home, "Downloads")), ("📃 اسناد", os.path.join(home, "Documents")), ("🖼 تصاویر", os.path.join(home, "Pictures")), ("📁 ریشه /", "/"), ("📁 موقت", "/tmp")]
        # فقط میان‌برهایی که واقعاً وجود دارند نمایش داده شوند
        for label, path in places:
            if not os.path.isdir(path):
                continue
            tk.Button(side, text=label, anchor="e", relief="flat", bd=0, cursor="hand2", bg=PANEL_2, fg=TEXT, activebackground=ACCENT, activeforeground="#1a1005", font=("Tahoma", 10), padx=10, pady=7, command=lambda p=path: self.load_dir(p)).pack(fill="x", padx=10, pady=3)
        info = tk.Frame(side, bg=PANEL_2)
        info.pack(fill="x", padx=10, pady=(14, 6))
        tk.Label(info, text="📊 این پوشه", font=("Tahoma", 9, "bold"), bg=PANEL_2, fg=CYAN).pack(pady=(8, 2))
        self.info_label = tk.Label(info, text="", font=("Tahoma", 9), bg=PANEL_2, fg=TEXT, justify="right")
        self.info_label.pack(anchor="e", padx=10, pady=(0, 8))
        drv = tk.Frame(side, bg=PANEL_2)
        drv.pack(fill="both", expand=True, padx=10, pady=(6, 8))
        tk.Label(drv, text="💽 درایوها", font=("Tahoma", 9, "bold"), bg=PANEL_2, fg=ACCENT).pack(pady=(8, 2))
        self.drives_listbox = tk.Listbox(drv, bg=BG, fg=TEXT, selectbackground=ACCENT, selectforeground="#1a1005", relief="flat", font=("Consolas", 9), height=5, highlightthickness=1, highlightbackground=BORDER)
        self.drives_listbox.pack(fill="x", padx=8)
        self.drives_listbox.bind("<Double-Button-1>", lambda e: self.open_drive_from_list())
        row = tk.Frame(drv, bg=PANEL_2)
        row.pack(fill="x", padx=8, pady=6)
        tk.Button(row, text="➕", relief="flat", bd=0, cursor="hand2", bg=BG, fg=GREEN, font=("Tahoma", 10, "bold"), command=self.add_drive).pack(side="left", fill="x", expand=True, padx=2)
        tk.Button(row, text="➖", relief="flat", bd=0, cursor="hand2", bg=BG, fg=RED, font=("Tahoma", 10, "bold"), command=self.remove_drive).pack(side="left", fill="x", expand=True, padx=2)
        tk.Button(row, text="🔄", relief="flat", bd=0, cursor="hand2", bg=BG, fg=CYAN, font=("Tahoma", 10), command=self._refresh_drive_box).pack(side="left", fill="x", expand=True, padx=2)
        tk.Button(drv, text="🌐 اسکن کل دستگاه", relief="flat", bd=0, cursor="hand2", bg=ACCENT, fg="#1a1005", activebackground=ACCENT_D, font=("Tahoma", 10, "bold"), pady=6, command=self.open_scan_dialog).pack(fill="x", padx=8, pady=(2, 4))
        tk.Button(drv, text="↩ برگشت به مرور", relief="flat", bd=0, cursor="hand2", bg=BG, fg=TEXT, activebackground=PANEL, activeforeground=ACCENT, font=("Tahoma", 9), pady=4, command=self.exit_scan).pack(fill="x", padx=8, pady=(0, 8))
        main = tk.Frame(body, bg=BG)
        main.pack(side="right", fill="both", expand=True)
        self.tab_bar = tk.Frame(main, bg=BG, height=30)
        self.tab_bar.pack(fill="x", pady=(2, 0))
        path_bar = tk.Frame(main, bg=PANEL, height=40)
        path_bar.pack(fill="x")
        path_bar.pack_propagate(False)
        tk.Label(path_bar, text="مسیر:", font=("Tahoma", 9, "bold"), bg=PANEL, fg=MUTED).pack(side="right", padx=(10, 4))
        self.path_var = tk.StringVar()
        pe = tk.Entry(path_bar, textvariable=self.path_var, bg=PANEL_2, fg=TEXT, insertbackground=ACCENT, relief="flat", font=("Consolas", 10), highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT)
        pe.pack(side="right", fill="x", expand=True, padx=8, pady=6)
        pe.bind("<Return>", lambda e: self.load_dir(self.path_var.get()))
        tk.Button(path_bar, text="برو ▸", relief="flat", bd=0, cursor="hand2", bg=ACCENT, fg="#1a1005", font=("Tahoma", 9, "bold"), padx=10, activebackground=ACCENT_D, command=lambda: self.load_dir(self.path_var.get())).pack(side="right", padx=(0, 8))
        self._rebuild_tabs()
        table_frame = tk.Frame(main, bg=ACCENT)
        table_frame.pack(fill="both", expand=True, pady=(8, 0))
        inner = tk.Frame(table_frame, bg=BG)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        try:
            style = ttk.Style()
            try:
                style.theme_use("clam")
            except Exception:
                pass
            style.configure("Dark.Treeview", background=BG, foreground=TEXT, fieldbackground=BG, rowheight=30, borderwidth=0, font=("Tahoma", 10))
            style.map("Dark.Treeview", background=[("selected", ACCENT)], foreground=[("selected", "#1a1005")])
            style.configure("Dark.Treeview.Heading", background=PANEL, foreground=ACCENT, borderwidth=0, font=("Tahoma", 9, "bold"))
            style.map("Dark.Treeview.Heading", background=[("active", PANEL_2)])
            style.configure("Vertical.TScrollbar", background=PANEL, troughcolor=BG, bordercolor=BG, arrowcolor=ACCENT, relief="flat")
        except Exception:
            pass
        cols = ("name", "size", "modified")
        self.tree = ttk.Treeview(inner, columns=cols, show="tree headings", style="Dark.Treeview", selectmode="extended")
        self.tree.heading("#0", text="نوع", anchor="center", command=lambda: self.sort_by("is_dir"))
        self.tree.heading("name", text="نام ▲", anchor="e", command=lambda: self.sort_by("name"))
        self.tree.heading("size", text="حجم", anchor="center", command=lambda: self.sort_by("size"))
        self.tree.heading("modified", text="تاریخ تغییر", anchor="center", command=lambda: self.sort_by("mtime"))
        self.tree.column("#0", width=50, stretch=False, anchor="center")
        self.tree.column("name", width=380, anchor="e")
        self.tree.column("size", width=100, anchor="center", stretch=False)
        self.tree.column("modified", width=150, anchor="center", stretch=False)
        vsb = ttk.Scrollbar(inner, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="left", fill="y")
        self.tree.pack(side="right", fill="both", expand=True)
        self.tree.bind("<Double-Button-1>", self.open_item)
        self.tree.bind("<Return>", self.open_item)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.update_preview())
        self.tree.bind("<Button-3>", self.show_menu)
        self.menu = tk.Menu(self, bg=PANEL, fg=TEXT, bd=0, activebackground=ACCENT, activeforeground="#1a1005", font=("Tahoma", 10), tearoff=0)
        self.menu.add_command(label="📂 باز کن", command=self.open_item)
        self.menu.add_command(label="📁 بازکردن محل فایل", command=self.open_containing)
        self.menu.add_separator()
        self.menu.add_command(label="📄 فایل جدید", command=self.new_file)
        self.menu.add_command(label="✏️ تغییر نام", command=self.rename_item)
        self.menu.add_command(label="📋 کپی", command=self.copy_item)
        self.menu.add_command(label="✂️ برش", command=self.cut_item)
        self.menu.add_command(label="📥 چسباندن", command=self.paste_item)
        self.menu.add_command(label="📋 کپی مسیر", command=self.copy_path)
        self.menu.add_separator()
        self.menu.add_command(label="🗜 زیپ", command=self.zip_selected)
        self.menu.add_command(label="📦 آنزیپ", command=self.unzip_selected)
        self.menu.add_command(label="🔍 مشخصات", command=self.show_properties)
        self.menu.add_separator()
        self.menu.add_command(label="🗑 حذف", command=self.delete_item)
        prev = tk.Frame(main, bg=PANEL, height=86)
        prev.pack(fill="x", pady=(6, 0))
        prev.pack_propagate(False)
        tk.Label(prev, text="👁 پیش‌نمایش:", font=("Tahoma", 9, "bold"), bg=PANEL, fg=CYAN).pack(side="right", padx=10, pady=6)
        self.preview_label = tk.Label(prev, text="یک فایل را انتخاب کن...", font=("Tahoma", 9), bg=PANEL, fg=MUTED, anchor="e", justify="right", wraplength=700)
        self.preview_label.pack(side="right", fill="x", expand=True, padx=8)

    def _build_statusbar(self):
        bar = tk.Frame(self, bg=PANEL, height=26)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        self.status = tk.Label(bar, text="آماده", font=("Tahoma", 9), bg=PANEL, fg=MUTED, anchor="e")
        self.status.pack(side="right", padx=12)
        self.prog = ttk.Progressbar(bar, length=220, mode="determinate", maximum=100)
        self.prog.pack(side="left", padx=10, pady=4)
        tk.Label(bar, text="FULL · TABS · TRASH · ZIP", font=("Consolas", 8), bg=PANEL, fg=MUTED).pack(side="left", padx=6)

    def set_status(self, text, color=MUTED):
        try:
            self.status.config(text=text, fg=color)
        except Exception:
            pass

    def set_prog(self, v):
        try:
            self.prog["value"] = max(0, min(100, v))
        except Exception:
            pass

    def _bind_shortcuts(self):
        try:
            self.tree.bind("<Control-c>", lambda e: (self.copy_item(), "break")[1])
            self.tree.bind("<Control-x>", lambda e: (self.cut_item(), "break")[1])
            self.tree.bind("<Control-v>", lambda e: (self.paste_item(), "break")[1])
            self.tree.bind("<F2>", lambda e: self.rename_item())
            self.tree.bind("<F5>", lambda e: self.refresh())
            self.tree.bind("<Delete>", lambda e: self.delete_item())
        except Exception:
            pass

    def _rebuild_tabs(self):
        try:
            for w in self.tab_bar.winfo_children():
                w.destroy()
            for i, p in enumerate(self.tabs):
                nm = os.path.basename(p.rstrip(os.sep)) or p
                if len(nm) > 18:
                    nm = nm[:17] + "…"
                bgc = ACCENT if i == self.tab_index else PANEL
                fgc = "#1a1005" if i == self.tab_index else TEXT
                tk.Button(self.tab_bar, text=f"{'● ' if i==self.tab_index else ''}{nm}", bg=bgc, fg=fgc, relief="flat", bd=0, cursor="hand2", font=("Tahoma", 9), padx=10, pady=3, command=lambda k=i: self.switch_tab(k)).pack(side="left", padx=2)
            tk.Button(self.tab_bar, text="+ تب", bg=PANEL_2, fg=GREEN, relief="flat", bd=0, cursor="hand2", font=("Tahoma", 9, "bold"), padx=8, command=self.new_tab).pack(side="left", padx=4)
            if len(self.tabs) > 1:
                tk.Button(self.tab_bar, text="✕", bg=PANEL_2, fg=RED, relief="flat", bd=0, cursor="hand2", font=("Tahoma", 9), command=self.close_tab).pack(side="left")
        except Exception:
            pass

    def new_tab(self):
        try:
            self.tabs.append(self.current)
            self.tab_index = len(self.tabs) - 1
            self._rebuild_tabs()
        except Exception:
            pass

    def switch_tab(self, i):
        try:
            if 0 <= i < len(self.tabs):
                self.tab_index = i
                self.load_dir(self.tabs[i], push=False)
                self._rebuild_tabs()
        except Exception:
            pass

    def close_tab(self):
        try:
            if len(self.tabs) > 1:
                self.tabs.pop(self.tab_index)
                self.tab_index = max(0, min(self.tab_index, len(self.tabs)-1))
                self.load_dir(self.tabs[self.tab_index], push=False)
                self._rebuild_tabs()
        except Exception:
            pass

    # ---------- drives ----------

    def _get_system_drives(self):
        drives = []
        try:
            if os.name == "nt":
                for c in string.ascii_uppercase:
                    d = f"{c}:\\"
                    try:
                        if os.path.exists(d):
                            drives.append(d)
                    except Exception:
                        continue
            else:
                drives.append("/")
                home = os.path.expanduser("~")
                if os.path.isdir(home):
                    drives.append(home)
                for base in [f"/media/{os.environ.get('USER','')}", "/media", "/mnt"]:
                    try:
                        if os.path.isdir(base):
                            for x in os.listdir(base):
                                p = os.path.join(base, x)
                                if os.path.isdir(p) and p not in drives:
                                    drives.append(p)
                    except Exception:
                        continue
        except Exception:
            pass
        if not drives:
            drives = [os.path.expanduser("~")]
        return drives

    def _get_drive_list(self):
        try:
            raw = list(self.drives_listbox.get(0, "end"))
            clean = []
            for r in raw:
                clean.append(r.split("  |")[0].strip())
            return [d for d in clean if d]
        except Exception:
            return self._get_system_drives()

    def _refresh_drive_box(self):
        try:
            try:
                cur_raw = list(self.drives_listbox.get(0, "end"))
                cur = [r.split("  |")[0].strip() for r in cur_raw] if cur_raw else None
            except Exception:
                cur = None
            self.drives_listbox.delete(0, "end")
            for d in (cur if cur else self._get_system_drives()):
                fr = drive_free_str(d)
                self.drives_listbox.insert("end", f"{d}  | {fr}" if fr else d)
        except Exception:
            pass

    def add_drive(self):
        try:
            p = filedialog.askdirectory(title="انتخاب درایو / پوشه", parent=self)
        except Exception:
            p = None
        if not p:
            return
        p = os.path.abspath(p)
        cur = self._get_drive_list()
        if p in cur:
            self.set_status("این مسیر قبلا هست", YELLOW)
            return
        try:
            self.drives_listbox.insert("end", f"{p}  | {drive_free_str(p)}")
            self.set_status(f"اضافه شد: {p}", GREEN)
        except Exception as ex:
            messagebox.showerror("خطا", str(ex), parent=self)

    def remove_drive(self):
        try:
            sel = self.drives_listbox.curselection()
        except Exception:
            sel = ()
        if not sel:
            self.set_status("یک درایو را انتخاب کن", YELLOW)
            return
        try:
            val = self.drives_listbox.get(sel[0])
            self.drives_listbox.delete(sel[0])
            self.set_status(f"کم شد: {val}", GREEN)
        except Exception:
            pass

    def open_drive_from_list(self):
        try:
            sel = self.drives_listbox.curselection()
            if not sel:
                return
            p = self.drives_listbox.get(sel[0]).split("  |")[0].strip()
            if not p:
                return
            self.exit_scan(silent=True)
            self.load_dir(p)
        except Exception:
            pass

    # ---------- scan ----------

    def open_scan_dialog(self):
        dlg = tk.Toplevel(self)
        dlg.title("اسکن کل دستگاه")
        dlg.configure(bg=PANEL)
        dlg.transient(self)
        dlg.grab_set()
        dlg.geometry("440x400")
        dlg.resizable(False, False)
        tk.Label(dlg, text="🌐 اسکن کل دستگاه", font=("Tahoma", 12, "bold"), bg=PANEL, fg=ACCENT).pack(pady=(14, 4))
        tk.Label(dlg, text="همه فایل‌های درایوهای لیست آورده می‌شود", font=("Tahoma", 9), bg=PANEL, fg=MUTED).pack(pady=(0, 10))
        frm = tk.Frame(dlg, bg=PANEL)
        frm.pack(fill="x", padx=24)
        tk.Label(frm, text="فیلتر اسم (مثلا *.mp4,*.pdf یا خالی=همه):", font=("Tahoma", 9), bg=PANEL, fg=TEXT, anchor="e").pack(fill="x")
        pat_var = tk.StringVar(value="")
        tk.Entry(frm, textvariable=pat_var, bg=PANEL_2, fg=TEXT, relief="flat", font=("Tahoma", 10), highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT).pack(fill="x", ipady=5, pady=(4, 8))
        tk.Label(frm, text="متن داخل فایل (خالی=بدون جست‌وجوی متنی):", font=("Tahoma", 9), bg=PANEL, fg=TEXT, anchor="e").pack(fill="x")
        txt_var = tk.StringVar(value="")
        tk.Entry(frm, textvariable=txt_var, bg=PANEL_2, fg=TEXT, relief="flat", font=("Tahoma", 10), highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT).pack(fill="x", ipady=5, pady=(4, 8))
        tk.Label(frm, text="حداکثر تعداد:", font=("Tahoma", 9), bg=PANEL, fg=TEXT, anchor="e").pack(fill="x")
        max_var = tk.StringVar(value="5000")
        tk.Entry(frm, textvariable=max_var, bg=PANEL_2, fg=TEXT, relief="flat", font=("Tahoma", 10), justify="center", highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT).pack(fill="x", ipady=5, pady=(4, 12))
        def go():
            try:
                mx = int(max_var.get().strip() or "5000")
            except Exception:
                mx = 5000
            mx = max(100, min(mx, 50000))
            pats = [x.strip().lower() for x in pat_var.get().split(",") if x.strip()]
            drives = self._get_drive_list()
            content_q = txt_var.get().strip()
            dlg.destroy()
            self._start_scan_thread(drives, pats, mx, content_q)
        tk.Button(dlg, text="شروع اسکن", relief="flat", bd=0, cursor="hand2", bg=ACCENT, fg="#1a1005", font=("Tahoma", 11, "bold"), padx=20, pady=6, command=go).pack(pady=6)
        tk.Label(dlg, text="توقف با دکمه ⏹ بالا | جست‌وجوی متنی فقط فایل‌های متنی کوچک", font=("Tahoma", 8), bg=PANEL, fg=MUTED).pack(pady=(4, 10))

    def _start_scan_thread(self, drives, patterns, max_n, content_q=""):
        self.scan_stop = False
        self.set_prog(0)
        self.set_status(f"در حال اسکن {len(drives)} درایو...", YELLOW)
        try:
            self.title_path.config(text="🌐 در حال اسکن کل دستگاه... (صبر کن)")
        except Exception:
            pass
        TEXT_EXTS = {".txt", ".py", ".log", ".md", ".csv", ".json", ".html", ".css", ".js", ".xml", ".ini", ".bat", ".sh"}
        def worker():
            results = []
            scanned = [0]
            try:
                for d in drives:
                    if self.scan_stop or len(results) >= max_n:
                        break
                    if not os.path.isdir(d):
                        continue
                    for root, dirs, files in os.walk(d, topdown=True, onerror=None, followlinks=False):
                        if self.scan_stop or len(results) >= max_n:
                            break
                        try:
                            dirs[:] = [x for x in dirs if not x.startswith("$") and x not in ("System Volume Information", "$RECYCLE.BIN")]
                        except Exception:
                            pass
                        for fn in files:
                            if self.scan_stop or len(results) >= max_n:
                                break
                            low = fn.lower()
                            if patterns:
                                ok = False
                                for p in patterns:
                                    try:
                                        if fnmatch.fnmatch(low, p):
                                            ok = True
                                            break
                                    except Exception:
                                        continue
                                if not ok:
                                    continue
                            full = os.path.join(root, fn)
                            try:
                                sz = os.path.getsize(full)
                            except Exception:
                                sz = 0
                            if content_q:
                                ext = os.path.splitext(fn)[1].lower()
                                if ext not in TEXT_EXTS or sz > 2*1024*1024:
                                    continue
                                try:
                                    with open(full, "r", encoding="utf-8", errors="ignore") as f:
                                        data = f.read(500000)
                                    if content_q.lower() not in data.lower():
                                        continue
                                except Exception:
                                    continue
                            try:
                                mt = os.path.getmtime(full)
                            except Exception:
                                mt = 0
                            results.append({"name": fn, "full": full, "is_dir": False, "size": sz, "mtime": mt})
                            scanned[0] += 1
                            if scanned[0] % 800 == 0:
                                c = scanned[0]
                                n = len(results)
                                self._ui_call(lambda c=c, n=n: (self.set_status(f"اسکن... {c} بررسی ({n} نتیجه)", YELLOW), self.set_prog(min(95, n*100/max(1, max_n)))))
            except Exception as ex:
                self._ui_call(lambda ex=ex: messagebox.showerror("خطا در اسکن", str(ex), parent=self))
                return
            self._ui_call(lambda: (self._display_scan(results, drives), self.set_prog(100)))
        threading.Thread(target=worker, daemon=True).start()

    def _display_scan(self, results, drives):
        self.in_scan = True
        self.scan_all = list(results)
        self.scan_map = {}
        self._clear_tree()
        for e in results:
            size_s = fmt_size(e["size"])
            try:
                mtime_s = datetime.datetime.fromtimestamp(e["mtime"]).strftime("%Y-%m-%d %H:%M") if e["mtime"] else "؟"
            except Exception:
                mtime_s = "؟"
            try:
                iid = self.tree.insert("", "end", text=icon_for(e["name"], False), values=(e["full"], size_s, mtime_s))
                self.scan_map[iid] = e["full"]
            except Exception:
                continue
        try:
            self.info_label.config(text=f"درایوها: {len(drives)}\nفایل‌ها: {len(results)}\nحالت: اسکن کل")
        except Exception:
            pass
        try:
            self.title_path.config(text=f"🌐 نتیجه اسکن: {len(results)} فایل")
        except Exception:
            pass
        self.set_status(f"اسکن تمام شد: {len(results)} فایل", GREEN)

    def export_scan(self):
        if not getattr(self, "scan_all", None):
            self.set_status("نتیجه اسکنی برای خروجی نیست", YELLOW)
            return
        p = filedialog.asksaveasfilename(title="ذخیره لیست اسکن", defaultextension=".csv", filetypes=[("CSV", "*.csv"), ("TXT", "*.txt")], parent=self)
        if not p:
            return
        try:
            if p.lower().endswith(".csv"):
                with open(p, "w", newline="", encoding="utf-8-sig") as f:
                    w = csv.writer(f)
                    w.writerow(["path", "size", "mtime"])
                    for e in self.scan_all:
                        w.writerow([e["full"], e["size"], e["mtime"]])
            else:
                with open(p, "w", encoding="utf-8") as f:
                    for e in self.scan_all:
                        f.write(e["full"] + "\n")
            self.set_status(f"خروجی ذخیره شد: {p}", GREEN)
        except Exception as ex:
            messagebox.showerror("خطا", str(ex), parent=self)

    def exit_scan(self, silent=False):
        if not self.in_scan:
            return
        self.in_scan = False
        self.scan_map = {}
        self.scan_all = []
        self.scan_stop = True
        self.set_prog(0)
        if not silent:
            self.refresh()

    def cancel_scan(self):
        self.scan_stop = True
        self.set_status("اسکن لغو شد", YELLOW)

    def cancel_all(self):
        self.scan_stop = True
        self.copy_stop = True
        self.set_prog(0)
        self.set_status("توقف شد", YELLOW)

    # ---------- listing / sorting ----------

    def sort_by(self, key):
        if self.sort_key == key:
            self.sort_rev = not self.sort_rev
        else:
            self.sort_key = key
            self.sort_rev = False
        arrow = " ▼" if self.sort_rev else " ▲"
        try:
            self.tree.heading("name", text="نام" + (arrow if key == "name" else ""))
            self.tree.heading("size", text="حجم" + (arrow if key == "size" else ""))
            self.tree.heading("modified", text="تاریخ تغییر" + (arrow if key == "mtime" else ""))
        except Exception:
            pass
        self.apply_filter_sort()

    def _sorted_entries(self, items):
        try:
            if self.sort_key == "name":
                items.sort(key=lambda e: (not e["is_dir"], e["name"].lower()), reverse=self.sort_rev)
            elif self.sort_key == "size":
                items.sort(key=lambda e: (e["is_dir"], e["size"]), reverse=self.sort_rev)
            elif self.sort_key == "mtime":
                items.sort(key=lambda e: e["mtime"], reverse=self.sort_rev)
            elif self.sort_key == "is_dir":
                items.sort(key=lambda e: e["is_dir"], reverse=self.sort_rev)
        except Exception:
            pass
        return items

    def load_dir(self, path, push=True):
        self.in_scan = False
        self.scan_map = {}
        try:
            path = os.path.abspath(os.path.expanduser(path))
        except Exception:
            self.set_status("مسیر نامعتبر است", RED)
            return
        if not os.path.isdir(path):
            self.set_status("مسیر نامعتبر است", RED)
            return
        if push and path != self.current:
            self.back_stack.append(self.current)
            if len(self.back_stack) > 30:
                self.back_stack.pop(0)
        self.current = path
        try:
            self.tabs[self.tab_index] = path
            self._rebuild_tabs()
        except Exception:
            pass
        try:
            self.path_var.set(path)
        except Exception:
            pass
        try:
            self.title_path.config(text="📍 " + path)
        except Exception:
            pass
        try:
            names = os.listdir(path)
        except PermissionError:
            self.set_status("دسترسی به این پوشه مجاز نیست", RED)
            return
        except Exception as ex:
            self.set_status(f"خطا: {ex}", RED)
            return
        show_h = bool(self.show_hidden.get())
        self.all_entries = []
        for name in names:
            full = os.path.join(path, name)
            try:
                is_dir = os.path.isdir(full)
            except Exception:
                continue
            if not show_h:
                try:
                    if is_hidden_path(full, name):
                        continue
                except Exception:
                    pass
            try:
                sz = os.path.getsize(full) if not is_dir else 0
            except OSError:
                sz = 0
            try:
                mt = os.path.getmtime(full)
            except OSError:
                mt = 0
            self.all_entries.append({"name": name, "full": full, "is_dir": is_dir, "size": sz, "mtime": mt})
        self.apply_filter_sort()

    def apply_filter_sort(self):
        if getattr(self, "in_scan", False):
            self._clear_tree()
            q = ""
            try:
                q = self.search_var.get().strip().lower()
                if q == SEARCH_PLACEHOLDER.lower():
                    q = ""
            except Exception:
                q = ""
            items = [e for e in self.scan_all if q in e["full"].lower() or q in e["name"].lower()] if q else list(self.scan_all)
            # مرتب‌سازی در حالت اسکن هم اکنون کار می‌کند
            items = self._sorted_entries(items)
            self.scan_map = {}
            for e in items:
                size_s = fmt_size(e["size"])
                try:
                    mtime_s = datetime.datetime.fromtimestamp(e["mtime"]).strftime("%Y-%m-%d %H:%M") if e["mtime"] else "؟"
                except Exception:
                    mtime_s = "؟"
                try:
                    iid = self.tree.insert("", "end", text=icon_for(e["name"], False), values=(e["full"], size_s, mtime_s))
                    self.scan_map[iid] = e["full"]
                except Exception:
                    continue
            self.set_status(f"{len(items)} فایل (حالت اسکن)", GREEN)
            return
        self._clear_tree()
        q = ""
        try:
            q = self.search_var.get().strip().lower()
            if q == SEARCH_PLACEHOLDER.lower():
                q = ""
        except Exception:
            q = ""
        items = [e for e in self.all_entries if q in e["name"].lower()] if q else list(self.all_entries)
        items = self._sorted_entries(items)
        dirs = files = 0
        total_sz = 0
        for e in items:
            if e["is_dir"]:
                dirs += 1
                size_s = "—"
            else:
                files += 1
                total_sz += e["size"]
                size_s = fmt_size(e["size"])
            try:
                mtime_s = datetime.datetime.fromtimestamp(e["mtime"]).strftime("%Y-%m-%d %H:%M") if e["mtime"] else "؟"
            except Exception:
                mtime_s = "؟"
            try:
                self.tree.insert("", "end", text=icon_for(e["name"], e["is_dir"]), values=(e["name"], size_s, mtime_s))
            except Exception:
                continue
        try:
            self.info_label.config(text=f"پوشه‌ها: {dirs}\nفایل‌ها: {files}\nحجم فایل‌ها: {fmt_size(total_sz)}")
        except Exception:
            pass
        self.set_status(f"{len(items)} آیتم در {self.current}", GREEN)

    def refresh(self):
        if getattr(self, "in_scan", False):
            self.exit_scan(silent=True)
        self.load_dir(self.current, push=False)
        self._refresh_drive_box()

    def go_back(self):
        if self.back_stack:
            self.load_dir(self.back_stack.pop(), push=False)
        else:
            self.set_status("تاریخی برای برگشت نیست", YELLOW)

    def go_up(self):
        try:
            parent = os.path.dirname(os.path.abspath(self.current))
        except Exception:
            return
        if not parent or parent == self.current:
            self.set_status("در ریشه هستید", YELLOW)
            return
        self.load_dir(parent)

    # ---------- selection / open ----------

    def selected_paths(self):
        try:
            sel = self.tree.selection()
        except Exception:
            return []
        if not sel:
            return []
        if getattr(self, "in_scan", False):
            out = []
            for iid in sel:
                try:
                    p = self.scan_map.get(iid)
                    if p:
                        out.append(p)
                except Exception:
                    continue
            return out
        out = []
        for iid in sel:
            try:
                name = self.tree.item(iid, "values")[0]
                out.append(os.path.join(self.current, name))
            except Exception:
                continue
        return out

    def selected_path(self):
        ps = self.selected_paths()
        if not ps:
            self.set_status("ابتدا یک آیتم را انتخاب کنید", YELLOW)
            return None
        return ps[0]

    def open_item(self, event=None):
        paths = self.selected_paths()
        if not paths:
            return "break"
        if len(paths) == 1 and os.path.isdir(paths[0]):
            self.exit_scan(silent=True)
            self.load_dir(paths[0])
            return "break"
        missing = 0
        for path in paths:
            if os.path.isdir(path):
                continue
            if not os.path.exists(path):
                missing += 1
                continue
            try:
                if os.name == "nt":
                    os.startfile(path)
                else:
                    opener = "open" if sys.platform == "darwin" else "xdg-open"
                    subprocess.Popen([opener, path])
            except Exception as ex:
                messagebox.showerror("خطا", str(ex), parent=self)
                break
        if missing:
            self.set_status(f"{missing} فایل دیگر وجود ندارد (نتیجه اسکن قدیمی)", YELLOW)
        return "break"

    def open_containing(self):
        p = self.selected_path()
        if not p:
            return
        parent = os.path.dirname(os.path.abspath(p)) if not os.path.isdir(p) else os.path.abspath(p)
        try:
            self.exit_scan(silent=True)
            self.load_dir(parent)
        except Exception as ex:
            messagebox.showerror("خطا", str(ex), parent=self)

    def update_preview(self):
        try:
            ps = self.selected_paths()
            if not ps:
                self.preview_label.config(text="یک فایل را انتخاب کن...")
                return
            p = ps[0]
            if len(ps) > 1:
                self.preview_label.config(text=f"{len(ps)} آیتم انتخاب شده — {os.path.basename(p)} و ...")
                return
            if not os.path.exists(p):
                self.preview_label.config(text="⚠ این فایل دیگر وجود ندارد")
                return
            if os.path.isdir(p):
                try:
                    n = len(os.listdir(p))
                    self.preview_label.config(text=f"📁 پوشه: {os.path.basename(p)} — {n} آیتم داخلش")
                except Exception:
                    self.preview_label.config(text="📁 پوشه")
                return
            ext = os.path.splitext(p)[1].lower()
            try:
                sz = os.path.getsize(p)
            except Exception:
                sz = 0
            if ext in (".txt", ".py", ".log", ".md", ".csv", ".json", ".html", ".css", ".js", ".xml", ".ini", ".bat", ".sh"):
                try:
                    with open(p, "r", encoding="utf-8", errors="ignore") as f:
                        t = f.read(600).strip().replace("\n", " ⏎ ")[:380]
                    self.preview_label.config(text=f"📄 {os.path.basename(p)} ({fmt_size(sz)}): {t if t else 'فایل خالی'}")
                except Exception:
                    self.preview_label.config(text=f"📄 {os.path.basename(p)} ({fmt_size(sz)})")
            elif ext in (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"):
                self.preview_label.config(text=f"🖼 عکس: {os.path.basename(p)} — {fmt_size(sz)} — دابل‌کلیک برای باز شدن")
            elif ext in (".mp3", ".mp4", ".mkv", ".wav"):
                self.preview_label.config(text=f"🎬 مدیا: {os.path.basename(p)} — {fmt_size(sz)}")
            elif ext == ".zip":
                try:
                    with zipfile.ZipFile(p, "r") as z:
                        self.preview_label.config(text=f"🗜 زیپ: {os.path.basename(p)} — {len(z.namelist())} فایل داخلش — {fmt_size(sz)}")
                except Exception:
                    self.preview_label.config(text=f"🗜 {os.path.basename(p)} ({fmt_size(sz)})")
            else:
                self.preview_label.config(text=f"📄 {os.path.basename(p)} — {fmt_size(sz)}")
        except Exception:
            pass

    def copy_path(self):
        p = self.selected_path()
        if not p:
            return
        try:
            self.clipboard_clear()
            self.clipboard_append(p)
            self.set_status("مسیر کپی شد", GREEN)
        except Exception as ex:
            messagebox.showerror("خطا", str(ex), parent=self)

    def show_properties(self):
        p = self.selected_path()
        if not p:
            return
        if not os.path.exists(p):
            self.set_status("این آیتم دیگر وجود ندارد", YELLOW)
            return
        try:
            is_dir = os.path.isdir(p)
            try:
                sz = 0
                if is_dir:
                    for r, d, f in os.walk(p):
                        for x in f:
                            try:
                                sz += os.path.getsize(os.path.join(r, x))
                            except Exception:
                                pass
                else:
                    sz = os.path.getsize(p)
            except Exception:
                sz = 0
            try:
                mt = datetime.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d %H:%M")
            except Exception:
                mt = "؟"
            messagebox.showinfo("مشخصات", f"نام: {os.path.basename(p)}\nمسیر: {p}\nنوع: {'پوشه' if is_dir else 'فایل'}\nحجم: {fmt_size(sz)}\nتغییر: {mt}", parent=self)
        except Exception as ex:
            messagebox.showerror("خطا", str(ex), parent=self)

    # ---------- dialogs / file ops ----------

    def _ask_name(self, title, initial=""):
        dlg = tk.Toplevel(self)
        dlg.title(title)
        dlg.configure(bg=PANEL)
        dlg.transient(self)
        dlg.grab_set()
        dlg.geometry("360x140")
        dlg.resizable(False, False)
        tk.Label(dlg, text=title, font=("Tahoma", 10), bg=PANEL, fg=TEXT).pack(pady=(16, 6))
        var = tk.StringVar(value=initial)
        ent = tk.Entry(dlg, textvariable=var, bg=PANEL_2, fg=TEXT, relief="flat", font=("Tahoma", 11), justify="center", highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT)
        ent.pack(fill="x", padx=30, ipady=5)
        result = {"ok": False}
        def ok(event=None):
            nm = var.get().strip()
            bad = set('/\\:*?"<>|')
            if any(c in bad for c in nm):
                messagebox.showwarning("نام نامعتبر", "این کاراکترها مجاز نیست: / \\ : * ? \" < > |", parent=dlg)
                return
            if not nm:
                return
            result["ok"] = True
            dlg.destroy()
        ent.bind("<Return>", ok)
        tk.Button(dlg, text="تأیید", relief="flat", bd=0, cursor="hand2", bg=ACCENT, fg="#1a1005", font=("Tahoma", 10, "bold"), padx=18, command=ok).pack(pady=12)
        ent.focus()
        ent.select_range(0, "end")
        self.wait_window(dlg)
        return var.get().strip() if result["ok"] else None

    def _run_bg(self, func, ok_msg="انجام شد"):
        def worker():
            try:
                func()
            except Exception as ex:
                self._ui_call(lambda ex=ex: messagebox.showerror("خطا", str(ex), parent=self))
                self._ui_call(lambda ex=ex: self.set_status(f"خطا: {ex}", RED))
                return
            self._ui_call(lambda: (self.refresh(), self.set_status(ok_msg, GREEN), self.set_prog(0)))
        self.set_status("در حال انجام عملیات...", YELLOW)
        threading.Thread(target=worker, daemon=True).start()

    def new_folder(self):
        if getattr(self, "in_scan", False):
            self.set_status("اول برگشت به مرور را بزن", YELLOW)
            return
        name = self._ask_name("نام پوشه جدید:")
        if not name:
            return
        path = os.path.join(self.current, name)
        base, ext = path, 1
        while os.path.exists(path):
            path = f"{base} ({ext})"
            ext += 1
        try:
            os.makedirs(path)
            self.refresh()
            self.set_status(f"پوشه «{os.path.basename(path)}» ساخته شد", GREEN)
        except Exception as ex:
            messagebox.showerror("خطا", str(ex), parent=self)

    def new_file(self):
        if getattr(self, "in_scan", False):
            self.set_status("اول برگشت به مرور را بزن", YELLOW)
            return
        name = self._ask_name("نام فایل جدید:")
        if not name:
            return
        path = os.path.join(self.current, name)
        if os.path.exists(path):
            messagebox.showwarning("تکراری", "این نام قبلا وجود دارد.", parent=self)
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("")
            self.refresh()
            self.set_status(f"فایل «{name}» ساخته شد", GREEN)
        except Exception as ex:
            messagebox.showerror("خطا", str(ex), parent=self)

    def rename_item(self):
        ps = self.selected_paths()
        if not ps:
            self.set_status("ابتدا یک آیتم را انتخاب کنید", YELLOW)
            return
        if len(ps) > 1:
            messagebox.showwarning("تغییرنام", "فقط یک آیتم را برای تغییرنام انتخاب کن.", parent=self)
            return
        path = ps[0]
        if not os.path.exists(path):
            self.set_status("این آیتم دیگر وجود ندارد", YELLOW)
            return
        old = os.path.basename(path)
        new = self._ask_name("نام جدید:", old)
        if not new or new == old:
            return
        try:
            base_dir = os.path.dirname(path) if getattr(self, "in_scan", False) else self.current
            os.rename(path, os.path.join(base_dir, new))
            self.refresh()
            self.set_status(f"«{old}» به «{new}» تغییر نام یافت", GREEN)
        except Exception as ex:
            messagebox.showerror("خطا", str(ex), parent=self)

    def copy_item(self):
        ps = self.selected_paths()
        if ps:
            self.clipboard = (list(ps), True)
            self.set_status(f"{len(ps)} آیتم کپی شد — مقصد را باز کنید و «چسباندن» بزنید", GREEN)

    def cut_item(self):
        ps = self.selected_paths()
        if ps:
            self.clipboard = (list(ps), False)
            self.set_status(f"{len(ps)} آیتم برش شد — مقصد را باز کنید و «چسباندن» بزنید", YELLOW)

    def paste_item(self):
        if not self.clipboard:
            self.set_status("چیزی برای چسباندن نیست", YELLOW)
            return
        if getattr(self, "in_scan", False):
            self.set_status("اول برگشت به مرور را بزن بعد بچسبان", YELLOW)
            return
        srcs, is_copy = self.clipboard
        srcs = [s for s in srcs if os.path.exists(s)]
        if not srcs:
            self.set_status("فایل مبدأ دیگر وجود ندارد", RED)
            self.clipboard = None
            return
        self.copy_stop = False
        total = len(srcs)
        def worker():
            for i, src in enumerate(srcs):
                if self.copy_stop:
                    break
                # dst بیرون از try تعریف می‌شود تا هرگز NameError نگیرد
                dst = os.path.join(self.current, os.path.basename(src))
                try:
                    if os.path.abspath(src) == os.path.abspath(dst):
                        base, ext = os.path.splitext(dst)
                        dst = f"{base} - کپی{ext}"
                    if os.path.isdir(src) and os.path.abspath(dst).startswith(os.path.abspath(src) + os.sep):
                        self._ui_call(lambda: messagebox.showwarning("خطا", "نمی‌شود پوشه را داخل خودش کپی کرد.", parent=self))
                        continue
                except Exception:
                    pass
                try:
                    if os.path.isdir(src):
                        if is_copy:
                            if os.path.exists(dst):
                                shutil.copytree(src, dst, dirs_exist_ok=True)
                            else:
                                shutil.copytree(src, dst)
                        else:
                            shutil.move(src, dst)
                    else:
                        if is_copy:
                            shutil.copy2(src, dst)
                        else:
                            shutil.move(src, dst)
                except Exception as ex:
                    self._ui_call(lambda ex=ex, s=src: messagebox.showerror("خطا", f"{s}: {ex}", parent=self))
                    continue
                v = (i + 1) * 100 / max(1, total)
                self._ui_call(lambda v=v: (self.set_prog(v), self.set_status(f"کپی {int(v)}٪ ...", YELLOW)))
            def done():
                if not is_copy:
                    self.clipboard = None
                self.refresh()
                self.set_prog(100)
                self.set_status("عملیات انجام شد", GREEN)
            self._ui_call(done)
        self.set_status("در حال کپی/انتقال...", YELLOW)
        threading.Thread(target=worker, daemon=True).start()

    def zip_selected(self):
        ps = self.selected_paths()
        if not ps:
            self.set_status("ابتدا فایل انتخاب کن", YELLOW)
            return
        zpath = filedialog.asksaveasfilename(title="ذخیره زیپ", defaultextension=".zip", filetypes=[("ZIP", "*.zip")], parent=self)
        if not zpath:
            return
        def job():
            with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
                for p in ps:
                    if self.copy_stop:
                        break
                    if not os.path.exists(p):
                        continue
                    if os.path.isdir(p):
                        for r, d, fs in os.walk(p):
                            for fn in fs:
                                fp = os.path.join(r, fn)
                                z.write(fp, os.path.relpath(fp, os.path.dirname(p)))
                    else:
                        z.write(p, os.path.basename(p))
        self.copy_stop = False
        self._run_bg(job, "زیپ ساخته شد")

    def unzip_selected(self):
        ps = self.selected_paths()
        if not ps:
            self.set_status("یک فایل زیپ انتخاب کن", YELLOW)
            return
        zp = None
        for p in ps:
            if p.lower().endswith(".zip") and os.path.exists(p):
                zp = p
                break
        if not zp:
            self.set_status("فایل زیپ انتخاب نشده", YELLOW)
            return
        dest = filedialog.askdirectory(title="پوشه مقصد آنزیپ", parent=self)
        if not dest:
            return
        def job():
            with zipfile.ZipFile(zp, "r") as z:
                try:
                    # محافظت در برابر مسیرهای مخرب ../ داخل زیپ (zip-slip)
                    z.extractall(dest, filter="data")
                except TypeError:
                    # پایتون قدیمی‌تر از 3.12 پارامتر filter را ندارد
                    for member in z.namelist():
                        target = os.path.realpath(os.path.join(dest, member))
                        if not target.startswith(os.path.realpath(dest) + os.sep):
                            continue
                        z.extract(member, dest)
        self._run_bg(job, "آنزیپ شد")

    def delete_item(self):
        ps = self.selected_paths()
        if not ps:
            return
        if not messagebox.askyesno("تأیید حذف", f"{len(ps)} آیتم حذف شود؟{' (می‌رود به سطل آشغال)' if HAS_TRASH else ' (دائمی!)'}", parent=self):
            return
        def job():
            errors = []
            for p in ps:
                try:
                    if not os.path.exists(p):
                        continue
                    deleted = False
                    if HAS_TRASH:
                        try:
                            send2trash(p)
                            deleted = True
                        except Exception:
                            deleted = False
                    if not deleted:
                        # اگر سطل آشغال خطا داد (نسخه قدیمی send2trash یا دسترسی محدود)،
                        # حذف مستقیم انجام می‌شود چون کاربر قبلاً تأیید کرده است
                        if os.path.isdir(p) and not os.path.islink(p):
                            shutil.rmtree(p, ignore_errors=False)
                        else:
                            os.remove(p)
                except Exception as ex:
                    errors.append(f"{p}: {ex}")
            if errors:
                raise Exception("\n".join(errors[:5]))
        msg = "به سطل آشغال رفت" if HAS_TRASH else "حذف شد (بدون send2trash دائمی است)"
        self._run_bg(job, msg)

    def show_menu(self, event):
        try:
            item = self.tree.identify_row(event.y)
        except Exception:
            return
        if item:
            try:
                if item not in self.tree.selection():
                    self.tree.selection_set(item)
                self.menu.post(event.x_root, event.y_root)
            except Exception:
                pass

if __name__ == "__main__":
    App().mainloop()
