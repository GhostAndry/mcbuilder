package mcbuilder.module

import com.github.jengelman.gradle.plugins.shadow.tasks.ShadowJar
import org.gradle.api.Plugin
import org.gradle.api.Project
import org.gradle.api.tasks.Copy

class McModulePlugin : Plugin<Project> {
    override fun apply(target: Project) {
        with(target) {
            pluginManager.apply("java-library")
            pluginManager.apply("com.gradleup.shadow")

            tasks.withType(ShadowJar::class.java).configureEach {
                archiveClassifier.set("")
                mergeServiceFiles()
            }

            tasks.named("build") {
                dependsOn("shadowJar")
            }

            val copyJarToRoot = tasks.register("copyJarToRoot", Copy::class.java) {
                from(tasks.named("shadowJar"))
                into(rootProject.layout.buildDirectory.dir("libs"))
            }

            tasks.named("build") {
                finalizedBy(copyJarToRoot)
            }
        }
    }
}
