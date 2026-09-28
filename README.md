# MC Builder

## Build automatiche e release

GitHub Actions compila e verifica la GUI su **Windows x86_64** e **Linux x86_64** a ogni push su `main`, pull request o avvio manuale da **Actions → Build and release → Run workflow**. Gli archivi sono scaricabili dagli artifact della run.

Per pubblicare automaticamente una release con ZIP Windows, TAR.GZ Linux e checksum SHA-256:

```bash
git tag v1.0.0
git push origin v1.0.0
```

La release viene creata solo se entrambe le build riescono. Il binario Linux richiede un ambiente desktop ed è compilato su Ubuntu 22.04 (glibc 2.35 o successiva). Ogni eseguibile è specifico del sistema operativo e dell'architettura di build.

Generatore di progetti Minecraft plugin multi-modulo Gradle con GUI cross-platform (Windows, macOS, Linux).

## Funzionalità

- 🧱 **Multi-modulo Gradle**: ogni modulo = `{server}-{version}`
- **API condivisa opzionale**: seleziona “Crea modulo API condiviso” per generare `api/`, una libreria Java per interfacce e contratti. Tutti i moduli server dipendono da `implementation(project(":api"))`. Senza la selezione non viene generato alcun modulo API.
- 🎨 **GUI premium** dark-theme con CustomTkinter
- 🌍 **Cross-platform**: Windows, macOS, Linux
- 📦 **buildLogic** con convention plugins + Shadow per il jar unificato
- 🎮 **Server supportati**: Paper, Spigot, Bukkit, Purpur, Folia, Velocity, BungeeCord, Fabric, Forge, NeoForge, Sponge, Nukkit

## Installazione

```bash
pip install -r requirements.txt
```

## Avvio

Dalla root del progetto:

```bash
python -m mcbuilder
```

## Utilizzo

Il selettore Gradle parte da **9.8.0** e aggiorna in background l'elenco delle release stabili da `https://services.gradle.org/versions/all`. Offline usa un elenco integrato delle serie 8.x/9.x; puoi anche digitare una versione. La selezione viene applicata al `distributionUrl` del wrapper generato. La presenza nell'elenco non certifica la compatibilità di tutti i plugin di build con quella release; Gradle 9 richiede almeno Java 17 per eseguire la build.

1. Scegli il nome del progetto, group, versione
2. Clicca **+ Add module** per ogni modulo (es. `paper-1.20.4`); abilita **Crea modulo API condiviso** se vuoi esporre le interfacce del progetto in `api/src/main/java/<group>/api/`.
3. Seleziona **cartella di output** (il progetto verrà creato dentro come sottocartella)
4. Premi **⚡ Generate project**

Il JAR unificato di ogni modulo viene generato con `./gradlew shadowJar` e copiato in `build/libs/`.

## Struttura generata

```
my-plugin/
├── build.gradle.kts
├── settings.gradle.kts
├── gradle.properties
├── buildLogic/                  # convention plugins
│   ├── settings.gradle.kts
│   └── convention/
│       ├── build.gradle.kts
│       └── src/main/kotlin/...
├── paper-1.20.4/
│   ├── build.gradle.kts
│   └── src/main/{java,resources}/...
└── velocity-3.3.0/
    ├── build.gradle.kts
    └── src/main/{java,resources}/...
```

## Build

```bash
cd <project-folder>
./gradlew shadowJar
# Output: build/libs/<module>-<version>.jar
```

## Build distributable (MC Builder itself)

Crea un eseguibile standalone nella cartella `dist/`:

- **macOS / Linux:** `./build.sh`
- **Windows:** `build.cmd`

Lo script crea un venv locale (se mancante), installa dipendenze + PyInstaller, e produce un singolo binario (`MCBuilder` su macOS/Linux, `MCBuilder.exe` su Windows) portabile su tutto il sistema.

> **Nota su Tk:** `customtkinter` richiede `tkinter`. Lo script rileva automaticamente un Python con Tk:
> - macOS: installa `brew install python-tk@3.14`; lo script rileva Python Homebrew e usa `.venv-build`. Tk 8.5 di Apple non è supportato.
> - Linux: installa `python3-tk` (es. `sudo apt install python3-tk`)
> - pyenv Python: installa Tcl/Tk moderno e ricompila Python seguendo le istruzioni pyenv per il tuo sistema.
>
> Oppure forza il Python: `PYTHON=/path/to/python ./build.sh`
