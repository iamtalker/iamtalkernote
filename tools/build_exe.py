"""iamtalkernote 를 파이썬 없이 도는 exe 로 묶는다 (PyInstaller 필요: pip install pyinstaller).

    py -3 tools/build_exe.py     →  프로젝트 맨 위 폴더에 iamtalkernote.exe  (clipper/ 폴더는 exe 옆에 둔다)
"""
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "app")


def main():
    icon = os.path.join(APP, "assets", "icon.ico")
    work = tempfile.mkdtemp(prefix="iamtalkernote-build-")
    try:
        subprocess.check_call([
            sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile", "--windowed", "--name", "iamtalkernote",
            "--icon", icon, "--paths", APP, "--hidden-import", "PIL.Image", "--hidden-import", "PIL.WebPImagePlugin", "--add-data", os.path.join(APP, "assets") + os.pathsep + "assets",
            "--workpath", os.path.join(work, "build"), "--specpath", work, "--distpath", os.path.join(work, "dist"),
            os.path.join(APP, "iamtalkernote.pyw")])
        out = os.path.join(ROOT, "iamtalkernote.exe")
        built = os.path.join(work, "dist", "iamtalkernote.exe")
        try:
            shutil.copyfile(built, out)
        except PermissionError:   # 앱이 실행 중이라 덮어쓸 수 없으면 옆에 새 이름으로 둔다
            out = os.path.join(ROOT, "iamtalkernote.new.exe")
            shutil.copyfile(built, out)
            print("앱이 실행 중이라 덮어쓰지 못했습니다. 앱을 끄고 iamtalkernote.new.exe 의 이름을 iamtalkernote.exe 로 바꾸세요.")
        print("만들었습니다:", out)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
