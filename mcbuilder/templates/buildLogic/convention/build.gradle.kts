plugins {
    `kotlin-dsl`
}

group = "mcbuilder.buildlogic.convention"

java {
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
}

dependencies {
    compileOnly(gradleApi())
    compileOnly("com.github.jengelman.gradle.plugins:shadow:8.1.1")
}

gradlePlugin {
    plugins {
        register("mcbuilderBase") {
            id = "mcbuilder.base"
            implementationClass = "mcbuilder.base.McBasePlugin"
        }
        register("mcbuilderModule") {
            id = "mcbuilder.module"
            implementationClass = "mcbuilder.module.McModulePlugin"
        }
    }
}
