"""Project generation logic (Aurora-style multi-platform template)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .gradle_versions import DEFAULT_GRADLE

BUKKIT = "bukkit"
VELOCITY = "velocity"


@dataclass
class ProjectConfig:
    name: str
    group: str
    version: str = "1.0.0"
    description: str = ""
    java_version: str = "21"
    gradle_version: str = DEFAULT_GRADLE
    platforms: list[str] = field(default_factory=lambda: [BUKKIT])
    include_api: bool = True
    include_common: bool = True
    include_nms: bool = False
    nms_versions: list[str] = field(default_factory=list)

    @property
    def root(self) -> str:
        return self.name

    @property
    def slug(self) -> str:
        s = re.sub(r"[^a-z0-9]", "", self.name.lower())
        return s or "plugin"

    @property
    def base_package(self) -> str:
        return f"{self.group}.{self.slug}"

    @property
    def class_prefix(self) -> str:
        parts = re.split(r"[^A-Za-z0-9]+", self.name)
        return "".join(p[:1].upper() + p[1:] for p in parts if p) or "Plugin"

    def module(self, *parts: str) -> str:
        return f"{self.base_package}.{'.'.join(parts)}"


def sanitize(name: str) -> str:
    """Sanitize a name for filesystem use."""
    name = name.strip()
    name = re.sub(r"[^\w\-.]", "-", name)
    name = re.sub(r"-+", "-", name)
    return name.strip("-") or "project"


class NmsData:
    """Loads the NMS version catalogue."""

    def __init__(self, data_path: Path):
        self.data = {}
        if data_path.exists():
            self.data = json.loads(data_path.read_text(encoding="utf-8"))

    def versions(self) -> list[str]:
        return list(self.data.keys())

    def info(self, version: str) -> dict:
        return self.data.get(version, {})


class ProjectGenerator:
    """Generates the multi-platform Gradle project on disk."""

    def __init__(self, config: ProjectConfig, nms_data: NmsData, template_dir: Path):
        self.config = config
        self.nms = nms_data
        self.template_dir = template_dir

    # ------------------------------------------------------------------ public

    def generate(self, output_dir: Path) -> None:
        if not re.fullmatch(r"\d+\.\d+(?:\.\d+)?", self.config.gradle_version):
            raise ValueError("Versione Gradle non valida: usa una release stabile, es. 9.8.0")
        root = output_dir / self.config.name
        root.mkdir(parents=True, exist_ok=True)

        self._write(root / "settings.gradle", self._render_settings())
        self._write(root / "build.gradle", self._render_root_build())
        self._write(root / "gradle.properties", self._render_gradle_props())
        self._write(root / ".gitignore", self._read(".gitignore"))
        self._write(root / "README.md", self._render_readme())
        self._write(root / "build.sh", self._read("build.sh"))
        self._chmod_exec(root / "build.sh")
        self._write_wrapper(root)

        self._generate_build_logic(root)
        if self.config.include_api:
            self._generate_api(root)
        if self.config.include_common:
            self._generate_common(root)
        for platform in self.config.platforms:
            if platform == BUKKIT:
                self._generate_bukkit(root)
            elif platform == VELOCITY:
                self._generate_velocity(root)
        if self.config.include_nms:
            self._generate_nms(root)

    # ------------------------------------------------------------- root files

    def _render_settings(self) -> str:
        cfg = self.config
        lines = [f"rootProject.name = '{cfg.name}'", "", "include 'buildLogic'"]
        if cfg.include_api:
            lines.append("include 'api'")
        if cfg.include_common:
            lines.append("include 'common'")
        for platform in cfg.platforms:
            lines.append(f"include '{platform}'")
        if cfg.include_nms:
            lines += ["", "// NMS modules"]
            lines.append("include 'nms:nms-api'")
            lines.append("include 'nms:nms-loader'")
            lines.append("include 'nms:nms-paper-modern'")
            lines.append("")
            lines.append("// Version-specific NMS modules require Spigot BuildTools JARs in")
            lines.append("// each module's lib/ folder. Uncomment modules you have built.")
            for version in cfg.nms_versions:
                mc = self.nms.info(version).get("mc", "?")
                lines.append(f"include 'nms:nms-{version}'  // {mc}")
        return "\n".join(lines) + "\n"

    def _render_root_build(self) -> str:
        cfg = self.config
        platform_projects = ", ".join(f"':{p}'" for p in cfg.platforms)
        return f"""subprojects {{
    apply plugin: 'java'

    group = rootProject.group
    version = rootProject.version

    repositories {{
        mavenLocal()
        mavenCentral()
        maven {{ url = 'https://repo.papermc.io/repository/maven-public/' }}
        maven {{ url = 'https://hub.spigotmc.org/nexus/content/repositories/snapshots/' }}
        maven {{ url = 'https://jitpack.io' }}
    }}

    dependencies {{
        compileOnly 'org.jetbrains:annotations:{self._versions()['annotations']}'
    }}

    java {{
        toolchain.languageVersion.set(JavaLanguageVersion.of({cfg.java_version}))
    }}

    tasks.withType(JavaCompile).configureEach {{
        options.encoding = 'UTF-8'
    }}
}}

