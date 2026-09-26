# Installing Docker on Windows

On macOS or Linux, install Docker Desktop or Docker Engine from the [official documentation](https://docs.docker.com/get-started/get-docker/). On Windows, install Docker Desktop with the WSL 2 backend. See the [official Windows installation guide](https://docs.docker.com/desktop/setup/install/windows-install/) for current system requirements.

1. Open PowerShell **as Administrator** and install WSL without an additional Linux distribution:

   ```powershell
   wsl --install --no-distribution
   ```

   Restart Windows if prompted. Docker manages its own Linux environment; Ubuntu is not required for these commands.

2. Install Docker Desktop using WinGet, or use the installer linked in the official guide:

   ```powershell
   winget install --id Docker.DockerDesktop --exact --source winget
   ```

   Select the WSL 2 backend if prompted. Open Docker Desktop, complete its initial setup, and wait for the engine to start.

3. Open a new PowerShell window and verify both the client and engine:

   ```powershell
   wsl --version
   docker --version
   docker version
   docker compose version
   ```

   `docker version` should display both **Client** and **Server** sections. A client version alone does not confirm the engine is running.

If `docker` is not recognized, reopen the terminal after installation. For a per-user installation, check the executable directly:

```powershell
& "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin\docker.exe" version
```

If the error mentions a missing `dockerDesktopLinuxEngine` pipe, open Docker Desktop and wait for startup. If WSL is missing, complete step 1; if it needs an update, run `wsl --update` in Administrator PowerShell and restart Docker Desktop.

Then follow [Run the image locally](deployment.md#run-the-image-locally).
