package mcbuilder.module

import com.github.jengelman.gradle.plugins.shadow.tasks.ShadowJar
import org.gradle.api.Plugin
import org.gradle.api.Project
import org.gradle.api.plugins.JavaPlugin
import org.gradle.api.tasks.Copy
import org.gradle.api.tasks.bundling.Jar

class McModulePlugin : Plugin<Project> {
    override fun apply(target: Project) {
        with(target) {
            apply(plugin = "java-library")

            extensions.configure(JavaPlugin::class.java) { _ -> }

            tasks.named<Jar>("jar") {
                archiveClassifier.set("unshaded")
            }

            tasks.named<ShadowJar>("shadowJar") {
                archiveClassifier.set("")
                mergeServiceFiles()
            }

            tasks.named("build") {
                dependsOn("shadowJar")
            }

            tasks.register<Copy>("copyJarToRoot") {
                from(tasks.named<ShadowJar>("shadowJar"))
                into(rootProject.layout.buildDirectory.dir("libs"))
            }

            afterEvaluate {
                tasks.named("build").configure {
                    finalizedBy("copyJarToRoot")
                }
            }
        }
    }
}
