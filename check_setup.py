import subprocess
import sys
import importlib.util

def check_ffmpeg():
    """
    Check if FFmpeg is installed and accessible via command line.
    """
    try:
        # Redirect output to DEVNULL to keep the console clean
        subprocess.run(
            ["ffmpeg", "-version"], 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL,
            check=True
        )
        print("✅ FFmpeg is installed and recognized.")
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("❌ FFmpeg NOT found in PATH.")
        print("   -> Please install FFmpeg and add it to your system PATH.")
        return False

def check_library(package_name, import_name=None):
    """
    Check if a specific Python library is installed.
    """
    if import_name is None:
        import_name = package_name
        
    try:
        __import__(import_name)
        print(f"✅ Library '{package_name}' is installed.")
        return True
    except ImportError:
        print(f"⚠️  Library '{package_name}' is NOT installed.")
        return False

def main():
    print("--- 🩺 Checking System Environment ---\n")
    
    # 1. Check FFmpeg
    ffmpeg_ok = check_ffmpeg()
    
    # 2. Check Python Dependencies
    # List format: (Pip Package Name, Import Name)
    # Note: 'yt-dlp' imports as 'yt_dlp', 'faster-whisper' imports as 'faster_whisper'
    packages = [
        ("requests", "requests"),
        ("yt-dlp", "yt_dlp"),
        ("faster-whisper", "faster_whisper")
    ]
    
    all_packages_ok = True
    for pkg_name, import_name in packages:
        if not check_library(pkg_name, import_name):
            all_packages_ok = False

    print("\n" + "="*40)
    
    if ffmpeg_ok and all_packages_ok:
        print("🎉 GREAT! Your system is ready.")
        print("   You can now run: python run.py")
    else:
        print("❌ SETUP INCOMPLETE.")
        if not ffmpeg_ok:
            print("   - You need to install FFmpeg.")
        if not all_packages_ok:
            print("   - You need to install Python dependencies.")
            print("     Run: pip install requests yt-dlp faster-whisper")

if __name__ == "__main__":
    main()