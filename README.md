# Report to podcast (market reports, local TTS)

`report_to_podcast.py` turns a written report — e.g. a market study from `space-market-intel` — into a
two-voice audio briefing. Unlike the original generator below, it **reads the document** and is told to
say only what the report says, keeping its flight-proven / roadmap labels, hedges and dates.

```
python report_to_podcast.py make ../space-market-intel/market-studies/reaction-wheel/2026-09-30/report.md
# -> episodes/reaction-wheel-2026-09-30.txt  (script: read and edit it)
# -> episodes/reaction-wheel-2026-09-30.mp3  (audio)
```

Two stages, so you can review the script before making audio:

| Command | Does | Needs |
|---|---|---|
| `script report.md [--style story\|briefing] [--minutes 12] [--note "..."]` | Claude writes the dialogue (`ALEX:` / `SAM:` paragraphs) | Anthropic credentials (`ANTHROPIC_API_KEY` or `ant auth login`) |
| `audio episode.txt [--report report.md]` | Speaks it with [Kokoro](https://huggingface.co/hexgrad/Kokoro-82M), locally on CPU, then ffmpeg to MP3 | Nothing external after the one-time model download (~330 MB) |
| `make report.md` | Both | Both |

- **Style.** `story` (default) opens on the most surprising finding and builds the episode around three
  to five stories from the report, with a host who reacts and asks "so what?". `briefing` is a straight
  read-out of the findings.
- **Background.** The script may explain concepts the report relies on (how a wheel works, what TRL or
  qualification means, why micro-vibration matters) from general knowledge. Background never names a
  company or product or gives a market figure, sits under a `# background` marker line so you can see
  what isn't from the report, and is capped at about a fifth of the episode. Market facts still come
  only from the report.
- For a `market-studies/<category>/<date>/report.md`, the study's row in `market-studies/index.md` is
  passed along automatically, so a correction recorded there (a ⚠️ note) is respected.
- After the script is written, every number in its report-sourced turns is checked against the report
  and any that do not appear are listed; the background share is reported, and numbers inside
  background turns are listed for a look. It catches invented figures, not a real figure attached to the wrong product —
  read the script before relying on it.
- Voices: `--voice ALEX=bm_george --voice SAM=bf_emma` (any Kokoro voice). Speaking rate defaults to `--speed 1.5`; lower it for a slower read.
- Synthesis runs at roughly real time on a 4-core CPU.
- Only the script stage sends text off the machine (to the Claude API). Don't feed it material you
  wouldn't send there.

Setup (Python 3.10–3.12, plus `ffmpeg`):

```
python3.12 -m venv venv && source venv/bin/activate
pip install --index-url https://download.pytorch.org/whl/cpu torch
pip install -r requirements-report.txt
```

---

# AI-Podcast-Generator

AI Podcast Generator is a AI powered software that automatically generates podcast scripts and audio from text files. This tool leverages [Marvin](https://github.com/PrefectHQ/marvin) for text generation and [Play.ht API](https://docs.play.ht/reference/api-getting-started) for text-to-speech conversion. The generated audio clips are then merged using [pydub](https://github.com/jiaaro/pydub) to create the final podcast output.

## Features

- Generate podcast scripts and audio automatically.
- Customize podcast details, host, guest, topics, and output settings.
- Supports multiple voices from Play.ht API.
- Requires minimal setup and configuration.

## Examples

[**Soundcloud Playlist 📻**](https://soundcloud.com/aastroza/sets/ai-podcast-generator?si=b10c28990e5f424eae907075448ddaf8&utm_source=clipboard&utm_medium=text&utm_campaign=social_sharing)

### Artificial Intelligence for Natural Brains
[This Audio](https://github.com/aastroza/ai-podcast-generator/raw/main/examples/ai/2023-04-24_e8548d33-47b0-493e-9326-b95d618af463.mp3) was generated based on this YAML text file.

```yaml
# Podcast Interview Configuration
podcast:
  info:
    title: Artificial Intelligence for Natural Brains
    description: A podcast where we talk about the future of AI and how it will affect our lives
  host:
    name: Brandon Bert
    voice: en-US-BrandonNeural #A value from data/voices.json
  guest:
    name: Monica Gradient
    voice: en-US-MonicaNeural #A value from data/voices.json
  topics:
    main: Artificial Intelligence
    sub:
      - ChatGPT
      - Generative AI
      - AGI
      - AI Ethics
  output:
    duration: 5 #Episode length in minutes
    language: english
    audio: True #Set to False if you want to generate only the text script
    folder: examples/ai/
```


### Cats and Egyptians Gods (Spanish)
[This Audio](https://github.com/aastroza/ai-podcast-generator/raw/main/examples/cats/2023-04-24_f08752be-a652-4df7-9e12-591dee1da6ad.mp3) was generated based on this YAML text file.

```yaml
# Podcast Interview Configuration
podcast:
  info:
    title: Todos los gatitos se van al cielo
    description: Un programa donde conversamos sobre gatitos y las divinidades egipcias
  host:
    name: Alfonso Astorga
    voice: es-AR-TomasNeural #A value from data/voices.json
  guest:
    name: Alicia Cats
    voice: es-MX-BeatrizNeural #A value from data/voices.json
  topics:
    main: Gatos y Dioses Egipcios
    sub:
      - Los Gatos en el Antiguo Egipto
      - Historias acerca de Gatos y Dioses Egipcios
      - ¿Por qué los gatos eran considerados divinos?
  output:
    duration: 5 #Episode length in minutes
    language: spanish
    audio: True #Set to False if you want to generate only the text script
    folder: examples/cats/
```

### Can ants be standup comedians? (Spanish)
[This Audio](https://github.com/aastroza/ai-podcast-generator/raw/main/examples/ants/2023-04-24_6985971b-9a53-4f11-bc86-8cc9dfe26bec.mp3) was generated based on this YAML text file.

```yaml
# Podcast Interview Configuration
podcast:
  info:
    title: Los que reímos al último
    description: Un programa donde conversamos sobre la comedia, el humor y los que les gusta terminar el día con una sonrisa
  host:
    name: Alfonso Astorga
    voice: es-US-AlonsoNeural #A value from data/voices.json
  guest:
    name: Penelope Antenas
    voice: es-CO-SalomeNeural #A value from data/voices.json
  topics:
    main: Las hormigas y la comedia
    sub:
      - ¿Pueden hablar las hormigas?
      - ¿Pueden las hormigas hacer comedia?
      - ¿Sobre que se ríen las hormigas?
      - Cuentanos un chiste clásico que hagan las hormigas.
      - Nombre un comediante hormiga famoso.
  output:
    duration: 5 #Episode length in minutes
    language: spanish
    audio: True #Set to False if you want to generate only the text script
    folder: examples/ants/
```

## Installation

1. Clone this repository:

```
git clone https://github.com/aastroza/podcast-automation.git
```

2. Navigate to the project directory:

```
cd podcast-automation
```

3. Create a Python virtual environment:

```
python3 -m venv venv
```

4. Activate the virtual environment:

- For Linux/MacOS:

```
source venv/bin/activate
```

- For Windows:

```
venv\Scripts\activate.bat
```

5. Install the required packages:

```
pip install -r requirements.txt
```

## Usage

1. Create a YAML configuration file for your podcast (e.g., [`podcast.YAML`](examples/ai/podcast.YAML)).
2. Set up the environment variables by creating a `.env` file and adding the required API keys.
3. Run the script to generate the podcast:

```
python podcast.py --input examples/ai/podcast.YAML
```

The script will generate the podcast audio and save it in output folder specified in the YAML file.

## Configuration

The YAML configuration file contains information about the podcast, host, guest, topics, and output settings. Here's an example:

```yaml
# Podcast Interview Configuration
podcast:
  info:
    title: Artificial Intelligence for Natural Brains
    description: A podcast where we talk about the future of AI and how it will affect our lives
  host:
    name: Brandon Bert
    voice: en-US-BrandonNeural #A value from data/voices.json
  guest:
    name: Monica Gradient
    voice: en-US-MonicaNeural #A value from data/voices.json
  topics:
    main: Artificial Intelligence
    sub:
      - ChatGPT
      - Generative AI
      - AGI
      - AI Ethics
  output:
    duration: 5 #Episode length in minutes
    language: english
    audio: True #Set to False if you want to generate only the text script
    folder: examples/ai/
```

## Getting an API key
To obtain an **OpenAI API key**, follow these steps:

- Log in to your an [OpenAI account](https://platform.openai.com/) (sign up if you don't have one)
- Go to the "API Keys" page under your account settings.
- Click "Create new secret key." A new API key will be generated. Make sure to copy the key to your clipboard, as you will not be able to see it again.

To obtain a **Play.HT API access**, follow [these instructions](https://docs.play.ht/reference/api-authentication).

## Environment Variables

1. Rename `.env.example` fileto `.env` in the project directory:
2. Open the `.env` file and replace the placeholder values with your actual API keys:

```
OPENAI_API_KEY='your_openai_api_key'
PLAYHT_SECRET='your_playht_secret_key'
PLAYHT_USER_ID='your_playht_user_id'
```

Make sure to save the changes to the `.env` file.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more information.