// Unified jar is produced by :buildLogic (see buildLogic/build.gradle).
// Platform modules: {platform_projects}
"""

    def _render_gradle_props(self) -> str:
        v = self._versions()
        return (
            "# Project\n"
            f"group={self.config.group}\n"
            f"version={self.config.version}\n\n"
            "# Dependency versions\n"
            f"paperVersion={v['paper']}\n"
            f"velocityVersion={v['velocity']}\n"
            f"annotationsVersion={v['annotations']}\n"
            f"lombokVersion={v['lombok']}\n"
            f"junitVersion={v['junit']}\n"
        )

    def _render_readme(self) -> str:
        cfg = self.config
        modules = []
        if cfg.include_api:
            modules.append("- `api` — interfaces and public API")
        if cfg.include_common:
            modules.append("- `common` — shared implementations")
        if BUKKIT in cfg.platforms:
            modules.append("- `bukkit` — Paper/Bukkit plugin")
        if VELOCITY in cfg.platforms:
            modules.append("- `velocity` — Velocity proxy plugin")
        if cfg.include_nms:
            modules.append("- `nms/` — version-agnostic NMS abstraction + per-version modules")
        modules.append("- `buildLogic` — aggregates every module into a single unified jar")
        body = "\n".join(modules)
        nms_note = ""
        if cfg.include_nms and cfg.nms_versions:
            nms_note = (
                "\n## NMS BuildTools\n\n"
                "Version-specific `nms-v*` modules compile against Spigot/Paper jars you must\n"
                "generate with [BuildTools](https://www.spigotmc.org/wiki/buildtools/) and place in\n"
                "`nms/<module>/lib/`. Modules without their jars are commented out in\n"
                "`settings.gradle`.\n"
            )
        return (
            f"# {cfg.name}\n\n"
            f"{cfg.description}\n\n"
            f"**Group:** `{cfg.group}` · **Version:** `{cfg.version}`\n\n"
            f"## Modules\n\n{body}\n"
            f"{nms_note}\n"
            "## Build\n\n"
            "```bash\n./gradlew build\n# Unified jar: buildLogic/build/libs/\n```\n"
        )

    # --------------------------------------------------------------- buildLogic

    def _generate_build_logic(self, root: Path) -> None:
        bl = root / "buildLogic"
        deps = []
        if self.config.include_api:
            deps.append("    implementation project(':api')")
        if self.config.include_common:
            deps.append("    implementation project(':common')")
        for platform in self.config.platforms:
            deps.append(f"    implementation project(':{platform}')")
        if self.config.include_nms:
            deps.append("    implementation project(':nms:nms-api')")
            deps.append("    implementation project(':nms:nms-loader')")
            deps.append("    implementation project(':nms:nms-paper-modern')")
            for version in self.config.nms_versions:
                deps.append(f"    implementation project(':nms:nms-{version}')")
        content = self._read("buildLogic/build.gradle").replace("{dependencies}", "\n".join(deps))
        self._write(bl / "build.gradle", content)

    # --------------------------------------------------------------------- api

    def _generate_api(self, root: Path) -> None:
        cfg = self.config
        pkg = cfg.module("api")
        deps = [
            "    compileOnly 'org.jetbrains:annotations:26.0.2-1'",
        ]
        self._write(root / "api" / "build.gradle",
                    self._read("api/build.gradle").replace("{dependencies}", "\n".join(deps)))
        self._write(root / "api" / "src" / "main" / "java" / self._pkg_path(pkg) / "AuroraApi.java",
                    self._java_api(pkg))
        self._write(root / "api" / "src" / "main" / "java" / self._pkg_path(pkg) / "PluginAdapter.java",
                    self._java_plugin_adapter(pkg))

    # ------------------------------------------------------------------ common

    def _generate_common(self, root: Path) -> None:
        cfg = self.config
        pkg = cfg.module("common")
        deps = [
            "    api project(':api')",
            "",
            "    compileOnly 'org.jetbrains:annotations:26.0.2-1'",
            "    compileOnly 'org.projectlombok:lombok:1.18.46'",
            "    annotationProcessor 'org.projectlombok:lombok:1.18.46'",
        ]
        self._write(root / "common" / "build.gradle",
                    self._read("common/build.gradle").replace("{dependencies}", "\n".join(deps)))
        self._write(root / "common" / "src" / "main" / "java" / self._pkg_path(pkg) / "core" / f"{cfg.class_prefix}ApiImpl.java",
                    self._java_api_impl(pkg + ".core"))

    # ------------------------------------------------------------------ bukkit

    def _generate_bukkit(self, root: Path) -> None:
        cfg = self.config
        pkg = cfg.module("bukkit")
        deps = ["    compileOnly 'io.papermc.paper:paper-api:' + rootProject.paperVersion"]
        if cfg.include_api:
            deps.insert(0, "    implementation project(':api')")
        if cfg.include_common:
            deps.insert(1, "    implementation project(':common')")
        if cfg.include_nms:
            deps.append("    implementation project(':nms:nms-api')")
            deps.append("    implementation project(':nms:nms-loader')")
        self._write(root / "bukkit" / "build.gradle",
                    self._read("bukkit/build.gradle").replace("{dependencies}", "\n".join(deps)))
        self._write(root / "bukkit" / "src" / "main" / "java" / self._pkg_path(pkg) / f"{cfg.class_prefix}.java",
                    self._java_bukkit_main(pkg))
        self._write(root / "bukkit" / "src" / "main" / "resources" / "plugin.yml",
                    self._render_plugin_yml())

    def _render_plugin_yml(self) -> str:
        cfg = self.config
        return (
            f"name: {cfg.name}\n"
            f"version: ${{version}}\n"
            f"main: {cfg.base_package}.bukkit.{cfg.class_prefix}\n"
            f"api: '{self._api_version()}'\n"
            f"description: {cfg.description or cfg.name}\n"
            f"authors: [ {cfg.group} ]\n"
        )

    # ---------------------------------------------------------------- velocity

    def _generate_velocity(self, root: Path) -> None:
        cfg = self.config
        pkg = cfg.module("velocity")
        deps = [
            "    compileOnly \"com.velocitypowered:velocity-api:${rootProject.velocityVersion}\"",
            "    annotationProcessor \"com.velocitypowered:velocity-api:${rootProject.velocityVersion}\"",
        ]
        if cfg.include_api:
            deps.insert(0, "    implementation project(':api')")
        if cfg.include_common:
            deps.insert(1, "    implementation project(':common')")
        if cfg.include_nms:
            deps.append("    implementation project(':nms:nms-api')")
        self._write(root / "velocity" / "build.gradle",
                    self._read("velocity/build.gradle").replace("{dependencies}", "\n".join(deps)))
        self._write(root / "velocity" / "src" / "main" / "java" / self._pkg_path(pkg) / f"{cfg.class_prefix}Velocity.java",
                    self._java_velocity_main(pkg))

    # --------------------------------------------------------------------- nms

    def _generate_nms(self, root: Path) -> None:
        cfg = self.config
        nms = root / "nms"
        base = cfg.module("nms")
        self._write(nms / "nms-api" / "build.gradle", self._read("nms/nms-api/build.gradle"))
        self._write(nms / "nms-api" / "src" / "main" / "java" / self._pkg_path(base) / "Nms.java",
                    self._java_nms_access(base))
        self._write(nms / "nms-api" / "src" / "main" / "java" / self._pkg_path(base) / "NmsHandler.java",
                    self._java_nms_handler(base))
        self._write(nms / "nms-api" / "src" / "main" / "java" / self._pkg_path(base) / "NmsProvider.java",
                    self._java_nms_provider(base))

        self._write(nms / "nms-loader" / "build.gradle", self._read("nms/nms-loader/build.gradle"))
        self._write(nms / "nms-loader" / "src" / "main" / "java" / self._pkg_path(base + ".loader") / "NmsLoader.java",
                    self._java_nms_loader(base))

        self._write(nms / "nms-paper-modern" / "build.gradle", self._read("nms/nms-paper-modern/build.gradle"))
        self._write(nms / "nms-paper-modern" / "src" / "main" / "java" / self._pkg_path(base + ".paper_modern") / "NmsHandlerImpl.java",
                    self._java_nms_impl(base + ".paper_modern", "paper-modern"))
        self._write(nms / "nms-paper-modern" / "src" / "main" / "resources" / "META-INF" / "services" / f"{base}.NmsProvider",
                    base + ".paper_modern.NmsHandlerImpl$Provider\n")

        for version in cfg.nms_versions:
            info = self.nms.info(version)
            mod = nms / f"nms-{version}"
            self._write(mod / "build.gradle", self._render_nms_version_build(version, info))
            self._write(mod / "src" / "main" / "java" / self._pkg_path(base + f".{version}") / "NmsHandlerImpl.java",
                        self._java_nms_impl(base + f".{version}", version))
            self._write(mod / "src" / "main" / "resources" / "META-INF" / "services" / f"{base}.NmsProvider",
                        base + f".{version}.NmsHandlerImpl$Provider\n")

    def _render_nms_version_build(self, version: str, info: dict) -> str:
        toolchain = info.get("java", "21")
        mc = info.get("mc", version)
        return self._read("nms/nms-v/build.gradle").replace("{java}", str(toolchain)).replace("{mc}", mc)

    # ------------------------------------------------------------ java sources

    def _java_api(self, pkg: str) -> str:
        return (
            f"package {pkg};\n\n"
            "import java.util.concurrent.CompletableFuture;\n\n"
            "/** Public API surface shared across platforms. */\n"
            "public interface AuroraApi {\n\n"
            "    /** @return the running version string. */\n"
            "    String version();\n\n"
            "    /** @return a future completing once the platform is ready. */\n"
            "    CompletableFuture<Void> ready();\n"
            "}\n"
        )

    def _java_plugin_adapter(self, pkg: str) -> str:
        return (
            f"package {pkg};\n\n"
            "import java.io.File;\n"
            "import java.util.logging.Logger;\n\n"
            "/** Minimal, platform-agnostic adapter passed from a platform into the core. */\n"
            "public interface PluginAdapter {\n"
            "    File getDataFolder();\n"
            "    Logger getLogger();\n"
            "    String getPlatform();\n"
            "}\n"
        )

    def _java_api_impl(self, pkg: str) -> str:
        cfg = self.config
        iface = cfg.module("api") + ".AuroraApi"
        return (
            f"package {pkg};\n\n"
            "import java.util.concurrent.CompletableFuture;\n"
            f"import {iface};\n\n"
            "/** Default implementation of the shared API. */\n"
            "public final class " + cfg.class_prefix + "ApiImpl implements AuroraApi {\n\n"
            "    private final String version;\n\n"
            "    public " + cfg.class_prefix + "ApiImpl(String version) {\n"
            "        this.version = version;\n"
            "    }\n\n"
            "    @Override\n"
            "    public String version() {\n"
            "        return version;\n"
            "    }\n\n"
            "    @Override\n"
            "    public CompletableFuture<Void> ready() {\n"
            "        return CompletableFuture.completedFuture(null);\n"
            "    }\n"
            "}\n"
        )

    def _java_bukkit_main(self, pkg: str) -> str:
        cfg = self.config
        return (
            f"package {pkg};\n\n"
            "import org.bukkit.plugin.java.JavaPlugin;\n\n"
            f"public final class {cfg.class_prefix} extends JavaPlugin {{\n\n"
            "    @Override\n"
            "    public void onEnable() {\n"
            f"        getLogger().info(\"{cfg.name} enabled.\");\n"
            "    }\n\n"
            "    @Override\n"
            "    public void onDisable() {\n"
            f"        getLogger().info(\"{cfg.name} disabled.\");\n"
            "    }\n"
            "}\n"
        )

    def _java_velocity_main(self, pkg: str) -> str:
        cfg = self.config
        plugin_id = re.sub(r"[^a-z0-9_-]", "-", cfg.slug)
        return (
            f"package {pkg};\n\n"
            "import com.google.inject.Inject;\n"
            "import com.velocitypowered.api.event.Subscribe;\n"
            "import com.velocitypowered.api.event.proxy.ProxyInitializeEvent;\n"
            "import com.velocitypowered.api.plugin.Plugin;\n"
            "import com.velocitypowered.api.proxy.ProxyServer;\n"
            "import org.slf4j.Logger;\n\n"
            f"@Plugin(id = \"{plugin_id}\")\n"
            f"public final class {cfg.class_prefix}Velocity {{\n\n"
            "    private final ProxyServer server;\n"
            "    private final Logger logger;\n\n"
            "    @Inject\n"
            f"    public {cfg.class_prefix}Velocity(ProxyServer server, Logger logger) {{\n"
            "        this.server = server;\n"
            "        this.logger = logger;\n"
            "    }\n\n"
            "    @Subscribe\n"
            "    public void onProxyInitialize(ProxyInitializeEvent event) {\n"
            f"        logger.info(\"{cfg.name} enabled.\");\n"
            "    }\n"
            "}\n"
        )

    def _java_nms_access(self, pkg: str) -> str:
        return (
            f"package {pkg};\n\n"
            "/** Global access point for the current NMS handler. */\n"
            "public final class Nms {\n\n"
            "    private static NmsHandler handler;\n\n"
            "    private Nms() {}\n\n"
            "    public static void init(NmsHandler handler) {\n"
            "        Nms.handler = handler;\n"
            "    }\n\n"
            "    public static NmsHandler get() {\n"
            "        if (handler == null) {\n"
            "            throw new IllegalStateException(\"Nms not initialised. Call Nms.init() first.\");\n"
            "        }\n"
            "        return handler;\n"
            "    }\n\n"
            "    public static boolean isInitialized() {\n"
            "        return handler != null;\n"
            "    }\n\n"
            "    public static void reset() {\n"
            "        handler = null;\n"
            "    }\n"
            "}\n"
        )

    def _java_nms_handler(self, pkg: str) -> str:
        return (
            f"package {pkg};\n\n"
            "import org.bukkit.entity.Player;\n\n"
            "/** Version-agnostic NMS operations. Implemented once per server version. */\n"
            "public interface NmsHandler {\n\n"
            "    /** @return the NMS version handled (e.g. \"v1_21_R3\"). */\n"
            "    String getNmsVersion();\n\n"
            "    /** Send an action bar message to a player. */\n"
            "    void sendActionBar(Player player, String message);\n\n"
            "    /** @return the player's ping in milliseconds. */\n"
            "    int getPing(Player player);\n"
            "}\n"
        )

    def _java_nms_provider(self, pkg: str) -> str:
        return (
            f"package {pkg};\n\n"
            "/** ServiceLoader provider; one per NMS implementation. */\n"
            "public interface NmsProvider {\n\n"
            "    /** @return the supported NMS version (e.g. \"v1_21_R3\"). */\n"
            "    String version();\n\n"
            "    /** Create the handler instance. */\n"
            "    NmsHandler create();\n"
            "}\n"
        )

    def _java_nms_loader(self, pkg: str) -> str:
        return (
            f"package {pkg};\n\n"
            "import java.util.ServiceLoader;\n"
            "import java.util.logging.Level;\n"
            "import java.util.logging.Logger;\n\n"
            f"import {self.config.module('nms')}.Nms;\n"
            f"import {self.config.module('nms')}.NmsHandler;\n"
            f"import {self.config.module('nms')}.NmsProvider;\n\n"
            "/** Detects the server version and loads the matching NMS handler. */\n"
            "public final class NmsLoader {\n\n"
            "    private static final Logger LOGGER = Logger.getLogger(\"NMS-Loader\");\n\n"
            "    private NmsLoader() {}\n\n"
            "    public static boolean load() {\n"
            "        String version = detectVersion();\n"
            "        LOGGER.info(\"Detected NMS version: \" + version);\n"
            "        try {\n"
            "            for (NmsProvider provider : ServiceLoader.load(NmsProvider.class)) {\n"
            "                if (provider.version().equals(version)) {\n"
            "                    Nms.init(provider.create());\n"
            "                    LOGGER.info(\"Loaded NMS handler: \" + version);\n"
            "                    return true;\n"
            "                }\n"
            "            }\n"
            "        } catch (Throwable t) {\n"
            "            LOGGER.log(Level.WARNING, \"NMS ServiceLoader failed\", t);\n"
            "        }\n"
            "        LOGGER.warning(\"No NMS handler found for version: \" + version);\n"
            "        return false;\n"
            "    }\n\n"
            "    public static String detectVersion() {\n"
            "        try {\n"
            "            String pkg = org.bukkit.Bukkit.getServer().getClass().getPackage().getName();\n"
            "            String[] parts = pkg.split(\"\\\\.\");\n"
            "            if (parts.length >= 4 && parts[3].startsWith(\"v\")) {\n"
            "                return parts[3];\n"
            "            }\n"
            "        } catch (Throwable ignored) {\n"
            "            // fall through to modern detection\n"
            "        }\n"
            "        return \"paper-modern\";\n"
            "    }\n"
            "}\n"
        )

    def _java_nms_impl(self, pkg: str, version: str) -> str:
        ns = self.config.module("nms")
        return (
            f"package {pkg};\n\n"
            "import org.bukkit.entity.Player;\n\n"
            f"import {ns}.NmsHandler;\n"
            f"import {ns}.NmsProvider;\n\n"
            f"/** NMS handler for {version}. Add version-specific code here. */\n"
            "public class NmsHandlerImpl implements NmsHandler {\n\n"
            "    @Override\n"
            "    public String getNmsVersion() {\n"
            f"        return \"{version}\";\n"
            "    }\n\n"
            "    @Override\n"
            "    public void sendActionBar(Player player, String message) {\n"
            "        player.sendActionBar(message);\n"
            "    }\n\n"
            "    @Override\n"
            "    public int getPing(Player player) {\n"
            "        return player.getPing();\n"
            "    }\n\n"
            "    public static class Provider implements NmsProvider {\n"
            "        @Override\n"
            "        public String version() {\n"
            f"            return \"{version}\";\n"
            "        }\n\n"
            "        @Override\n"
            "        public NmsHandler create() {\n"
            "            return new NmsHandlerImpl();\n"
            "        }\n"
            "    }\n"
            "}\n"
        )

    # ------------------------------------------------------------------ helpers

    def _versions(self) -> dict:
        return {
            "paper": "1.21.4-R0.1-SNAPSHOT",
            "velocity": "3.4.0",
            "annotations": "26.0.2-1",
            "lombok": "1.18.46",
            "junit": "5.14.4",
        }

    def _api_version(self) -> str:
        return "1.21"

    def _pkg_path(self, pkg: str) -> Path:
        return Path(*pkg.split("."))

    def _write_wrapper(self, root: Path) -> None:
        gradle_dir = root / "gradle" / "wrapper"
        gradle_dir.mkdir(parents=True, exist_ok=True)
        props = self._read("gradle-wrapper.properties").replace("{gradle_version}", self.config.gradle_version)
        self._write(gradle_dir / "gradle-wrapper.properties", props)
        self._copy_binary(gradle_dir / "gradle-wrapper.jar", self.template_dir / "gradle-wrapper.jar")
        self._write(root / "gradlew", self._read("gradlew"))
        self._write(root / "gradlew.bat", self._read("gradlew.bat"))
        self._chmod_exec(root / "gradlew")

    def _read(self, name: str) -> str:
        return (self.template_dir / name).read_text(encoding="utf-8")

    def _write(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _copy_binary(self, dest: Path, src: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())

    def _chmod_exec(self, path: Path) -> None:
        try:
            path.chmod(0o755)
        except OSError:
            pass
