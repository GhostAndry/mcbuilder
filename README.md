# MC Builder

Generatore con GUI cross-platform (Windows, macOS, Linux) di progetti Minecraft plugin multi-modulo Gradle, con `buildLogic` a convention plugins e jar unificato via Shadow.

## Funzionalità

- **Multi-modulo Gradle**: ogni modulo è `{server}-{version}` (es. `paper-1.20.4`, `velocity-3.4.0`)
- **API condivisa opzionale**: genera un modulo `api/` per interfacce e contratti; i moduli server dipendono da `implementation(project(":api"))`
- **Wrapper Gradle incluso**: vengono generati `gradlew`, `gradlew.bat` e `gradle-wrapper.jar`, quindi basta eseguire `./gradlew build`
- **Java corretta per versione**: Paper/Folia/Purpur/Spigot 1.20.5+ usano Java 21, le altre Java 17; il JDK mancante viene scaricato automaticamente dal toolchain Foojay
- **Descriptor per piattaforma**: `plugin.yml` (Bukkit), `bungee.yml` (BungeeCord/Waterfall), `velocity-plugin.json` via annotation processor (Velocity)
- **GUI premium** dark-theme con CustomTkinter
- **Server supportati**: Paper, Spigot, Bukkit, Purpur, Folia, Velocity, BungeeCord, Waterfall

## Installazione e avvio

```bash
pip install -r requirements.txt
python -m mcbuilder
```

## Utilizzo

1. Inserisci nome progetto, group e versione nella barra laterale
2. Clicca **+ Add module** per ogni modulo; abilita **Crea modulo API condiviso** se servono interfacce condivise
3. Scegli la **cartella di output** e premi **⚡ Generate project**

Il selettore Gradle parte da **9.8.0** e aggiorna in background l'elenco delle release stabili da `https://services.gradle.org/versions/all`; offline usa un elenco integrato e puoi digitare una versione manualmente.

## Struttura generata

```
my-plugin/
├── gradlew / gradlew.bat
├── gradle/wrapper/…
├── settings.gradle.kts
├── build.gradle.kts
├── gradle.properties
├── buildLogic/                  # convention plugin (mcbuilder.module)
│   └── src/main/kotlin/…
├── api/                         # opzionale
└── paper-1.20.4/
    ├── build.gradle.kts
    └── src/main/{java,resources}/…
```

## Build del progetto generato

```bash
cd <project-folder>
./gradlew build
# Jar unificati in build/libs/<modulo>-<versione>.jar
```

## Build distributable (MC Builder stesso)

- **macOS / Linux:** `./build.sh`
- **Windows:** `build.cmd`

Gli script creano un venv locale, installano dipendenze + PyInstaller e producono un binario singolo in `dist/` (`MCBuilder` o `MCBuilder.exe`).

> **Nota su Tk:** `customtkinter` richiede `tkinter`.
> - macOS: `brew install python-tk@3.14` (il Tk 8.5 di Apple non è supportato)
> - Linux: `sudo apt install python3-tk`
> - Forza un Python specifico: `PYTHON=/path/to/python ./build.sh`

## Build automatiche e release

GitHub Actions compila e verifica la GUI su **Windows x86_64** e **Linux x86_64** a ogni push su `main`, pull request o avvio manuale. Per pubblicare una release:

```bash
git tag v1.0.0
git push origin v1.0.0
```

La release include ZIP Windows, TAR.GZ Linux e `SHA256SUMS.txt` e viene creata solo se entrambe le build riescono.
