import json
import tempfile
import unittest
from pathlib import Path

from mcbuilder.generator import Module, ProjectConfig, ProjectGenerator, ServerData
from mcbuilder.gradle_versions import stable_versions


RESOURCES = Path(__file__).parent / "mcbuilder"


def generate(tmp, modules, include_api, gradle_version="9.8.0"):
    data = ServerData(RESOURCES / "assets" / "server_data.json")
    config = ProjectConfig(
        name="example",
        group="com.example",
        version="1.0.0",
        modules=modules,
        include_api=include_api,
        gradle_version=gradle_version,
    )
    ProjectGenerator(config, data, RESOURCES / "templates").generate(Path(tmp))
    return config, Path(tmp) / config.name


class GradleVersionTests(unittest.TestCase):
    def test_release_filter_and_order(self):
        releases = [{"version": v} for v in ("9.8.0", "8.14.5", "9.10.0", "9.9-rc-1", "9.9-SNAPSHOT")]
        releases.append({"version": "10.0.0", "broken": True})
        self.assertEqual(stable_versions(releases), ["9.10.0", "9.8.0", "8.14.5"])


class ServerDataTests(unittest.TestCase):
    def test_every_version_resolves_and_has_platform(self):
        data = ServerData(RESOURCES / "assets" / "server_data.json")
        self.assertIn("platform", data.servers["paper"])
        for name in data.server_names():
            platform = data.platform(name)
            self.assertIn(platform, {"bukkit", "velocity", "bungee"})
            for version in data.versions(name):
                deps = data.dependencies(name, version)
                self.assertTrue(any("compileOnly" in d for d in deps), f"{name} {version}")

    def test_java_version_per_minecraft_version(self):
        data = ServerData(RESOURCES / "assets" / "server_data.json")
        self.assertEqual(data.java_version("paper", "1.21.4"), "21")
        self.assertEqual(data.java_version("paper", "1.20.4"), "17")
        self.assertEqual(data.java_version("velocity", "3.4.0"), "17")
        self.assertEqual(data.java_version("paper", "9.9.9", default="17"), "17")


class GenerationTests(unittest.TestCase):
    def test_optional_shared_api(self):
        for enabled in (False, True):
            with self.subTest(api=enabled), tempfile.TemporaryDirectory() as tmp:
                config, root = generate(tmp, [Module("paper", "1.20.4"), Module("spigot", "1.20.4")], enabled)
                settings = (root / "settings.gradle.kts").read_text()
                self.assertEqual('include("api")' in settings, enabled)
                self.assertEqual((root / "api").exists(), enabled)
                for module in config.modules:
                    script = (root / module.name / "build.gradle.kts").read_text()
                    self.assertEqual('implementation(project(":api"))' in script, enabled)
                    self.assertIn(f'include("{module.server}-{module.version}")', settings)
                if enabled:
                    self.assertTrue((root / "api/src/main/java/com/example/api/ProjectApi.java").exists())
                    self.assertNotIn("mcbuilder.module", (root / "api/build.gradle.kts").read_text())

    def test_wrapper_files_present_and_pinned(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, root = generate(tmp, [Module("paper", "1.20.4")], False, gradle_version="9.8.0")
            wrapper = (root / "gradle/wrapper/gradle-wrapper.properties").read_text()
            self.assertIn("gradle-9.8.0-bin.zip", wrapper)
            self.assertNotIn("{gradle_version}", wrapper)
            self.assertTrue((root / "gradlew").exists())
            self.assertTrue((root / "gradlew.bat").exists())
            self.assertTrue((root / "gradle/wrapper/gradle-wrapper.jar").exists())

    def test_platform_specific_descriptors(self):
        cases = {
            "paper": ("plugin.yml", "JavaPlugin"),
            "bungeecord": ("bungee.yml", "net.md_5.bungee.api.plugin.Plugin"),
        }
        with tempfile.TemporaryDirectory() as tmp:
            modules = [Module("paper", "1.20.4"), Module("bungeecord", "1.21"), Module("velocity", "3.4.0")]
            _, root = generate(tmp, modules, False)
            for name, (descriptor, base) in cases.items():
                module_dir = next(root.glob(f"{name}-*"))
                self.assertTrue((module_dir / "src/main/resources" / descriptor).exists())
                java_file = next(module_dir.glob("src/main/java/com/example/*Plugin.java"))
                self.assertIn(base, java_file.read_text())
            velocity_dir = next(root.glob("velocity-*"))
            velocity_java = next(velocity_dir.glob("src/main/java/com/example/*Plugin.java"))
            self.assertIn('@Plugin(id = "velocity-3-4-0")', velocity_java.read_text())
            self.assertFalse((velocity_dir / "src/main/resources/velocity-plugin.json").exists())

    def test_velocity_ids_are_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, root = generate(tmp, [Module("velocity", "3.4.0")], False)
            java_file = next(root.glob("velocity-*/src/main/java/com/example/*.java"))
            import re
            match = re.search(r'@Plugin\(id = "([^"]+)"\)', java_file.read_text())
            self.assertIsNotNone(match)
            self.assertRegex(match.group(1), r"^[a-z][a-z0-9_-]*$")


if __name__ == "__main__":
    unittest.main()
