NOTE: This is just a static copy of code from Gitea, action workflow will not run here.

# Dash Sensor Status

Web-based dashboard for monitoring sensor status in real-time.

## Features

- **Real-time Monitoring** - Live sensor status updates
- **Web Interface** - Clean dashboard UI with responsive design
- **Docker Support** - Containerized deployment with Docker Compose
- **Configuration** - Environment-based setup via `.env` file

## Tech Stack

Python, Flask, HTML/CSS, Docker

## Quick Start

```bash
# Clone repository
git clone https://github.com/abiding9072/dash_sensor_status.git
cd dash_sensor_status

# Configure environment
cp env.example .env
# Edit .env with your settings

# Run with Docker
docker-compose up
```

## Structure

```
├── app.py              # Main application
├── templates/          # HTML templates
├── static/             # CSS and assets
├── Dockerfile          # Container image
└── compose.yaml        # Docker orchestration
```

<img width="1916" height="1073" alt="image" src="https://github.com/user-attachments/assets/7fc10044-f87a-43a1-9841-fff6f422c034" />
