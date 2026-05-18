# Gemeente Bekendmakingen Integration for Home Assistant

<p align="center">
  <!-- Release / License -->
  <a href="https://github.com/DonTranQuiL/Bekendmakingen/releases">
    <img src="https://img.shields.io/github/v/release/DonTranQuiL/Bekendmakingen?style=for-the-badge&color=007ec6" alt="Latest Release">
  </a>
  <a href="https://github.com/DonTranQuiL/Bekendmakingen/blob/main/LICENSE">
    <img src="https://img.shields.io/github/license/DonTranQuiL/Bekendmakingen?style=for-the-badge&color=007ec6" alt="License">
  </a>

  <!-- CI / Quality -->
  <a href="https://github.com/DonTranQuiL/Bekendmakingen/actions">
    <img src="https://img.shields.io/github/actions/workflow/status/DonTranQuiL/Bekendmakingen/codechecker.yml?style=for-the-badge&label=CODE%20CHECKS&color=5dbb0f" alt="Code Checks">
  </a>
  <a href="https://github.com/DonTranQuiL/Bekendmakingen/actions">
    <img src="https://img.shields.io/github/actions/workflow/status/DonTranQuiL/Bekendmakingen/pytest.yml?style=for-the-badge&label=TESTS&color=5dbb0f" alt="Tests">
  </a>
  <a href="https://github.com/DonTranQuiL/Bekendmakingen/actions">
    <img src="https://img.shields.io/github/actions/workflow/status/DonTranQuiL/Bekendmakingen/hacs.yaml?style=for-the-badge&label=HACS%20VALIDATION&color=5dbb0f" alt="HACS Validation">
  </a>

  <!-- Code Quality -->
  <a href="https://github.com/pre-commit/pre-commit">
    <img src="https://img.shields.io/badge/pre--commit-enabled-5dbb0f?style=for-the-badge" alt="pre-commit">
  </a>
  <a href="https://github.com/astral-sh/ruff">
    <img src="https://img.shields.io/badge/code%20style-ruff-000000?style=for-the-badge" alt="Ruff">
  </a>
  <a href="https://codecov.io/gh/DonTranQuiL/Bekendmakingen">
    <img src="https://img.shields.io/codecov/c/github/DonTranQuiL/Bekendmakingen?style=for-the-badge&color=5dbb0f&label=coverage" alt="Coverage">
  </a>

  <!-- Ecosystem -->
  <a href="https://hacs.xyz/">
    <img src="https://img.shields.io/badge/HACS-CUSTOM-ff6e27?style=for-the-badge" alt="HACS">
  </a>
  <a href="https://www.home-assistant.io/">
    <img src="https://img.shields.io/badge/Home%20Assistant-2024.5%2B-007ec6?style=for-the-badge" alt="Home Assistant">
  </a>

  <!-- Social / Support -->
  <a href="https://github.com/DonTranQuiL">
    <img src="https://img.shields.io/badge/maintainer-%40DonTranQuiL-007ec6?style=for-the-badge" alt="Maintainer">
  </a>
  <a href="https://ko-fi.com/DonTranQuiL">
    <img src="https://img.shields.io/badge/buy%20me%20a%20coffee-donate-ffdd00?style=for-the-badge" alt="Donate">
  </a>
  <a href="https://community.home-assistant.io/">
    <img src="https://img.shields.io/badge/community-forum-007ec6?style=for-the-badge" alt="Community">
  </a>
</p>

