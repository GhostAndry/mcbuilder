import tempfile
import unittest
from pathlib import Path

from mcbuilder.generator import Module, ProjectConfig, ProjectGenerator, ServerData
from mcbuilder.gradle_versions import stable_versions


class SharedApiTests(unittest.TestCase):
    def test_release_filter_and_order(self):
        releases = [{"version": version} for version in ("9.8.0", "8.14.5", "9.10.0", "9.9-rc-1", "9.9-SNAPSHOT")]
        releases.append({"version": "10.0.0", "broken": True})
        self.assertEqual(stable_versions(releases), ["9.10.0", "9.8.0", "8.14.5"])

    def test_optional_shared_api(self):
        resources = Path(__file__).parent / "mcbuilder"
        data = ServerData(resources / "assets" / "server_data.json")
        for enabled in (False, True):
            with self.subTest(api=enabled), tempfile.TemporaryDirectory() as tmp:
                config = ProjectConfig(
                    name="example", group="com.example", version="1.0.0",
                    modules=[Module("paper", "1.20.4"), Module("spigot", "1.20.4")],
                    include_api=enabled,
                    gradle_version="9.8.0" if enabled else "8.14.5",
                )
                ProjectGenerator(config, data, resources / "templates").generate(Path(tmp))
                root = Path(tmp) / config.name
                settings = (root / "settings.gradle.kts").read_text()
                wrapper = (root / "gradle/wrapper/gradle-wrapper.properties").read_text()
                self.assertIn(f"gradle-{config.gradle_version}-bin.zip", wrapper)
                self.assertNotIn("{gradle_version}", wrapper)
                self.assertEqual('include("api")' in settings, enabled)
                self.assertEqual((root / "api").exists(), enabled)
                for module in config.modules:
                    script = (root / module.name / "build.gradle.kts").read_text()
                    self.assertEqual('implementation(project(":api"))' in script, enabled)
                    self.assertIn(f'include("{module.server}-{module.version}")', settings)
                if enabled:
                    script = (root / "api" / "build.gradle.kts").read_text()
                    self.assertIn('`java-library`', script)
                    self.assertNotIn('mcbuilder.module', script)
                    self.assertFalse((root / "api/src/main/resources/plugin.yml").exists())
                    self.assertTrue((root / "api/src/main/java/com/example/api/package-info.java").exists())


if __name__ == "__main__":
    unittest.main()
