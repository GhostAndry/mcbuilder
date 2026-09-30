"""MC Builder GUI - premium cross-platform interface (Aurora-style)."""
from __future__ import annotations

import os
import platform
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Optional

import customtkinter as ctk

from .generator import BUKKIT, VELOCITY, NmsData, ProjectConfig, ProjectGenerator, sanitize
from .gradle_versions import DEFAULT_GRADLE, FALLBACK_VERSIONS, fetch_versions


IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform.startswith("win")

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
        tk.Label(
            self.tip,
            text=self.text,
            bg=PALETTE["panel_2"],
            fg=PALETTE["text"],
            padx=10,
            pady=6,
            font=(FONT_FAMILY, 10),
            borderwidth=1,
        ).pack()

    def _hide(self, _=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("MC Builder")
        self.geometry("1120x780")
        self.minsize(1000, 680)
        self.configure(fg_color=PALETTE["bg"])

        self.nms_data = NmsData(Path(__file__).parent / "assets" / "nms_data.json")
        self.template_dir = Path(__file__).parent / "templates"
        self.output_dir: Optional[Path] = None
        self.nms_vars: dict[str, tk.BooleanVar] = {}

        self._build_layout()

    # ------------------------------------------------------------------ layout

    def _build_layout(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()
        self._build_main()

    def _build_sidebar(self):
        side = ctk.CTkFrame(self, corner_radius=0, fg_color=PALETTE["panel"], width=330)
        side.grid(row=0, column=0, sticky="nsew", padx=(0, 1))
        side.grid_propagate(False)
        side.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(side, fg_color="transparent")
        header.grid(row=0, column=0, padx=24, pady=(28, 18), sticky="ew")

        logo = ctk.CTkFrame(header, width=44, height=44, corner_radius=12, fg_color=PALETTE["accent"])
        logo.grid(row=0, column=0, padx=(0, 12), sticky="w")
        logo.grid_propagate(False)
        ctk.CTkLabel(logo, text="⬢", text_color="white", font=(FONT_FAMILY, 22, "bold")).place(
            relx=0.5, rely=0.5, anchor="center"
        )

        title = ctk.CTkFrame(header, fg_color="transparent")
        title.grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(title, text="MC Builder", text_color=PALETTE["text"],
                     font=(FONT_FAMILY, 18, "bold"), anchor="w").pack(anchor="w")
        ctk.CTkLabel(title, text="Multi-platform plugin generator",
                     text_color=PALETTE["muted"], font=(FONT_FAMILY, 11), anchor="w").pack(anchor="w")

        ctk.CTkLabel(side, text="PROJECT", text_color=PALETTE["muted"],
                     font=(FONT_FAMILY, 10, "bold"), anchor="w").grid(
            row=1, column=0, padx=24, pady=(8, 6), sticky="ew")

        fields = ctk.CTkFrame(side, fg_color="transparent")
        fields.grid(row=2, column=0, padx=24, pady=(0, 8), sticky="ew")
        fields.grid_columnconfigure(0, weight=1)

        self.name_entry = self._entry(fields, "Project name", "MyPlugin", 0)
        self.group_entry = self._entry(fields, "Group", "com.example", 1)
        self.version_entry = self._entry(fields, "Version", "1.0.0", 2)
        self.desc_entry = self._entry(fields, "Description", "Awesome plugin", 3)

        adv = ctk.CTkFrame(side, fg_color="transparent")
        adv.grid(row=3, column=0, padx=24, pady=(0, 8), sticky="ew")
        adv.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(adv, text="Java", text_color=PALETTE["muted"], font=(FONT_FAMILY, 11), anchor="w").grid(
            row=0, column=0, sticky="w")
        ctk.CTkLabel(adv, text="Gradle", text_color=PALETTE["muted"], font=(FONT_FAMILY, 11), anchor="w").grid(
            row=0, column=1, sticky="w")

        self.java_var = tk.StringVar(value="21")
        self.gradle_var = tk.StringVar(value=DEFAULT_GRADLE)
        self._menu(adv, ["17", "21", "25"], self.java_var).grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.gradle_menu = ctk.CTkComboBox(
            adv, values=FALLBACK_VERSIONS, variable=self.gradle_var, width=130, height=30,
            corner_radius=8, fg_color=PALETTE["panel_2"], button_color=PALETTE["accent"],
            text_color=PALETTE["text"], dropdown_fg_color=PALETTE["panel_2"], font=(FONT_FAMILY, 11),
        )
        self.gradle_menu.grid(row=1, column=1, sticky="w", pady=(4, 0))

        output = ctk.CTkFrame(side, fg_color=PALETTE["panel_2"], corner_radius=12)
        output.grid(row=4, column=0, padx=24, pady=(8, 12), sticky="ew")
        output.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(output, text="OUTPUT LOCATION", text_color=PALETTE["muted"],
                     font=(FONT_FAMILY, 10, "bold"), anchor="w").grid(
            row=0, column=0, padx=14, pady=(12, 4), sticky="ew")
        self.output_label = ctk.CTkLabel(output, text="No folder selected", text_color=PALETTE["muted"],
                                         font=(FONT_FAMILY, 11), anchor="w", wraplength=250)
        self.output_label.grid(row=1, column=0, padx=14, pady=(0, 8), sticky="ew")
        ctk.CTkButton(output, text="Choose folder…", command=self._choose_output, height=34,
                      corner_radius=10, fg_color=PALETTE["accent"], hover_color="#6b46d8",
                      text_color="white", font=(FONT_FAMILY, 12, "bold")).grid(
            row=2, column=0, padx=14, pady=(0, 14), sticky="ew")

        ctk.CTkLabel(side, text=f"v{self._version()} · {platform.system()} {platform.release()}",
                     text_color=PALETTE["muted"], font=(FONT_FAMILY, 10)).grid(
            row=5, column=0, padx=24, pady=(0, 20), sticky="w")

        self.gradle_results = queue.Queue()
        threading.Thread(target=self._fetch_gradle, daemon=True).start()
        self.after(100, self._poll_gradle)

    def _build_main(self):
        main = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color=PALETTE["bg"])
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)

        head = ctk.CTkFrame(main, fg_color="transparent")
        head.grid(row=0, column=0, padx=32, pady=(28, 8), sticky="ew")
        head.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(head, text="Project layout", text_color=PALETTE["text"],
                     font=(FONT_FAMILY, 22, "bold"), anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(head, text="api → common → platforms, plus optional multi-version NMS.",
                     text_color=PALETTE["muted"], font=(FONT_FAMILY, 12), anchor="w").grid(
            row=1, column=0, sticky="w", pady=(4, 0))

        # Platform section
        self.bukkit_var = tk.BooleanVar(value=True)
        self.velocity_var = tk.BooleanVar(value=True)
        self.api_var = tk.BooleanVar(value=True)
        self.common_var = tk.BooleanVar(value=True)
        self.nms_var = tk.BooleanVar(value=False)

        self._section(main, 1, "PLATFORMS", [
            ("Paper / Bukkit plugin", self.bukkit_var),
            ("Velocity proxy plugin", self.velocity_var),
        ])
        self._section(main, 2, "SHARED MODULES", [
            ("api — interfaces and public API", self.api_var),
            ("common — shared implementations", self.common_var),
        ])

        nms_box = self._section(main, 3, "NMS (multi-version)",
                                [("Add NMS abstraction + per-version modules", self.nms_var)])
        self.nms_var.trace_add("write", lambda *_: self._toggle_nms())
        self.nms_panel = ctk.CTkFrame(main, fg_color=PALETTE["panel"], corner_radius=12,
                                      border_width=1, border_color=PALETTE["border"])
        self.nms_panel.grid(row=4, column=0, padx=32, pady=(0, 12), sticky="ew")
        self.nms_panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self.nms_panel, text="NMS versions to scaffold (BuildTools jars needed per version)",
                     text_color=PALETTE["muted"], font=(FONT_FAMILY, 11), anchor="w").grid(
            row=0, column=0, columnspan=2, padx=16, pady=(12, 6), sticky="w")
        for i, version in enumerate(self.nms_data.versions()):
            info = self.nms_data.info(version)
            var = tk.BooleanVar(value=False)
            self.nms_vars[version] = var
            ctk.CTkCheckBox(self.nms_panel, text=f"{version}  ({info.get('mc', '?')})", variable=var,
                            fg_color=PALETTE["accent"], text_color=PALETTE["text"],
                            font=(FONT_FAMILY, 11)).grid(
                row=1 + i // 2, column=i % 2, padx=16, pady=4, sticky="w")
        self.nms_panel.grid_remove()

        self.generate_btn = ctk.CTkButton(main, text="⚡ Generate project", command=self._generate,
                                          height=44, corner_radius=12, fg_color=PALETTE["accent_2"],
                                          hover_color="#16a34a", text_color="#06210f",
                                          font=(FONT_FAMILY, 14, "bold"))
        self.generate_btn.grid(row=5, column=0, padx=32, pady=(8, 8), sticky="ew")

        self.status = ctk.CTkLabel(main, text="Ready", text_color=PALETTE["muted"],
                                   font=(FONT_FAMILY, 11), anchor="w")
        self.status.grid(row=6, column=0, padx=32, pady=(0, 20), sticky="ew")

    def _section(self, parent, row, title, options):
        frame = ctk.CTkFrame(parent, fg_color=PALETTE["panel"], corner_radius=12,
                             border_width=1, border_color=PALETTE["border"])
        frame.grid(row=row, column=0, padx=32, pady=(0, 12), sticky="ew")
        frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(frame, text=title, text_color=PALETTE["muted"],
                     font=(FONT_FAMILY, 10, "bold"), anchor="w").grid(
            row=0, column=0, padx=16, pady=(12, 6), sticky="w")
        for i, (label, var) in enumerate(options):
            ctk.CTkCheckBox(frame, text=label, variable=var, fg_color=PALETTE["accent"],
                            text_color=PALETTE["text"], font=(FONT_FAMILY, 12)).grid(
                row=1 + i, column=0, padx=16, pady=(4, 6), sticky="w")
        return frame

    def _entry(self, parent, label, placeholder, row):
        ctk.CTkLabel(parent, text=label, text_color=PALETTE["muted"],
                     font=(FONT_FAMILY, 11), anchor="w").grid(row=row * 2, column=0, pady=(8, 4), sticky="w")
        entry = ctk.CTkEntry(parent, placeholder_text=placeholder, height=34, corner_radius=10,
                             fg_color=PALETTE["panel_2"], border_color=PALETTE["border"],
                             text_color=PALETTE["text"], placeholder_text_color=PALETTE["muted"],
                             font=(FONT_FAMILY, 12))
        entry.grid(row=row * 2 + 1, column=0, sticky="ew")
        return entry

    def _menu(self, parent, values, variable):
        return ctk.CTkOptionMenu(parent, values=values, variable=variable, width=130, height=30,
                                 corner_radius=8, fg_color=PALETTE["panel_2"], button_color=PALETTE["accent"],
                                 text_color=PALETTE["text"], dropdown_fg_color=PALETTE["panel_2"],
                                 font=(FONT_FAMILY, 11))

    # ------------------------------------------------------------------- logic

    def _toggle_nms(self):
        if self.nms_var.get():
            self.nms_panel.grid()
        else:
            self.nms_panel.grid_remove()
        self._set_status("NMS enabled" if self.nms_var.get() else "NMS disabled")

    def _fetch_gradle(self):
        try:
            self.gradle_results.put(fetch_versions())
        except Exception:
            self.gradle_results.put(None)

    def _poll_gradle(self):
        try:
            versions = self.gradle_results.get_nowait()
        except queue.Empty:
            self.after(100, self._poll_gradle)
            return
        if versions:
            self.gradle_menu.configure(values=versions)
            self._set_status(f"Gradle updated — latest stable: {versions[0]}")
        else:
            self._set_status("Gradle: offline list; type a version manually if needed.")

    def _choose_output(self):
        folder = filedialog.askdirectory(title="Select output folder")
        if folder:
            self.output_dir = Path(folder)
            self.output_label.configure(text=str(self.output_dir), text_color=PALETTE["text"])
            self._set_status(f"Output: {self.output_dir}")

    def _build_config(self) -> Optional[ProjectConfig]:
        platforms = []
        if self.bukkit_var.get():
            platforms.append(BUKKIT)
        if self.velocity_var.get():
            platforms.append(VELOCITY)
        if not platforms:
            messagebox.showwarning("MC Builder", "Select at least one platform (Paper/Bukkit or Velocity).")
            return None

        nms_versions = [v for v, var in self.nms_vars.items() if var.get()]
        if self.nms_var.get() and not nms_versions:
            if not messagebox.askyesno(
                "MC Builder",
                "NMS is enabled but no version is selected.\n"
                "Generate only the abstraction (nms-api, nms-loader, nms-paper-modern)?",
            ):
                return None

        return ProjectConfig(
            name=sanitize(self.name_entry.get() or "MyPlugin"),
            group=self.group_entry.get().strip() or "com.example",
            version=self.version_entry.get().strip() or "1.0.0",
            description=self.desc_entry.get().strip(),
            java_version=self.java_var.get(),
            gradle_version=self.gradle_var.get(),
            platforms=platforms,
            include_api=self.api_var.get(),
            include_common=self.common_var.get() and self.api_var.get(),
            include_nms=self.nms_var.get(),
            nms_versions=nms_versions,
        )

    def _generate(self):
        if not self.output_dir:
            messagebox.showwarning("MC Builder", "Select an output folder first.")
            return
        config = self._build_config()
        if not config:
            return

        target = self.output_dir / config.name
        if target.exists() and not messagebox.askyesno(
            "MC Builder", f"Folder '{config.name}' already exists at:\n{self.output_dir}\n\nOverwrite?"
        ):
            return

        self._set_status("Generating project…")
        self.generate_btn.configure(state="disabled")

        def work():
            try:
                ProjectGenerator(config, self.nms_data, self.template_dir).generate(self.output_dir)
                self.after(0, lambda: self._on_success(target))
            except Exception as e:
                self.after(0, lambda err=e: self._on_error(err))

        threading.Thread(target=work, daemon=True).start()

    def _on_success(self, target: Path):
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
    App().mainloop()


if __name__ == "__main__":
    main()
