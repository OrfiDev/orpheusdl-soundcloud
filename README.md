<!-- PROJECT INTRO -->

OrpheusDL - SoundCloud
=================

A SoundCloud module for the OrpheusDL modular archival music program

[Report Bug](https://github.com/yarrm80s/orpheusdl-soundcloud/issues)
·
[Request Feature](https://github.com/yarrm80s/orpheusdl-soundcloud/issues)


## Table of content

- [About OrpheusDL - SoundCloud](#about-orpheusdl-soundcloud)
- [Getting Started](#getting-started)
    - [Prerequisites](#prerequisites)
    - [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
    - [SoundCloud](#soundcloud)
- [Contact](#contact)


<!-- ABOUT ORPHEUS -->
## About OrpheusDL - SoundCloud

OrpheusDL - SoundCloud is a module written in Python which allows archiving from **SoundCloud** for the modular music archival program.


<!-- GETTING STARTED -->
## Getting Started

Follow these steps to get a local copy of Orpheus up and running:

### Prerequisites

* Already have [OrpheusDL](https://github.com/yarrm80s/orpheusdl) installed

### Installation

Just clone the repo inside the folder `orpheusdl/modules/`
   ```sh
   git clone https://github.com/yarrm80s/orpheusdl-soundcloud.git orpheusdl/modules/soundcloud
   ```

<!-- USAGE EXAMPLES -->
## Usage

Just call `orpheus.py` with any link you want to archive:

```sh
python orpheus.py https://soundcloud.com/alanwalker/darkside-feat-tomine-harket-au
```

<!-- CONFIGURATION -->
## Configuration

You can customize every module from Orpheus individually and also set general/global settings which are active in every
loaded module. You'll find the configuration file here: `config/settings.json`

### SoundCloud
```json
"soundcloud": {
    "access_token": "",
    "artist_download_ignore_tracks_in_albums": ""
}
```
`access_token`: An access token from the MOBILE app in the form `2-111111-1111111111-aaaaaaaaaaaaa`

`artist_download_ignore_tracks_in_albums`: When downloading artists, albums and tracks are downloaded separately. Enable this to skip tracks already downloaded in albums.

<!-- Contact -->
## Contact

Yarrm80s - [@yarrm80s](https://github.com/yarrm80s)

Project Link: [OrpheusDL SoundCloud Public GitHub Repository](https://github.com/yarrm80s/orpheusdl-soundcloud)
