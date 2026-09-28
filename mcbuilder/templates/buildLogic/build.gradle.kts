plugins {
    `kotlin-dsl`
}

group = "mcbuilder.buildlogic"

java {
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
}

repositories {
    gradlePluginPortal()
    mavenCentral()
}

dependencies {
    implementation("com.github.jengelman.gradle.plugins:shadow:8.1.1")
}
