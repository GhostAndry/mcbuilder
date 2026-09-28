"""MC Builder GUI - premium cross-platform interface."""
from __future__ import annotations

import os
import platform
import subprocess
import sys
import threading
import queue
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Optional

import customtkinter as ctk

from .generator import Module, ProjectConfig, ProjectGenerator, ServerData, sanitize
from .gradle_versions import DEFAULT_GRADLE, FALLBACK_VERSIONS, fetch_versions


IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform.startswith("win")
IS_LINUX = sys.platform.startswith("linux")

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

PALETTE = {
    "bg": "#0e0f13",
    "panel": "#171922",
    "panel_2": "#1f2330",
    "border": "#2a2f3e",
    "text": "#e8eaf2",
    "muted": "#8b91a5",
    "accent": "#7c5cff",
    "accent_2": "#22c55e",
    "danger": "#ef4444",
    "warn": "#f59e0b",
}

FONT_FAMILY = "Inter" if platform.system() == "Darwin" else "Segoe UI"


class ToolTip:
    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self.tip: Optional[tk.Toplevel] = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, _=None):
        if self.tip:
            return
        x = self.widget.winfo_rootx() + 24
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            self.tip,
            text=self.text,
            bg=PALETTE["panel_2"],
            fg=PALETTE["text"],
            padx=10,
            pady=6,
            relief="flat",
            font=(FONT_FAMILY, 10),
            borderwidth=1,
        )
        label.pack()

    def _hide(self, _=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


class ModuleCard(ctk.CTkFrame):
    def __init__(self, master, server_data: ServerData, on_remove, **kwargs):
        super().__init__(
            master,
            corner_radius=14,
            fg_color=PALETTE["panel"],
            border_color=PALETTE["border"],
            border_width=1,
            **kwargs,
        )
        self.server_data = server_data
        self.on_remove = on_remove

        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(self, text="Server", text_color=PALETTE["muted"], font=(FONT_FAMILY, 11)).grid(
            row=0, column=0, padx=(16, 8), pady=(14, 4), sticky="w"
        )
        self.server_var = tk.StringVar(value="paper")
        self.server_menu = ctk.CTkOptionMenu(
            self,
            values=server_data.server_names(),
            variable=self.server_var,
            command=self._on_server_change,
            width=160,
            height=32,
            corner_radius=8,
            fg_color=PALETTE["panel_2"],
            button_color=PALETTE["accent"],
            button_hover_color="#6b46d8",
            text_color=PALETTE["text"],
            dropdown_fg_color=PALETTE["panel_2"],
            dropdown_hover_color=PALETTE["accent"],
            dropdown_text_color=PALETTE["text"],
            font=(FONT_FAMILY, 12),
        )
        self.server_menu.grid(row=1, column=0, padx=(16, 8), pady=(0, 12), sticky="w")

        ctk.CTkLabel(self, text="Version", text_color=PALETTE["muted"], font=(FONT_FAMILY, 11)).grid(
            row=0, column=1, padx=8, pady=(14, 4), sticky="w"
        )
        self.version_var = tk.StringVar()
        self.version_menu = ctk.CTkOptionMenu(
            self,
            values=[],
            variable=self.version_var,
            width=120,
            height=32,
            corner_radius=8,
            fg_color=PALETTE["panel_2"],
            button_color=PALETTE["accent"],
            button_hover_color="#6b46d8",
            text_color=PALETTE["text"],
            dropdown_fg_color=PALETTE["panel_2"],
            dropdown_hover_color=PALETTE["accent"],
            dropdown_text_color=PALETTE["text"],
            font=(FONT_FAMILY, 12),
        )
        self.version_menu.grid(row=1, column=1, padx=8, pady=(0, 12), sticky="w")

        self.preview_label = ctk.CTkLabel(
            self,
            text="",
            text_color=PALETTE["muted"],
            font=(FONT_FAMILY, 11),
            anchor="w",
        )
        self.preview_label.grid(row=0, column=3, rowspan=2, padx=8, pady=14, sticky="ew")

        self.remove_btn = ctk.CTkButton(
            self,
            text="✕",
            width=36,
            height=36,
            corner_radius=10,
            fg_color="transparent",
            hover_color=PALETTE["danger"],
            text_color=PALETTE["muted"],
            font=(FONT_FAMILY, 14, "bold"),
            command=self._remove,
        )
        self.remove_btn.grid(row=0, column=4, rowspan=2, padx=(8, 14), pady=14, sticky="ns")

        self._on_server_change(self.server_var.get())
        self.version_var.trace_add("write", lambda *_: self._refresh_preview())

    def _on_server_change(self, server: str):
        versions = self.server_data.versions(server)
        if versions:
            self.version_menu.configure(values=versions)
            self.version_var.set(versions[0])
        else:
            self.version_menu.configure(values=[])
            self.version_var.set("")
        self._refresh_preview()

    def _refresh_preview(self):
        name = self.module_name()
        self.preview_label.configure(text=f"→ {name}")

    def module_name(self) -> str:
        parts = [self.server_var.get(), self.version_var.get()]
        return "-".join(p for p in parts if p)

    def get_module(self) -> Optional[Module]:
        server = self.server_var.get()
        version = self.version_var.get()
        if not server or not version:
            return None
        return Module(server=server, version=version)

    def refresh(self):
        self._refresh_preview()

    def _remove(self):
        if self.on_remove:
            self.on_remove(self)


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("MC Builder")
        self.geometry("1100x760")
        self.minsize(960, 640)
        self.configure(fg_color=PALETTE["bg"])

        try:
            self.iconbitmap(default="")
        except Exception:
            pass

        self.server_data = ServerData(Path(__file__).parent / "assets" / "server_data.json")
        self.template_dir = Path(__file__).parent / "templates"
        self.output_dir: Optional[Path] = None
        self.module_cards: list[ModuleCard] = []

        self._build_layout()
        self._add_module_card()

        self.bind("<Command-n>" if IS_MAC else "<Control-n>", lambda e: self._add_module_card())

    def _build_layout(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main()

    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self, corner_radius=0, fg_color=PALETTE["panel"], width=320)
        sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, 1))
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(sidebar, fg_color="transparent")
        header.grid(row=0, column=0, padx=24, pady=(28, 18), sticky="ew")

        logo_frame = ctk.CTkFrame(
            header,
            width=44,
            height=44,
            corner_radius=12,
            fg_color=PALETTE["accent"],
        )
        logo_frame.grid(row=0, column=0, padx=(0, 12), sticky="w")
        logo_frame.grid_propagate(False)
        ctk.CTkLabel(
            logo_frame,
            text="⬢",
            text_color="white",
            font=(FONT_FAMILY, 22, "bold"),
        ).place(relx=0.5, rely=0.5, anchor="center")

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(
            title_box,
            text="MC Builder",
            text_color=PALETTE["text"],
            font=(FONT_FAMILY, 18, "bold"),
            anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            title_box,
            text="Multi-module plugin project generator",
            text_color=PALETTE["muted"],
            font=(FONT_FAMILY, 11),
            anchor="w",
        ).pack(anchor="w")

        section = ctk.CTkLabel(
            sidebar,
            text="PROJECT",
            text_color=PALETTE["muted"],
            font=(FONT_FAMILY, 10, "bold"),
            anchor="w",
        )
        section.grid(row=1, column=0, padx=24, pady=(8, 6), sticky="ew")

        fields = ctk.CTkFrame(sidebar, fg_color="transparent")
        fields.grid(row=2, column=0, padx=24, pady=(0, 12), sticky="ew")
        fields.grid_columnconfigure(0, weight=1)

        self.name_entry = self._labeled_entry(fields, "Project name", "my-plugin", row=0)
        self.group_entry = self._labeled_entry(fields, "Group", "com.example", row=1)
        self.version_entry = self._labeled_entry(fields, "Version", "1.0.0", row=2)
        self.desc_entry = self._labeled_entry(fields, "Description", "Awesome plugin suite", row=3)

        self.java_var = tk.StringVar(value="17")
        self.gradle_var = tk.StringVar(value=DEFAULT_GRADLE)

        adv = ctk.CTkFrame(sidebar, fg_color="transparent")
        adv.grid(row=3, column=0, padx=24, pady=(0, 12), sticky="ew")
        adv.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(adv, text="Java", text_color=PALETTE["muted"], font=(FONT_FAMILY, 11), anchor="w").grid(
            row=0, column=0, sticky="w"
        )
        ctk.CTkLabel(adv, text="Gradle", text_color=PALETTE["muted"], font=(FONT_FAMILY, 11), anchor="w").grid(
            row=0, column=1, sticky="w"
        )
        ctk.CTkOptionMenu(
            adv,
            values=["8", "11", "17", "21"],
            variable=self.java_var,
            width=120,
            height=30,
            corner_radius=8,
            fg_color=PALETTE["panel_2"],
            button_color=PALETTE["accent"],
            text_color=PALETTE["text"],
            dropdown_fg_color=PALETTE["panel_2"],
            font=(FONT_FAMILY, 11),
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.gradle_menu = ctk.CTkComboBox(
            adv,
            values=FALLBACK_VERSIONS,
            variable=self.gradle_var,
            width=120,
            height=30,
            corner_radius=8,
            fg_color=PALETTE["panel_2"],
            button_color=PALETTE["accent"],
            text_color=PALETTE["text"],
            dropdown_fg_color=PALETTE["panel_2"],
            font=(FONT_FAMILY, 11),
        )
        self.gradle_menu.grid(row=1, column=1, sticky="w", pady=(4, 0))
        self.gradle_results = queue.Queue()
        def load_versions():
            try:
                self.gradle_results.put(fetch_versions())
            except Exception:
                self.gradle_results.put(None)
        threading.Thread(target=load_versions, daemon=True).start()
        self.after(100, self._poll_gradle_versions)

        output_frame = ctk.CTkFrame(sidebar, fg_color=PALETTE["panel_2"], corner_radius=12)
        output_frame.grid(row=4, column=0, padx=24, pady=(8, 12), sticky="ew")
        output_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            output_frame,
            text="OUTPUT LOCATION",
            text_color=PALETTE["muted"],
            font=(FONT_FAMILY, 10, "bold"),
            anchor="w",
        ).grid(row=0, column=0, padx=14, pady=(12, 4), sticky="ew")

        self.output_label = ctk.CTkLabel(
            output_frame,
            text="No folder selected",
            text_color=PALETTE["muted"],
            font=(FONT_FAMILY, 11),
            anchor="w",
            wraplength=240,
        )
        self.output_label.grid(row=1, column=0, padx=14, pady=(0, 8), sticky="ew")

        ctk.CTkButton(
            output_frame,
            text="Choose folder…",
            command=self._choose_output,
            height=34,
            corner_radius=10,
            fg_color=PALETTE["accent"],
            hover_color="#6b46d8",
            text_color="white",
            font=(FONT_FAMILY, 12, "bold"),
        ).grid(row=2, column=0, padx=14, pady=(0, 14), sticky="ew")

        footer = ctk.CTkFrame(sidebar, fg_color="transparent")
        footer.grid(row=5, column=0, padx=24, pady=(8, 24), sticky="ew")
        ctk.CTkLabel(
            footer,
            text=f"v{self._version()} · {platform.system()} {platform.release()}",
            text_color=PALETTE["muted"],
            font=(FONT_FAMILY, 10),
        ).pack(anchor="w")

    def _poll_gradle_versions(self):
        try:
            versions = self.gradle_results.get_nowait()
        except queue.Empty:
            self.after(100, self._poll_gradle_versions)
            return
        if versions:
            self.gradle_menu.configure(values=versions)
            self._set_status(f"Versioni Gradle aggiornate — ultima stabile: {versions[0]}")
        else:
            self._set_status("Gradle: elenco offline; puoi inserire la versione manualmente.")

    def _build_main(self):
        main = ctk.CTkFrame(self, corner_radius=0, fg_color=PALETTE["bg"])
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(main, fg_color="transparent")
        header.grid(row=0, column=0, padx=32, pady=(28, 8), sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="Modules",
            text_color=PALETTE["text"],
            font=(FONT_FAMILY, 22, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            header,
            text="Moduli {server}-{version}, con API condivisa opzionale.",
            text_color=PALETTE["muted"],
            font=(FONT_FAMILY, 12),
            anchor="w",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.grid(row=0, column=1, rowspan=2, sticky="e")

        self.add_btn = ctk.CTkButton(
            actions,
            text="+ Add module",
            command=self._add_module_card,
            height=38,
            corner_radius=10,
            fg_color=PALETTE["panel_2"],
            hover_color=PALETTE["border"],
            text_color=PALETTE["text"],
            border_width=1,
            border_color=PALETTE["border"],
            font=(FONT_FAMILY, 12, "bold"),
        )
        self.add_btn.pack(side="left", padx=(0, 10))
        ToolTip(self.add_btn, "Add a new module (Ctrl/Cmd+N)")

        self.generate_btn = ctk.CTkButton(
            actions,
            text="⚡ Generate project",
            command=self._generate,
            height=38,
            corner_radius=10,
            fg_color=PALETTE["accent_2"],
            hover_color="#16a34a",
            text_color="#06210f",
            font=(FONT_FAMILY, 12, "bold"),
        )
        self.generate_btn.pack(side="left")

        self.include_api_var = tk.BooleanVar(value=False)
        self.api_checkbox = ctk.CTkCheckBox(
            main,
            text="Crea modulo API condiviso — interfacce e contratti del progetto",
            variable=self.include_api_var,
            fg_color=PALETTE["accent"],
            text_color=PALETTE["text"],
            font=(FONT_FAMILY, 12),
        )
        self.api_checkbox.grid(row=1, column=0, padx=32, pady=12, sticky="w")

        scroll_holder = ctk.CTkFrame(main, fg_color="transparent")
        scroll_holder.grid(row=2, column=0, padx=32, pady=(8, 8), sticky="nsew")
        scroll_holder.grid_columnconfigure(0, weight=1)
        scroll_holder.grid_rowconfigure(0, weight=1)

        self.modules_frame = ctk.CTkScrollableFrame(
            scroll_holder,
            corner_radius=14,
            fg_color=PALETTE["panel"],
            border_color=PALETTE["border"],
            border_width=1,
        )
        self.modules_frame.grid(row=0, column=0, sticky="nsew")
        self.modules_frame.grid_columnconfigure(0, weight=1)

        self.empty_state = ctk.CTkLabel(
            self.modules_frame,
            text="No modules yet. Click '+ Add module' to start.",
            text_color=PALETTE["muted"],
            font=(FONT_FAMILY, 12),
        )

        self.status = ctk.CTkLabel(
            main,
            text="Ready",
            text_color=PALETTE["muted"],
            font=(FONT_FAMILY, 11),
            anchor="w",
        )
        self.status.grid(row=3, column=0, padx=32, pady=(0, 20), sticky="ew")

    def _labeled_entry(self, parent, label: str, placeholder: str, row: int):
        ctk.CTkLabel(
            parent,
            text=label,
            text_color=PALETTE["muted"],
            font=(FONT_FAMILY, 11),
            anchor="w",
        ).grid(row=row * 2, column=0, pady=(8, 4), sticky="w")

        entry = ctk.CTkEntry(
            parent,
            placeholder_text=placeholder,
            height=34,
            corner_radius=10,
            fg_color=PALETTE["panel_2"],
            border_color=PALETTE["border"],
            text_color=PALETTE["text"],
            placeholder_text_color=PALETTE["muted"],
            font=(FONT_FAMILY, 12),
        )
        entry.grid(row=row * 2 + 1, column=0, sticky="ew")
        return entry

    def _add_module_card(self):
        self.empty_state.grid_forget()
        card = ModuleCard(self.modules_frame, self.server_data, on_remove=self._remove_module_card)
        card.grid(row=len(self.module_cards), column=0, padx=8, pady=8, sticky="ew")
        self.module_cards.append(card)
        self._set_status(f"Module #{len(self.module_cards)} added")

    def _remove_module_card(self, card: ModuleCard):
        if card in self.module_cards:
            self.module_cards.remove(card)
            card.destroy()
            for i, c in enumerate(self.module_cards):
                c.grid(row=i, column=0, padx=8, pady=8, sticky="ew")
        if not self.module_cards:
            self.empty_state.grid(row=0, column=0, pady=40)
        self._set_status("Module removed")

    def _choose_output(self):
        folder = filedialog.askdirectory(title="Select output folder")
        if folder:
            self.output_dir = Path(folder)
            self.output_label.configure(text=str(self.output_dir), text_color=PALETTE["text"])
            self._set_status(f"Output: {self.output_dir}")

    def _build_config(self) -> Optional[ProjectConfig]:
        name = sanitize(self.name_entry.get() or "my-plugin")
        group = self.group_entry.get().strip() or "com.example"
        version = self.version_entry.get().strip() or "1.0.0"
        description = self.desc_entry.get().strip()

        if not self.module_cards:
            messagebox.showwarning("MC Builder", "Add at least one module.")
            return None

        modules = []
        seen = set()
        for card in self.module_cards:
            m = card.get_module()
            if not m:
                continue
            if m.name in seen:
                messagebox.showerror(
                    "MC Builder",
                    f"Duplicate module: {m.name}\nChoose a different server/version.",
                )
                return None
            seen.add(m.name)
            modules.append(m)

        if not modules:
            messagebox.showwarning("MC Builder", "Modules are not configured correctly.")
            return None

        return ProjectConfig(
            name=name,
            group=group,
            version=version,
            description=description,
            java_version=self.java_var.get(),
            gradle_version=self.gradle_var.get(),
            modules=modules,
            include_api=self.include_api_var.get(),
        )

    def _generate(self):
        if not self.output_dir:
            messagebox.showwarning("MC Builder", "Select an output folder first.")
            return

        config = self._build_config()
        if not config:
            return

        target = self.output_dir / config.name
        if target.exists():
            if not messagebox.askyesno(
                "MC Builder",
                f"Folder '{config.name}' already exists at:\n{self.output_dir}\n\nOverwrite?",
            ):
                return

        self._set_status("Generating project…")
        self.generate_btn.configure(state="disabled")

        def work():
            try:
                gen = ProjectGenerator(config, self.server_data, self.template_dir)
                gen.generate(self.output_dir)
                self.after(0, lambda: self._on_success(config, target))
            except Exception as e:
                self.after(0, lambda err=e: self._on_error(err))

        threading.Thread(target=work, daemon=True).start()

    def _on_success(self, config: ProjectConfig, target: Path):
        self.generate_btn.configure(state="normal")
        self._set_status(f"✓ Project generated at {target}")
        if messagebox.askyesno("MC Builder", f"Project created!\n\n{target}\n\nOpen the folder now?"):
            self._open_folder(target)

    def _on_error(self, err: Exception):
        self.generate_btn.configure(state="normal")
        self._set_status(f"✗ Error: {err}")
        messagebox.showerror("MC Builder", f"Generation failed:\n{err}")

    def _open_folder(self, path: Path):
        try:
            if IS_MAC:
                subprocess.run(["open", str(path)])
            elif IS_WIN:
                os.startfile(str(path))
            else:
                subprocess.run(["xdg-open", str(path)])
        except Exception as e:
            self._set_status(f"Could not open folder: {e}")

    def _set_status(self, text: str):
        self.status.configure(text=text)

    def _version(self) -> str:
        from . import __version__
        return __version__


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
