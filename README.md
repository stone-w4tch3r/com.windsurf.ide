# Windsurf Flatpak

🚨 Warning: This is an unofficial Flatpak build of Windsurf, automatically generated from the official .tar.gz packages from windsurf.com. Based on com.vscodium.codium flatpak packages.

🚨🚨 Warning: flatpak version of Windsurf is not straightforward to use. Stick to native packages if you are not confident in linux and/or value simplicity.

## Usage

Basic text editor/extensions functionality works, but for any real development you need to setup flatpak SDK extensions or tweak isolation.

This will not work from VScode out of the box:
- using docker-related functions
- building apps and managing dependencies, eg `npm install` or `dotnet build`
- connecting or ssh-ing into local VMs and containers
- many more

For this you need to configure integration with host. Ask your AI or see [VScodium repo and docs](https://github.com/flathub/com.vscodium.codium/).

## Support

This package is mostly based on VScodium. Look at their repo and issues first if you will have any problems. Before leaving feedback here, ensure your situation does not reproduce in VScodium flatpak.
