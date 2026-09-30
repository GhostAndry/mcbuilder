# MC Builder

GUI cross-platform (Windows, macOS, Linux) che genera progetti Minecraft plugin **multi-piattaforma** in stile Aurora: `api` → `common` → `bukkit`/`velocity`, con supporto opzionale NMS multi-versione e un `buildLogic` che produce un jar unificato via Shadow.

## Funzionalità

- **Multi-piattaforma**: `api` (interfacce) + `common` (implementazioni) + `bukkit` (Paper/Bukkit) e/o `velocity`
- **NMS multi-versione opzionale**: genera `nms/nms-api`, `nms/nms-loader`, `nms/nms-paper-modern` e i moduli `nms/nms-v*` selezionati, con caricamento via `ServiceLoader` e rilevamento automatico della versione server
- **Jar unificato**: `buildLogic` applica Shadow e aggrega api, common, piattaforme e NMS in un singolo jar in `build/libs/`
- **Wrapper incluso**: `gradlew`, `gradlew.bat`, `gradle-wrapper.jar`
- **Java 21** di default, toolchain configurabile
- GUI dark premium con CustomTkinter

## Installazione e avvio

```bash
pip install -r requirements.txt
python -m mcbuilder
```

## Utilizzo

1. Inserisci nome progetto, group, versione, descrizione
2. Seleziona le **piattaforme** (Paper/Bukkit, Velocity)
3. Attiva/disattiva **api** e **common**
4. Abilita **NMS** e scegli le versioni da generare (le altre vanno ricompilate con BuildTools)
5. Scegli la **cartella di output** e premi **⚡ Generate project**

## Struttura generata

```
MyPlugin/
├── gradlew / gradlew.bat / gradle/wrapper/
├── settings.gradle
├── build.gradle
├── gradle.properties
├── build.sh
├── buildLogic/              # aggrega tutto in un jar unificato (Shadow)
├── api/                     # interfacce
├── common/                  # implementazioni condivise
├── bukkit/                  # plugin Paper/Bukkit (plugin.yml)
├── velocity/                # plugin Velocity
└── nms/                     # opzionale
    ├── nms-api/             # Nms, NmsHandler, NmsProvider
    ├── nms-loader/          # rileva versione, ServiceLoader
    ├── nms-paper-modern/
    └── nms-v<ver>/          # codice version-specific (BuildTools)
```

## Build del progetto generato

```bash
cd <project-folder>
./gradlew build
# Jar unificato: build/libs/<Progetto>-<versione>.jar
```

### NMS e BuildTools

I moduli `nms-v*` compilano contro i jar Spigot/Paper generati con [BuildTools](https://www.spigotmc.org/wiki/buildtools/). Copiali in `nms/nms-<ver>/lib/`. I moduli senza i jar sono commentati in `settings.gradle`.

## Build distributable (MC Builder stesso)

- **macOS / Linux:** `./build.sh`
- **Windows:** `build.cmd`

> **Nota su Tk:** `customtkinter` richiede `tkinter`.
> - macOS: `brew install python-tk@3.14` (Tk 8.5 di Apple non è supportato)
> - Linux: `sudo apt install python3-tk`
> - Forza un Python specifico: `PYTHON=/path/to/python ./build.sh`

## Build automatiche e release

GitHub Actions compila e verifica la GUI su **Windows x86_64** e **Linux x86_64** a ogni push su `main`, PR o run manuale. Per pubblicare una release:

```bash
git tag v1.0.0
git push origin v1.0.0
```

La release include ZIP Windows, TAR.GZ Linux e `SHA256SUMS.txt`.
