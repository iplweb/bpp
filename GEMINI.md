# BPP (Bibliografia Publikacji Pracowników)

This document provides a comprehensive overview of the BPP project, its architecture, and development practices to be used as a context for Gemini.

## Project Overview

BPP is a sophisticated open-source (MIT licensed) web application designed for managing the bibliography of publications by academic staff at Polish universities. It serves as a central repository for publications, helping institutions with reporting, evaluation, and maintaining a comprehensive record of scholarly output.

### Architecture

The project is a monolithic Django application with a rich set of features and a traditional server-side rendered frontend. It leverages a number of technologies to provide a robust and scalable system:

*   **Backend**: Python with the Django web framework.
*   **Database**: PostgreSQL.
*   **Asynchronous Tasks**: Celery with Redis as the message broker.
*   **Real-time Features**: Django Channels with Daphne for WebSocket support.
*   **Frontend**: JavaScript (jQuery, Foundation, htmx, DataTables.net) and SASS for styling.
*   **Containerization**: Docker and Docker Compose for development and production environments.
*   **CI/CD**: GitHub Actions for running tests and building Docker images.

## Getting Started

### Prerequisites

*   [uv](https://github.com/astral-sh/uv): For managing Python dependencies.
*   [Docker](https://www.docker.com/): For running the application and its services.
*   [Node.js](https://nodejs.org/) and [Yarn](https://yarnpkg.com/): For managing frontend dependencies.
*   [GNU Make](https://www.gnu.org/software/make/): For running common development tasks.

### Installation

1.  **Install Python dependencies:**
    ```bash
    uv sync --all-extras
    ```

2.  **Install frontend dependencies:**
    ```bash
    yarn install
    ```

3.  **Build frontend assets:**
    ```bash
    make assets
    ```

### Running the Application

The application is designed to be run with Docker Compose.

1.  **Start all services:**
    ```bash
    docker compose up
    ```

2.  The application will be available at `http://localhost:1080` and `https://localhost:10443`. The main Django application runs on port 8000.

## Development

### Building Assets

Frontend assets (CSS and JavaScript) are managed with Grunt and Sass. To build the assets, run:

```bash
make assets
```

### Running Tests

The project has a comprehensive test suite, including unit tests, integration tests, and end-to-end tests using Selenium and Playwright.

*   **Run all tests:**
    ```bash
    make tests
    ```

*   **Run tests without Selenium:**
    ```bash
    make tests-without-selenium
    ```

*   **Run tests with Selenium:**
    ```bash
    make tests-with-selenium
    ```

*   **Run JavaScript tests:**
    ```bash
    make js-tests
    ```

### Database

The application uses PostgreSQL as its database. The `fabfile.py` contains tasks for managing the database, such as `getdb`, `putdb`, and `installdb`.

### Coding Style & Conventions

The project enforces a consistent coding style and high code quality using a set of tools integrated with pre-commit hooks.

*   **Linting and Formatting**: `ruff` is used for linting and formatting Python code.
*   **Pre-commit Hooks**: The `.pre-commit-config.yaml` file defines a set of hooks that are run before each commit to ensure code quality, including `ruff`, `check-yaml`, `check-toml`, and `trufflehog` for secret scanning.

## Docker

The project is fully containerized with Docker. The `docker-compose.yml` file defines the services for the application, and the `Makefile` contains commands for building the Docker images.

### Building Images

To build all Docker images, run:

```bash
make docker
```

### Services

The `docker-compose.yml` file defines the following services:

*   `db`: The PostgreSQL database.
*   `redis`: The Redis server for Celery and caching.
*   `appserver`: The main Django application.
*   `workerserver-*`: Celery workers for different queues.
*   `celerybeat`: The Celery beat scheduler.
*   `webserver`: An Nginx reverse proxy.
*   `ofelia`: A cron-like scheduler for running periodic tasks in a Docker environment.
