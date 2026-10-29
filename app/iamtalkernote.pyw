import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":   # 문서 읽기 작업 프로세스(multiprocessing)가 이 파일을 다시 불러도 앱 창이 또 뜨지 않게
    import multiprocessing
    multiprocessing.freeze_support()
    import notes
    notes.main()
