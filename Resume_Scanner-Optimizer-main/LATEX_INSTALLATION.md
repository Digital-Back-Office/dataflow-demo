# LaTeX Installation Guide

## Why LaTeX is Needed

The Resume ATS Scanner & Optimizer uses LaTeX to generate professional, ATS-friendly PDF resumes. LaTeX provides superior formatting control and ensures consistent output across different systems.

## Quick Installation Options

### Option 1: Automatic Installation (Windows)

Run the included installation helper:
```bash
python install_latex.py
```

### Option 2: Manual Installation (Recommended)

#### For Windows - MiKTeX (Recommended)

1. **Download MiKTeX**
   - Visit: https://miktex.org/download
   - Download the "Basic MiKTeX" installer
   - Run the installer as Administrator

2. **Installation Steps**
   - Choose "Complete" installation (recommended)
   - Allow automatic package installation
   - Restart your computer after installation

3. **Verify Installation**
   - Open Command Prompt
   - Run: `pdflatex --version`
   - You should see version information

#### For macOS - MacTeX

1. **Download MacTeX**
   - Visit: https://www.tug.org/mactex/
   - Download the MacTeX.pkg file
   - Install the package

2. **Verify Installation**
   - Open Terminal
   - Run: `pdflatex --version`

#### For Linux - TeX Live

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install texlive-full
```

**Fedora/CentOS:**
```bash
sudo dnf install texlive-scheme-full
```

**Arch Linux:**
```bash
sudo pacman -S texlive-most
```

## Fallback Option (No LaTeX Required)

If you cannot install LaTeX, the application includes a fallback PDF generator using ReportLab. This provides basic PDF formatting without LaTeX's advanced features.

To ensure the fallback works:
```bash
pip install reportlab
```

## Troubleshooting

### "pdflatex not found" Error

1. **Restart your computer** after LaTeX installation
2. **Add LaTeX to PATH** (if not automatic):
   - Windows: Add `C:\Program Files\MiKTeX\miktex\bin\x64` to PATH
   - macOS/Linux: Usually added automatically

3. **Reinstall** with "Complete" installation option

### Permission Issues

- Run installer as Administrator
- On macOS: Allow installation in Security & Privacy settings

### Package Installation Errors

- Choose "Install missing packages on-the-fly" in MiKTeX settings
- Or run: `miktex packages install` (Windows)

## After Installation

1. **Restart** your computer
2. **Open new terminal/command prompt**
3. **Test**: `pdflatex --version`
4. **Run the application**: `python run.py`

## First Compilation

The first LaTeX compilation may take longer as MiKTeX downloads required packages. Subsequent compilations will be much faster.

## Verification

Test LaTeX installation with:
```bash
echo "\documentclass{article}\begin{document}Hello World\end{document}" > test.tex
pdflatex test.tex
```

If this creates `test.pdf`, LaTeX is working correctly.

## Need Help?

- Check the [MiKTeX documentation](https://miktex.org/documentation)
- Visit [TeX Stack Exchange](https://tex.stackexchange.com)
- Use the fallback PDF generator if LaTeX installation fails
