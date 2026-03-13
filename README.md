# ![Icon](assets/rgb_wheel.ico) 4 Zone RGB Toolkit

![Preview](assets/preview.png)

A modern, highly optimized hardware and software RGB visualization tool specifically designed and tested for Lenovo LOQ and Legion laptops with 4-Zone RGB keyboards. This toolkit provides a sleek, Fluent Design-inspired graphical interface that lets you customize keyboard lighting dynamically.

## What's New in v2.2

- Added an embedded Live Preview panel below Zone Colors with a local On/Off toggle and smooth collapse animation.
- Live Preview now remembers its last user-selected state between sessions.
- Live Preview automatically turns off in hardware modes and Live Audio Visualizer mode, then restores when you return to other software effects.
- Refined the left-side layout so Main Controls, Zone Colors, and preview space stay cleaner and more stable.
- Reset This Mode now restores the selected effect immediately without an extra popup.
- Removed the in-app hardware compatibility warning banner for a cleaner main window.

## Features

- **Hardware Modes:** Direct control over the keyboard's built-in firmware effects, including Off, Static, Breath, Smooth, and Wave with selectable direction.
- **Advanced Software Engine:** Custom software-driven effects rendered in real time, including:
  - **Smooth Wave:** A sweeping gradient with optional Fill Mode and palette choices: **RGBW**, **Pastel**, and **Custom 4-Color**.
  - **Lightning:** Staged storm strikes with flicker, afterglow, and adjustable Storm Intensity.
  - **Party:** Tempo-driven color bursts with pulsing brightness.
  - **Realistic Fire, Scanner (Cylon), Aurora Borealis, Meteor Shower, Ambient Screen Color, Battery Visualizer, Mouse-Reactive Aura, and Pomodoro Timer.**
  - **Live Audio Visualizer:** A 4-band WASAPI-driven visualizer that uses your selected zone colors with Sensitivity, Smoothness, and Flicker Reduction controls.
- **Presets and Mode Memory:**
  - Import and export custom presets with JSON files.
  - Remember per-mode settings such as Wave direction, Smooth Wave direction, Fill Mode state, Smooth Wave palette selection, and Scanner Rainbow Sweep.
  - Restore the last selected mode and preview preference on launch.
- **Workflow Polish:**
  - Embedded effect descriptions under the mode list.
  - Responsive preset toolbar behavior in tighter window widths.
  - Adaptive control label widths so rows stay aligned across modes.
  - Zone Colors stay anchored more cleanly while controls change between effects.
- **Performance and Safety:**
  - Automatic FPS throttling when the window loses focus.
  - Cleaner effect state resets when switching modes.
  - Stronger Live Audio visualizer shutdown fallback handling.
  - Keyboard LEDs turn off on shutdown.

## Hardware Compatibility

**Officially Tested & Supported:**
- Lenovo Legion Series (2020-2024 models)
- Lenovo LOQ Series
- Must have a 4-Zone RGB keyboard.

> Note: Using this software on unsupported hardware, such as per-key RGB keyboards or non-Lenovo devices, may result in unexpected behavior, failure to locate the controller, or crashes.

## Installation

1. Go to the Releases tab and download the latest version.



