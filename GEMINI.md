# GEMINI.md

## Project Overview

This project is an educational video automation system that transforms ideas into engaging short-form videos for platforms like TikTok and Instagram Reels. It leverages AI to automate the entire video creation process, from research and music generation to visual curation and video assembly.

The system is built primarily in Python and shell scripts. It uses a modular, agent-based architecture, where each stage of the pipeline is handled by a specific script or "agent." The pipeline is orchestrated by the `pipeline.sh` script, which executes the agents in a predefined order.

### Key Technologies

*   **Python**: The core logic is written in Python, utilizing libraries like:
    *   `moviepy` for video editing and assembly.
    *   `sentence-transformers` and `torch` for semantic analysis and visual ranking.
    *   `requests` for interacting with external APIs (e.g., Suno for music generation).
    *   `google-api-python-client` for uploading videos to YouTube.
    *   `pycaps` for generating karaoke-style subtitles.
*   **Shell Scripts**: Used for orchestrating the pipeline and managing the different stages.
*   **Suno API**: For generating AI-powered music.
*   **Claude Code CLI**: For AI-powered phrase grouping and other tasks.

### Architecture

The project follows a pipeline architecture, where each stage produces artifacts that are used by subsequent stages. The main stages are:

1.  **Research**: Gathers facts and royalty-free media related to the input idea.
2.  **Visual Ranking**: Analyzes the curated media for visual diversity using CLIP.
3.  **Context Pruning (for Lyricist)**: A smaller version of the research data, containing only the `key_facts`, is created to reduce token usage.
4.  **Lyrics Generation**: Creates lyrics based on the pruned research data.
5.  **Music Composition**: Generates music using the Suno API.
6.  **Segment Analysis**: Analyzes the song to identify the best segments for short-form videos.
7.  **Context Pruning (for Curator)**: A smaller version of the research data, containing only the `media_suggestions`, is created.
8.  **Media Curation**: Selects and downloads the most relevant media for each shot.
9.  **Video Assembly**: Assembles the video, combining the media, music, and lyrics.
10. **Subtitle Generation**: Adds subtitles to the videos.
11. **YouTube Upload**: Uploads the final videos to YouTube.
12. **Cross-Linking**: Adds links to the video descriptions to connect the different formats.

## Building and Running

### Setup

1.  **Install Dependencies**: Run the setup script to create a virtual environment and install the required dependencies.

    ```bash
    ./setup.sh
    ```

2.  **Configure API Keys**: Add your Suno API key and configure your YouTube OAuth credentials in `config/config.json`.

### Running the Pipeline

1.  **Create an Idea**: Write your video idea in the `input/idea.txt` file.

    ```bash
    echo "Explain black holes. Tone: mysterious and awe-inspiring" > input/idea.txt
    ```

2.  **Run the Pipeline**: Execute the main pipeline script.

    ```bash
    ./pipeline.sh
    ```

    You can use the `--express` flag to skip the manual media approval step.

### Testing

The project includes a `test_pipeline.sh` script for testing the entire pipeline. There are also individual test files for specific components in the `tests/` directory.

## Development Conventions

*   **Modular Design**: The project is organized into modules, with each agent responsible for a specific task. This makes it easy to extend and maintain the system.
*   **Configuration as Code**: The pipeline's behavior can be configured through the `config/config.json` file.
*   **Timestamped Runs**: Each pipeline run is stored in a unique, timestamped directory, which makes it easy to track and debug previous runs.
*   **Logging**: The pipeline logs all output to a log file in the `logs/` directory.
