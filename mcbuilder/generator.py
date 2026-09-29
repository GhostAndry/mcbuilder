"""Project generation logic."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from .gradle_versions import DEFAULT_GRADLE


@dataclass
class Module:
    server: str
    version: str
    name: str = ""

    def __post_init__(self):
        if not self.name:
            parts = [self.server, self.version]
            self.name = "-".join(parts)

    @property
    def path(self) -> str:
        return self.name


@dataclass
class ProjectConfig:
    name: str
    group: str
    version: str
    description: str = ""
    java_version: str = "17"
    gradle_version: str = DEFAULT_GRADLE
    modules: list[Module] = field(default_factory=list)
    include_api: bool = False

    @property
    def root(self) -> str:
        return self.name


def sanitize(name: str) -> str:
    """Sanitize a name for filesystem use."""
    name = name.strip()
    name = re.sub(r"[^\w\-.]", "-", name)
    name = re.sub(r"-+", "-", name)
    return name.strip("-").lower() or "project"


class ServerData:
    """Loads server software metadata."""

    def __init__(self, data_path: Path):
        self.data_path = data_path
        self.servers: dict = {}
        self._load()

    def _load(self):
        if self.data_path.exists():
            with self.data_path.open("r", encoding="utf-8") as f:
                self.servers = json.load(f)

    def server_names(self) -> list[str]:
        return list(self.servers.keys())

    def display_name(self, key: str) -> str:
        return self.servers.get(key, {}).get("name", key.title())

    def versions(self, key: str) -> list[str]:
        return list(self.servers.get(key, {}).get("versions", {}).keys())

    def resolve_version(self, key: str, label: str) -> str:
        versions = self.servers.get(key, {}).get("versions", {})
        if isinstance(versions, dict):
            return versions.get(label, label)
        return label

    def dependencies(self, key: str, version: str) -> list[str]:
        resolved = self.resolve_version(key, version)
        deps = self.servers.get(key, {}).get("dependencies", [])
        return [d.replace("{version}", resolved) for d in deps]

    def platform(self, key: str) -> str:
        return self.servers.get(key, {}).get("platform", "bukkit")

    def java_version(self, key: str, label: str, default: str = "17") -> str:
        versions = self.servers.get(key, {}).get("java", {})
        if isinstance(versions, dict):
            return versions.get(label, default)
        return default


class ProjectGenerator:
    """Generates the multi-module Gradle project on disk."""

    def __init__(self, config: ProjectConfig, server_data: ServerData, template_dir: Path):
        self.config = config
        self.server_data = server_data
        self.template_dir = template_dir

    def generate(self, output_dir: Path) -> None:
        if not re.fullmatch(r"\d+\.\d+(?:\.\d+)?", self.config.gradle_version):
            raise ValueError("Versione Gradle non valida: usa una release stabile, es. 9.8.0")
        output_dir = output_dir / self.config.name
        output_dir.mkdir(parents=True, exist_ok=True)

        self._write_file(output_dir / "settings.gradle.kts", self._render_settings())
        self._write_file(output_dir / "build.gradle.kts", self._read_template("build.gradle.kts.root"))
        self._write_file(output_dir / ".gitignore", self._read_template(".gitignore"))
        self._write_file(output_dir / "gradle.properties", self._render_gradle_props())
        self._write_file(output_dir / "README.md", self._render_readme())

        gradle_dir = output_dir / "gradle" / "wrapper"
        gradle_dir.mkdir(parents=True, exist_ok=True)
        self._write_file(gradle_dir / "gradle-wrapper.properties", self._read_template("gradle-wrapper.properties").replace("{gradle_version}", self.config.gradle_version))
        self._copy_binary(gradle_dir / "gradle-wrapper.jar", self.template_dir / "gradle-wrapper.jar")
        self._write_file(output_dir / "gradlew", self._read_template("gradlew"))
        self._write_file(output_dir / "gradlew.bat", self._read_template("gradlew.bat"))
        try:
            (output_dir / "gradlew").chmod(0o755)
        except OSError:
            pass

        self._generate_build_logic(output_dir)
        if self.config.include_api:
            self._generate_api(output_dir)
        for module in self.config.modules:
            self._generate_module(output_dir, module)

    def _render_settings(self) -> str:
        includes = "\n".join(f'include("{m.name}")' for m in self.config.modules)
        if self.config.include_api:
            includes = 'include("api")\n' + includes
        template = self._read_template("settings.gradle.kts")
        return template.replace("{project_name}", self.config.name).replace("{module_includes}", includes)

    def _render_gradle_props(self) -> str:
        return (
            f"org.gradle.jvmargs=-Xmx2048M\n"
            f"org.gradle.parallel=true\n"
            f"org.gradle.caching=true\n"
            f"group={self.config.group}\n"
            f"version={self.config.version}\n"
        )

    def _render_readme(self) -> str:
        modules_list = "\n".join(f"- `{m.name}` ({m.server} {m.version})" for m in self.config.modules)
        if self.config.include_api:
            modules_list = "- `api`: shared Java interfaces and contracts, used by every server module.\n" + modules_list
        return (
            f"# {self.config.name}\n\n"
            f"{self.config.description}\n\n"
            f"**Group:** `{self.config.group}` · **Version:** `{self.config.version}`\n\n"
            f"## Modules\n\n{modules_list}\n\n"
            f"## Build\n\n"
            f"```bash\n./gradlew shadowJar\n```\n\n"
            f"Unified JAR: `build/libs/`\n"
        )

    def _generate_build_logic(self, root: Path) -> None:
        bl = root / "buildLogic"
        kotlin_dir = bl / "src" / "main" / "kotlin"

        self._write_file(bl / "settings.gradle.kts", self._read_template("buildLogic/settings.gradle.kts"))
        self._write_file(bl / "build.gradle.kts", self._read_template("buildLogic/build.gradle.kts"))

        for rel in (
            "mcbuilder/module/McModulePlugin.kt",
        ):
            src = self.template_dir / "buildLogic" / "src" / "main" / "kotlin" / rel
            if src.exists():
                self._write_file(kotlin_dir / rel, src.read_text())

    def _generate_api(self, root: Path) -> None:
        self._write_file(root / "api" / "build.gradle.kts", (
            'plugins {\n    `java-library`\n}\n\n'
            'group = rootProject.group\nversion = rootProject.version\n\n'
            'java {\n'
            f'    toolchain.languageVersion.set(JavaLanguageVersion.of({self.config.java_version}))\n'
            '    withSourcesJar()\n}\n'
        ))
        package = self.config.group + ".api"
        package_path = root / "api" / "src" / "main" / "java" / Path(*package.split("."))
        self._write_file(
            package_path / "ProjectApi.java",
            f"package {package};\n\n"
            "import java.util.UUID;\n\n"
            "/** Shared API surface implemented by the server modules. */\n"
            "public interface ProjectApi {\n\n"
            "    /** @return the project name, stable across platforms. */\n"
            "    String projectName();\n\n"
            "    /** @return whether the given player is currently known to the module. */\n"
            "    boolean isKnown(UUID playerId);\n"
            "}\n",
        )

    def _generate_module(self, root: Path, module: Module) -> None:
        mod_dir = root / module.name
        src_main = mod_dir / "src" / "main" / "java"
        src_resources = mod_dir / "src" / "main" / "resources"
        src_main.mkdir(parents=True, exist_ok=True)
        src_resources.mkdir(parents=True, exist_ok=True)

        deps = self.server_data.dependencies(module.server, module.version)
        if self.config.include_api:
            deps.insert(0, 'implementation(project(":api"))')
        deps_str = "\n    ".join(deps) if deps else ""

        template = self._read_template("build.gradle.kts.module")
        content = (
            template
            .replace("{dependencies}", deps_str)
            .replace("{java_version}", self.server_data.java_version(module.server, module.version, self.config.java_version))
        )
        self._write_file(mod_dir / "build.gradle.kts", content)

        platform = self.server_data.platform(module.server)
        package = self.config.group
        class_name = self._class_name(module.name)

        if platform == "velocity":
            pass
        elif platform == "bungee":
            self._write_file(src_resources / "bungee.yml", self._render_bungee_yml(module, class_name))
        else:
            self._write_file(src_resources / "plugin.yml", self._render_plugin_yml(module, class_name))

        package_path = mod_dir / "src" / "main" / "java" / Path(*package.split("."))
        package_path.mkdir(parents=True, exist_ok=True)
        self._write_file(
            package_path / f"{class_name}.java",
            self._render_main_class(class_name, module, platform),
        )

    def _render_plugin_yml(self, module: Module, class_name: str) -> str:
        return (
            f"name: {module.name}\n"
            f"version: '{self.config.version}'\n"
            f"main: {self.config.group}.{class_name}\n"
            f"description: {self.config.description or module.name}\n"
            f"api-version: '{module.version.split('-')[0]}'\n"
            f"author: {self.config.group}\n"
        )

    def _render_bungee_yml(self, module: Module, class_name: str) -> str:
        return (
            f"name: {module.name}\n"
            f"version: '{self.config.version}'\n"
            f"main: {self.config.group}.{class_name}\n"
            f"description: {self.config.description or module.name}\n"
            f"author: {self.config.group}\n"
        )

    def _render_main_class(self, class_name: str, module: Module, platform: str) -> str:
        pkg = self.config.group
        if platform == "velocity":
            plugin_id = re.sub(r"[^a-z0-9_-]", "-", module.name.lower())
            return (
                f"package {pkg};\n\n"
                f"import com.google.inject.Inject;\n"
                f"import com.velocitypowered.api.event.Subscribe;\n"
                f"import com.velocitypowered.api.event.proxy.ProxyInitializeEvent;\n"
                f"import com.velocitypowered.api.plugin.Plugin;\n"
                f"import com.velocitypowered.api.proxy.ProxyServer;\n"
                f"import org.slf4j.Logger;\n\n"
                f"@Plugin(id = \"{plugin_id}\")\n"
                f"public final class {class_name} {{\n\n"
                f"    private final ProxyServer server;\n"
                f"    private final Logger logger;\n\n"
                f"    @Inject\n"
                f"    public {class_name}(ProxyServer server, Logger logger) {{\n"
                f"        this.server = server;\n"
                f"        this.logger = logger;\n"
                f"    }}\n\n"
                f"    @Subscribe\n"
                f"    public void onProxyInitialize(ProxyInitializeEvent event) {{\n"
                f"        logger.info(\"{module.name} enabled.\");\n"
                f"    }}\n"
                f"}}\n"
            )
        if platform == "bungee":
            return (
                f"package {pkg};\n\n"
                f"import net.md_5.bungee.api.plugin.Plugin;\n\n"
                f"public final class {class_name} extends Plugin {{\n"
                f"    @Override\n"
                f"    public void onEnable() {{\n"
                f"        getLogger().info(\"{module.name} enabled.\");\n"
                f"    }}\n"
                f"}}\n"
            )
        return (
            f"package {pkg};\n\n"
            f"import org.bukkit.plugin.java.JavaPlugin;\n\n"
            f"public final class {class_name} extends JavaPlugin {{\n"
            f"    @Override\n"
            f"    public void onEnable() {{\n"
            f"        getLogger().info(\"{module.name} enabled.\");\n"
            f"    }}\n\n"
            f"    @Override\n"
            f"    public void onDisable() {{\n"
            f"        getLogger().info(\"{module.name} disabled.\");\n"
            f"    }}\n"
            f"}}\n"
        )

    def _class_name(self, module_name: str) -> str:
        parts = re.split(r"[-_.]", module_name)
        parts = [p for p in parts if p]
        return "".join(p.title() for p in parts) + "Plugin"

    def _read_template(self, name: str) -> str:
        return (self.template_dir / name).read_text(encoding="utf-8")

    def _write_file(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _copy_binary(self, dest: Path, src: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())
