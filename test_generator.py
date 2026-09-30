import tempfile
import unittest
from pathlib import Path

from mcbuilder.generator import ProjectConfig, ProjectGenerator, NmsData
from mcbuilder.gradle_versions import stable_versions

RESOURCES = Path(__file__).parent / "mcbuilder"


def generate(tmp, **kwargs):
    nms = NmsData(RESOURCES / "assets" / "nms_data.json")
    cfg = ProjectConfig(name="MyCore", group="com.example", version="1.0.0",
                        gradle_version="9.8.0", **kwargs)
    ProjectGenerator(cfg, nms, RESOURCES / "templates").generate(Path(tmp))
    return cfg, Path(tmp) / cfg.name


class GradleVersionTests(unittest.TestCase):
    def test_release_filter_and_order(self):
        releases = [{"version": v} for v in ("9.8.0", "8.14.5", "9.10.0", "9.9-rc-1", "9.9-SNAPSHOT")]
        releases.append({"version": "10.0.0", "broken": True})
        self.assertEqual(stable_versions(releases), ["9.10.0", "9.8.0", "8.14.5"])


class GenerationTests(unittest.TestCase):
    def test_multiplatform_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg, root = generate(tmp, platforms=["bukkit", "velocity"],
                                 include_api=True, include_common=True)
            settings = (root / "settings.gradle").read_text()
            for token in ("include 'buildLogic'", "include 'api'", "include 'common'",
                          "include 'bukkit'", "include 'velocity'"):
                self.assertIn(token, settings)
            self.assertTrue((root / "buildLogic/build.gradle").exists())
            self.assertTrue((root / "api/src/main/java/com/example/mycore/api/AuroraApi.java").exists())
            self.assertTrue((root / "common/src/main/java/com/example/mycore/common/core/MyCoreApiImpl.java").exists())
            self.assertTrue((root / "bukkit/src/main/resources/plugin.yml").exists())
            self.assertTrue((root / "velocity/src/main/java/com/example/mycore/velocity/MyCoreVelocity.java").exists())

    def test_common_requires_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg, root = generate(tmp, platforms=["bukkit"], include_api=False, include_common=False)
            settings = (root / "settings.gradle").read_text()
            self.assertNotIn("include 'api'", settings)
            self.assertNotIn("include 'common'", settings)
            self.assertFalse((root / "api").exists())

    def test_nms_scaffold(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg, root = generate(tmp, platforms=["bukkit"], include_nms=True,
                                 nms_versions=["v1_20_R3", "v1_21_R3"])
            settings = (root / "settings.gradle").read_text()
            self.assertIn("include 'nms:nms-api'", settings)
            self.assertIn("include 'nms:nms-loader'", settings)
            self.assertIn("include 'nms:nms-paper-modern'", settings)
            self.assertIn("include 'nms:nms-v1_20_R3'", settings)
            self.assertIn("include 'nms:nms-v1_21_R3'", settings)

            base = "com/example/mycore/nms"
            for rel in ("Nms.java", "NmsHandler.java", "NmsProvider.java"):
                self.assertTrue((root / "nms/nms-api/src/main/java" / base / rel).exists())
            self.assertTrue((root / "nms/nms-loader/src/main/java" / base / "loader/NmsLoader.java").exists())
            service = root / "nms/nms-v1_21_R3/src/main/resources/META-INF/services/com.example.mycore.nms.NmsProvider"
            self.assertIn("v1_21_R3.NmsHandlerImpl$Provider", service.read_text())
            self.assertTrue((root / "nms/nms-paper-modern/src/main/java" / base / "paper_modern/NmsHandlerImpl.java").exists())
            build_logic = (root / "buildLogic/build.gradle").read_text()
            self.assertIn("project(':nms:nms-v1_20_R3')", build_logic)
            self.assertIn("project(':nms:nms-v1_21_R3')", build_logic)

    def test_wrapper_and_build_script(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, root = generate(tmp, platforms=["bukkit"], include_api=True)
            wrapper = (root / "gradle/wrapper/gradle-wrapper.properties").read_text()
            self.assertIn("gradle-9.8.0-bin.zip", wrapper)
            self.assertTrue((root / "gradlew").exists())
            self.assertTrue((root / "gradlew.bat").exists())
            self.assertTrue((root / "gradle/wrapper/gradle-wrapper.jar").exists())
            self.assertTrue((root / "build.sh").exists())

    def test_velocity_plugin_id_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, root = generate(tmp, platforms=["velocity"], include_api=True)
            java = next(root.glob("velocity/src/main/java/**/*Velocity.java")).read_text()
            import re
            match = re.search(r'@Plugin\(id = "([^"]+)"\)', java)
            self.assertIsNotNone(match)
            self.assertRegex(match.group(1), r"^[a-z][a-z0-9_-]*$")


if __name__ == "__main__":
    unittest.main()
