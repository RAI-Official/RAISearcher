import os
import threading
import queue
import customtkinter as ctk
from tkinter import messagebox, filedialog
import psutil
from tkinter import ttk


# ---------------- Global Flags ----------------
stop_flag = False
search_thread = None

# ---------------- Drives ----------------
def list_drives():
    drives = [d.device for d in psutil.disk_partitions(all=False)]
    drives.append("Select Folder...")
    return drives

# ---------------- Super Search ----------------
EXCLUDE_DIRS = [
    "C:\\Windows",
    "C:\\Program Files",
    "C:\\Program Files (x86)",
    "C:\\$Recycle.Bin",
    "C:\\ProgramData",
    "C:\\Users\\Default",
    "C:\\Users\\All Users"
]

def should_skip(path):
    for excl in EXCLUDE_DIRS:
        if path.startswith(excl):
            return True
    return False

def fast_scandir(drive, query, extension=None, include_folders=True, exact_match=False, callback=None):
    global stop_flag
    query = query.lower()
    if extension:
        extension = extension.lower()

    q = queue.Queue()
    q.put(drive)

    def worker():
        while not q.empty() and not stop_flag:
            try:
                path = q.get_nowait()
                if should_skip(path):
                    continue
                with os.scandir(path) as it:
                    for entry in it:
                        if stop_flag:
                            break
                        name = entry.name.lower()
                        base, extn = os.path.splitext(name)

                        ## Folder
                        if entry.is_dir(follow_symlinks=False):
                            q.put(entry.path)
                            if include_folders:
                                if exact_match:
                                    if name == query:
                                        if callback:
                                            callback(entry.path)
                                else:
                                    if query in name:
                                        if callback:
                                            callback(entry.path)
                        
                        # File
                        elif entry.is_file(follow_symlinks=False):
                            if exact_match:
                                if base == query:
                                    if not extension or name.endswith(extension):
                                        if callback:
                                            callback(entry.path)
                            else:
                                if query in name:
                                    if not extension or name.endswith(extension):
                                        if callback:
                                            callback(entry.path)

            except (PermissionError, FileNotFoundError, OSError):
                continue

    num_threads = os.cpu_count() * 2
    threads = []
    for _ in range(num_threads):
        t = threading.Thread(target=worker, daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

# ---------------- Search Orchestrator ----------------
def perform_search(drive, query, ext, include_folders=True, exact_match=False):
    global stop_flag
    stop_flag = False
    clear_results()

    def lazy_insert(path):
        root.after(0, lambda: insert_result(path))

    fast_scandir(drive, query, ext, include_folders, exact_match, callback=lazy_insert)

    if stop_flag:
        insert_result("Search stopped by user.")
    elif not results_tree.get_children():
        insert_result("No files/folders found.")

    root.after(0, stop_animation)
    root.after(0, reset_ui_after_search)

def threaded_search(drive, query, ext, include_folders=True, exact_match=False):
    global search_thread
    def task():
        perform_search(drive, query, ext, include_folders, exact_match)

    start_animation()
    disable_inputs()
    search_btn.configure(text="Stop Search", command=on_stop)
    search_thread = threading.Thread(target=task, daemon=True)
    search_thread.start()

# ---------------- GUI Callbacks ----------------
def on_search():
    if search_btn.cget("text") == "Stop Search":
        on_stop()
        return

    drive = drive_var.get()
    query = search_var.get().strip().lower()
    ext = ext_var.get().strip().lower()
    exact_match = exact_var.get()

    if "." in query and not ext:
        detected_ext = os.path.splitext(query)[1]
        if detected_ext:
            ext_var.set(detected_ext)
            ext = detected_ext

    if ext and not ext.startswith("."):
        ext = "." + ext

    if not drive or not query:
        messagebox.showwarning("Input Error", "Select a drive/folder and enter a search term.")
        return

    threaded_search(
        drive,
        query,
        ext,
        include_folders=True,
        exact_match=exact_var.get()  # ✅ Use .get() here
    )


def on_stop():
    global stop_flag
    stop_flag = True

def on_drive_selected(event):
    choice = drive_var.get()
    if choice == "Select Folder...":
        folder = ctk.filedialog.askdirectory()
        if folder:
            # Update dropdown values
            current_values = list(drive_dropdown.cget("values"))  # get current values
            if "Select Folder..." in current_values:
                current_values.remove("Select Folder...")
            current_values.append(folder)
            current_values.append("Select Folder...")  # keep option
            drive_dropdown.configure(values=current_values)
            drive_var.set(folder)  # select newly chosen folder




def open_selected(event):
    try:
        selection = results_tree.get(ctk.ACTIVE)
        if not selection:
            return
        path = results_tree.item(selection, "values")[0]
        if os.path.exists(path):
            os.startfile(path)
    except Exception as e:
        messagebox.showerror("Error", f"Could not open: {e}")

def copy_selected():
    try:
        selection = results_tree.selection()
        if not selection:
            messagebox.showwarning("Copy Error", "No item selected.")
            return
        path = results_tree.item(selection[0], "values")[0]
        root.clipboard_clear()
        root.clipboard_append(path)
        root.update()
        messagebox.showinfo("Copied", "Path copied to clipboard!")
    except Exception as e:
        messagebox.showerror("Error", f"Could not copy path: {e}")


# ---------------- Results Handling ----------------
def clear_results():
    for item in results_tree.get_children():
        results_tree.delete(item)

def insert_result(path):
    results_tree.insert("", "end", values=(path,))


# ---------------- Animation ----------------
spinner_frames = ["|", "/", "-", "\\"]
spinner_index = 0
animating = False

def animate():
    global spinner_index
    if animating:
        spinner_label.configure(text=f"{spinner_frames[spinner_index]} Searching...")
        spinner_index = (spinner_index + 1) % len(spinner_frames)
        root.after(200, animate)

def start_animation():
    global animating, spinner_index
    animating = True
    spinner_index = 0
    spinner_label.place(x=10, y=5)
    animate()

def stop_animation():
    global animating
    animating = False
    spinner_label.place_forget()

# ---------------- UI Enable/Disable ----------------
def disable_inputs():
    drive_dropdown.configure(state="disabled")
    ext_dropdown.configure(state="disabled")
    search_entry.configure(state="disabled")

def enable_inputs():
    drive_dropdown.configure(state="normal")
    ext_dropdown.configure(state="normal")
    search_entry.configure(state="normal")

def reset_ui_after_search():
    enable_inputs()
    search_btn.configure(text="Search", command=on_search)

# ---------------- GUI ----------------
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")  # Accent color

root = ctk.CTk()
root.title("RAISearcher")
root.geometry("900x650")

style = ttk.Style()
style.theme_use("clam")
style.configure("Treeview",
                background="#1f1f1f",
                foreground="white",
                fieldbackground="#1f1f1f",
                rowheight=25)
style.map('Treeview', background=[('selected', '#4a7cff')])


# Spinner
spinner_label = ctk.CTkLabel(root, text="", font=("Consolas", 12))

# Search bar
ctk.CTkLabel(root, text="Search:").pack(pady=5)
search_var = ctk.StringVar()
search_entry = ctk.CTkEntry(root, textvariable=search_var, width=400)
search_entry.pack(pady=5)

# File extension
ctk.CTkLabel(root, text="File Extension (optional):").pack(pady=5)
ext_var = ctk.StringVar()
common_exts = [
    ".txt", ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".webp",
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".ods", ".odp",
    ".csv", ".json", ".xml", ".html", ".htm", ".css", ".js", ".py", ".java",
    ".c", ".cpp", ".cs", ".php", ".rb", ".go", ".swift", ".sh", ".bat", ".exe",
    ".msi", ".dll", ".iso", ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2",
    ".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a",
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm"
]
ext_dropdown = ctk.CTkComboBox(root, values=common_exts, variable=ext_var)
ext_dropdown.pack(pady=5)
ext_dropdown.set("")

# Drive dropdown
ctk.CTkLabel(root, text="Select Drive or Folder:").pack(pady=5)
drive_var = ctk.StringVar()
drive_dropdown = ctk.CTkComboBox(root, variable=drive_var, values=list_drives())
drive_dropdown.pack(pady=5)
#drive_dropdown.bind("<<ComboboxSelected>>", on_drive_selected)

def drive_var_changed(*args):
    choice = drive_var.get()
    if choice == "Select Folder...":
        folder = filedialog.askdirectory()
        if folder:
            # Update dropdown values
            current_values = list(drive_dropdown.cget("values"))
            if "Select Folder..." in current_values:
                current_values.remove("Select Folder...")
            current_values.append(folder)
            current_values.append("Select Folder...")  # keep the option
            drive_dropdown.configure(values=current_values)
            drive_var.set(folder)  # select newly chosen folder
        else:
            # If user cancels folder selection, reset to first drive
            drive_var.set(current_values[0])

drive_var.trace_add("write", drive_var_changed)

# Options
exact_var = ctk.BooleanVar(value=False)
ctk.CTkCheckBox(root, text="Match Whole Name Only", variable=exact_var).pack(pady=5)

# Search button
search_btn = ctk.CTkButton(root, text="Search", command=on_search)
search_btn.pack(pady=10)

# Results Treeview
results_frame = ctk.CTkFrame(root)
results_frame.pack(pady=1, fill="both", expand=True)

columns = ("Path",)
results_tree = ttk.Treeview(results_frame, columns=columns, show="headings")
results_tree.heading("Path", text="File / Folder Path")
results_tree.column("Path", anchor="w", width=850)
results_tree.pack(side="left", fill="both", expand=True)
results_tree.bind("<Double-1>", open_selected)

scrollbar = ctk.CTkScrollbar(results_frame, orientation="vertical", command=results_tree.yview)
results_tree.configure(yscroll=scrollbar.set)
scrollbar.pack(side="right", fill="y")

# Copy button
ctk.CTkButton(root, text="Copy Selected Path", command=copy_selected).pack(pady=5)

root.mainloop()
