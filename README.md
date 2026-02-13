
<a id="readme-top"></a>

[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![Unlicense License][license-shield]][license-url]



<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a href="https://github.com/leonifrazao/MSRewardsFarm">
    <img src="images/logo.png" alt="Logo" width="80" height="80">
  </a>

  <h3 align="center">RaxyMS</h3>

  <p align="center">
    A powerful CLI automation tool for Microsoft Rewards farming, built with Python and designed for scalability.
    <br />
    <a href="https://github.com/leonifrazao/MSRewardsFarm"><strong>Explore the docs »</strong></a>
    <br />
    <br />
    <a href="https://github.com/leonifrazao/MSRewardsFarm">View Demo</a>
    &middot;
    <a href="https://github.com/leonifrazao/MSRewardsFarm/issues/new?labels=bug&template=bug-report---.md">Report Bug</a>
    &middot;
    <a href="https://github.com/leonifrazao/MSRewardsFarm/issues/new?labels=enhancement&template=feature-request---.md">Request Feature</a>
  </p>
</div>



<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#key-features">Key Features</a></li>
        <li><a href="#built-with">Built With</a></li>
      </ul>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>



<!-- ABOUT THE PROJECT -->
## About The Project

**RaxyMS** is a specialized command-line interface (CLI) application designed to automate Microsoft Rewards activities. It provides a robust engine for managing multiple accounts, handling proxy connections, and executing farming tasks efficiently.

Unlike browser-extension based solutions, RaxyMS runs logically in the backend, supporting concurrent execution and advanced state management via local databases (SQLite) or cloud sync (Supabase).

<p align="right">(<a href="#readme-top">back to top</a>)</p>


### Key Features

*   **Robust CLI**: Fully featured terminal interface using `Typer` and `Rich` for beautiful output and ease of use.
*   **Batch Automation**: Process multiple accounts in parallel with configurable worker threads.
*   **Proxy System**: Integrated proxy management with support for Xray/V2Ray, including auto-testing and rotation.
*   **Dual Storage**: Store account data locally in SQLite or sync with Supabase for centralized management.
*   **Headless Operation**: Powered by `Botasaurus` for reliable browser automation.
*   **Terminal Dashboard**: Real-time status updates and metrics directly in your terminal.

<p align="right">(<a href="#readme-top">back to top</a>)</p>


### Built With

*   [![Python][Python.org]][Python-url]
*   [Typer](https://typer.tiangolo.com/)
*   [Rich](https://rich.readthedocs.io/en/stable/)
*   [Botasaurus](https://github.com/omkarcloud/botasaurus)
*   [Supabase](https://supabase.com/)
*   [SQLite](https://www.sqlite.org/index.html)

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- GETTING STARTED -->
## Getting Started

To get RaxyMS running locally, follow these steps.

### Prerequisites

*   **Python 3.10+**: Ensure you have a compatible Python version installed.
*   **Xray / V2Ray**: Required if you plan to use the proxy features. Ensure the executable is in your system PATH or configured correctly.
*   **Nix (Optional)**: For a reproducible development environment.

### Installation

#### Option 1: Using Nix (Recommended)

If you have [Nix](https://nixos.org/download.html) installed, you can set up the entire environment automatically:

```sh
# Enter the nix shell (installs Python, dependencies, and system libraries)
nix-shell
```

Inside the shell, you are ready to run the CLI.

#### Option 2: Manual Installation

1.  **Clone the repository**
    ```sh
    git clone https://github.com/leonifrazao/MSRewardsFarm.git
    cd MSRewardsFarm/raxy_project
    ```

2.  **Install dependencies**
    ```sh
    pip install .
    # OR
    pip install -r requirements.txt
    ```

3.  **Configuration**
    Copy the example configuration file:
    ```sh
    cp config.example.yaml config.yaml
    ```
    Edit `config.yaml` to adjust settings like `max_workers`, `users_file` path, or Supabase credentials.

4.  **Environment Variables (Optional)**
    If using Supabase, create a `.env` file:
    ```env
    SUPABASE_URL=your_project_url
    SUPABASE_KEY=your_anon_key
    ```

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- USAGE EXAMPLES -->
## Usage

RaxyMS is controlled entirely via the `cli.py` script. Here are the common commands:

### Basic Farming
Run the standard farming process for all configured accounts:
```sh
python cli.py run
```

### Specific Account
Run farming for a single account (useful for testing):
```sh
python cli.py run --email user@example.com --password yourpassword
```

### Account Management
Import accounts from a text file (format: `email:password` per line):
```sh
python cli.py accounts import users.txt
```

List all accounts in the database:
```sh
python cli.py accounts list
```

### Proxy Management
Test your proxy list:
```sh
python cli.py proxy test --threads 20 --country US
```

Start proxy bridges manually:
```sh
python cli.py proxy start
```

For a full list of commands and options, run:
```sh
python cli.py --help
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- ROADMAP -->
## Roadmap

- [x] Core CLI Architecture
- [x] Batch Processing Engine
- [x] Proxy Management & Rotation
- [x] SQLite & Supabase Adapters
- [x] Terminal Dashboard
- [ ] Advanced Scheduling (Cron/Daemon mode)
- [ ] Docker Containerization
- [ ] Multi-region/Language Support

See the [open issues](https://github.com/your_username/repo_name/issues) for a full list of proposed features (and known issues).

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- CONTRIBUTING -->
## Contributing

Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

1.  Fork the Project
2.  Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3.  Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4.  Push to the Branch (`git push origin feature/AmazingFeature`)
5.  Open a Pull Request

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- LICENSE -->
## License

Distributed under the Unlicense License. See `LICENSE.txt` for more information.

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- CONTACT -->
## Contact

Leoni Frazão - leoni.frazao.oliveira@gmail.com

Project Link: [https://github.com/leonifrazao/MSRewardsFarm](https://github.com/leonifrazao/MSRewardsFarm)

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- ACKNOWLEDGMENTS -->
## Acknowledgments

*   [Typer](https://typer.tiangolo.com/)
*   [Rich](https://rich.readthedocs.io/en/stable/)
*   [Botasaurus](https://github.com/omkarcloud/botasaurus)
*   [Best-README-Template](https://github.com/othneildrew/Best-README-Template)

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- MARKDOWN LINKS & IMAGES -->
[contributors-shield]: https://img.shields.io/github/contributors/othneildrew/Best-README-Template.svg?style=for-the-badge
[contributors-url]: https://github.com/othneildrew/Best-README-Template/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/othneildrew/Best-README-Template.svg?style=for-the-badge
[forks-url]: https://github.com/othneildrew/Best-README-Template/network/members
[stars-shield]: https://img.shields.io/github/stars/othneildrew/Best-README-Template.svg?style=for-the-badge
[stars-url]: https://github.com/othneildrew/Best-README-Template/stargazers
[issues-shield]: https://img.shields.io/github/issues/othneildrew/Best-README-Template.svg?style=for-the-badge
[issues-url]: https://github.com/othneildrew/Best-README-Template/issues
[license-shield]: https://img.shields.io/github/license/othneildrew/Best-README-Template.svg?style=for-the-badge
[license-url]: https://github.com/othneildrew/Best-README-Template/blob/master/LICENSE.txt
[product-screenshot]: images/screenshot.png
[Python.org]: https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white
[Python-url]: https://python.org