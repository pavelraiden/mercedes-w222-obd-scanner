# Mercedes W222 OBD Scanner: Production Deployment Guide

**Author:** Manus AI & Claude
**Version:** 3.0.0-production
**Date:** 2025-09-27

## 1. Introduction

This document provides a comprehensive guide for deploying the **Mercedes W222 OBD Scanner** in a production environment. The system is designed for commercial-grade reliability, scalability, and security, leveraging a modern containerized architecture with Docker and Docker Compose. This guide is intended for system administrators and developers with basic knowledge of Docker and Linux environments.

## 2. System Architecture

The production architecture is composed of several interconnected services, all managed by Docker Compose. This containerized approach ensures consistency across different environments and simplifies dependency management.

| Service                  | Description                                                                                                | Technology Stack        |
| ------------------------ | ---------------------------------------------------------------------------------------------------------- | ----------------------- |
| **Web Application**      | The main FastAPI application that serves the web dashboard, API, and real-time communication.              | Python, FastAPI, Gunicorn |
| **Web Dashboard**        | A modern, responsive user interface for real-time monitoring, trip analysis, and diagnostics.              | React, shadcn/ui, Recharts |
| **Database**             | A robust PostgreSQL database for storing all OBD data, trip information, and ML model metadata.            | PostgreSQL              |
| **Cache & Task Queue**   | A Redis instance for caching frequently accessed data and managing background tasks.             | Redis                   |
| **Monitoring**           | A full monitoring stack to collect metrics, visualize performance, and set up alerts.                      | Prometheus, Grafana     |
| **Reverse Proxy**        | An Nginx server that acts as a reverse proxy, providing load balancing, security, and SSL termination.       | Nginx                   |

## 3. Prerequisites

Before proceeding with the deployment, ensure your server meets the following requirements:

- **Operating System:** A modern Linux distribution (e.g., Ubuntu 22.04 or later).
- **Docker:** The latest version of Docker must be installed. [1]
- **Docker Compose:** The latest version of Docker Compose is also required. [2]
- **Hardware:**
  - **CPU:** 2 or more CPU cores.
  - **RAM:** 4 GB or more.
  - **Disk Space:** At least 20 GB of free disk space.
- **API Keys:** You will need API keys from Anthropic (for Claude) and Stripe to enable the AI-powered analysis and payment features.

## 4. Deployment Steps

The deployment process is automated through the `deploy-production.sh` script. Follow these steps to get the application running.

### 4.1. Clone the Repository

First, clone the project repository to your server:

```bash
$ git clone https://github.com/pavelraiden/mercedes-w222-obd-scanner.git
$ cd mercedes-w222-obd-scanner
```

### 4.2. Run the Deployment Script

The deployment script will handle everything from creating directories to building and launching the services. Run the script with the following command:

```bash
$ ./deploy-production.sh
```

The script will perform the following actions:

1.  **Check System Requirements:** Verifies that Docker and Docker Compose are installed.
2.  **Create Directories:** Creates necessary directories for data, logs, and backups.
3.  **Generate Environment File:** Creates a `.env` file for your configuration. **This is a critical step.**
4.  **Set Up Monitoring:** Configures Prometheus and Grafana for monitoring.
5.  **Build and Deploy:** Builds the Docker images and launches all services using Docker Compose.

### 4.3. Configure Environment Variables

After the first run, the deployment script will create a `.env` file. You **must** edit this file to add your API keys and any other custom configurations.

```bash
$ nano .env
```

Update the following lines with your actual API keys:

```
ANTHROPIC_API_KEY=your_anthropic_api_key_here
STRIPE_SECRET_KEY=your_stripe_secret_key_here
STRIPE_WEBHOOK_SECRET=your_stripe_webhook_secret_here
```

After saving your changes, you will need to restart the application for the new settings to take effect:

```bash
$ docker-compose -f docker-compose.production.yml restart
```

## 5. Accessing the Application

Once the deployment is complete, you can access the various components of the system:

- **Web Dashboard:** `http://<your_server_ip>`
- **Grafana Monitoring:** `http://<your_server_ip>:3000` (Default login: `admin`/`admin`)
- **Prometheus Metrics:** `http://<your_server_ip>:9090`

## 6. System Management

All services are managed through Docker Compose. Here are some common commands for managing the system.

- **View Logs:**

  ```bash
  $ docker-compose -f docker-compose.production.yml logs -f
  ```

- **Stop Services:**

  ```bash
  $ docker-compose -f docker-compose.production.yml down
  ```

- **Restart Services:**

  ```bash
  $ docker-compose -f docker-compose.production.yml restart
  ```

- **Update Deployment:**

  To update the application to the latest version, simply run the deployment script with the `--update` flag:

  ```bash
  $ ./deploy-production.sh --update
  ```

## 7. Backup and Restore

Regular backups are crucial for a production system. The system includes a robust backup manager.

- **Create a Backup:**

  ```bash
  $ ./deploy-production.sh --backup
  ```

  This will create a compressed archive of your data and logs in the `backups/` directory.

- **Restore from Backup:**

  To restore from a backup, use the `--restore` flag with the path to your backup file:

  ```bash
  $ ./deploy-production.sh --restore backups/your_backup_file.tar.gz
  ```

## 8. References

[1] Docker. (n.d.). *Install Docker Engine*. Docker Documentation. Retrieved from https://docs.docker.com/engine/install/

[2] Docker. (n.d.). *Install Docker Compose*. Docker Documentation. Retrieved from https://docs.docker.com/compose/install/

---

*This document was collaboratively generated by Manus AI and Claude.*

