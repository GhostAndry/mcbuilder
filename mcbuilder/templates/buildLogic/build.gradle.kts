plugins {
    `kotlin-dsl`
}

group = "mcbuilder.buildlogic"

repositories {
    gradlePluginPortal()
    mavenCentral()
}

dependencies {
    implementation("com.gradleup.shadow:shadow-gradle-plugin:9.6.1")
}

gradlePlugin {
    plugins {
        register("mcbuilderModule") {
            id = "mcbuilder.module"
            implementationClass = "mcbuilder.module.McModulePlugin"
        }
    }
}