This custom component for Home Assistant allows you to monitor local government announcements, permits, and decisions for any Dutch municipality. It pulls data directly from the official [officielebekendmakingen.nl](https://zoek.officielebekendmakingen.nl/) RSS feed, keeping you informed about what is happening in your neighborhood.

> **Disclaimer:** This integration relies on the public RSS feed from the Dutch government. If the government changes the URL structure or query parameters of their search engine, this integration may need to be updated. Please use a reasonable scan interval (e.g., 3600 seconds) to avoid spamming the servers.

This integration was created with significant collaboration, testing, and debugging from **TranQuiL (@Malosaaa)**.

***
## 🚀 Key Features

* ✅ **L1/P2000-Style Persistence**: Includes a built-in JSON cache system. Your alerts are saved to disk and load **instantly** when Home Assistant reboots—no blank dashboard cards on startup.
* ✅ **Advanced Keyword Filtering**: Built-in, on-the-fly UI filtering! Choose to see 'ALLES', or strictly filter for specific categories like Aanvragen, Verleend, Meldingen, or Geweigerd. 
* ✅ **Master Sensor Approach**: A single master sensor displays the most recent announcement, while the previous 9 alerts are neatly stored in a `history` attribute.
* ✅ **Diagnostic Tracking**: Includes dedicated diagnostic sensors for "Last Update Status", "Last Update Time", and "Consecutive Errors".
* ✅ **Built-in Debugging**: Automatically generates a local `.txt` debug file in the integration folder so you can see exactly what the government server is returning.
* ✅ **Service Calls**: Includes services to manually trigger a refresh or cleanly delete all local cache and debug files.

## 🛠 Installation

### Method 1: HACS (Recommended)
1. Open **HACS** -> **Integrations**.
2. Click the 3-dots menu (top right) -> **Custom Repositories**.
3. Paste URL: `https://github.com/Malosaaa/ha-bekendmakingen` | Category: **Integration**.
4. Click **Add**, then find "Bekendmakingen" and click **Download**.
5. **Restart Home Assistant.**

### Method 2: Manual
1. Download the `bekendmakingen` folder from this repo.
2. Copy it into your Home Assistant `custom_components/` directory.
3. **Restart Home Assistant.**

## ⚙️ Configuration

1. Go to **Settings** -> **Devices & Services**.
2. Click **+ Add Integration** and search for **Bekendmakingen**.
3. **Municipality**: Enter the exact name of your municipality (e.g., `maastricht`).
4. **Instance Name**: Choose a friendly name for your device.
5. **Filters**: Select which types of announcements you want to track. *Leave "ALLES" checked if you want no filters.* (You can change these later by clicking "Configure" on the integration page!)
6. **Scan Interval**: Set how often to check for updates (3600 seconds / 1 hour recommended).

## 📊 Sensors & Attributes

### Master Sensor
`sensor.bekendmakingen_<municipality>`

| Attribute | Content |
| :--- | :--- |
| `date` | The official publication date (e.g., 2026-03-05). |
| `time` | The official publication time. |
| `link` | The direct URL to the full permit/announcement on the government website. |
| `summary` | A brief text description of the permit or decision. |
| `history` | A list of the 9 previous announcements, complete with their own dates, times, links, and summaries. |

## 🛠 Services

| Service | Description |
| :--- | :--- |
| `bekendmakingen.refresh` | Forces an immediate check of the RSS feed. |
| `bekendmakingen.clear_files` | Deletes the local `.json` cache file and the `.txt` debug logs for all configured municipalities. |


## 🎨 Recommended Dashboard (Markdown)

To get a beautifully formatted list of all your alerts with clickable links, use the standard **Markdown Card** built right into Home Assistant. 

*Note: Replace `maastricht` in the entity ID below with your actual municipality name.*

```yaml
type: markdown
content: |2-

    {% set entity = 'sensor.bekendmakingen_maastricht' %}
    
    ## 🏛️ Gemeente maastricht Bekendmakingen
    
    {% if states(entity) not in ['unknown', 'unavailable', 'Geen bekendmakingen'] %}
    **{{ state_attr(entity, 'date') }} ({{ state_attr(entity, 'time') }})** [**{{ states(entity) }}**]({{ state_attr(entity, 'link') }})  
    *{{ state_attr(entity, 'summary') | striptags | truncate(150, true, '...') }}*
    
    ---
    
    {% if state_attr(entity, 'history') %}
    {% for item in state_attr(entity, 'history') %}
    **{{ item.date }} ({{ item.time }})** [**{{ item.title }}**]({{ item.link }})  
    *{{ item.summary | striptags | truncate(150, true, '...') }}*
    
    ---
    {% endfor %}
    {% endif %}
    {% else %}
    Geen bekendmakingen gevonden in de huidige feed.
    {% endif %}
grid_options:
  rows: 8
  columns: 48

```
[hacs]: https://hacs.xyz
[hacs_badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge
[maintenance_badge]: https://img.shields.io/badge/Maintained%3F-yes-green.svg?style=for-the-badge
