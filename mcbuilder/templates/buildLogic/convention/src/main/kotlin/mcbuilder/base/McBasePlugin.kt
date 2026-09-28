package mcbuilder.base

import org.gradle.api.Plugin
import org.gradle.api.Project

class McBasePlugin : Plugin<Project> {
    override fun apply(target: Project) {
        target.subprojects {
            if (name != "api") {
                apply(plugin = "mcbuilder.module")
            }
        }
    }
}
