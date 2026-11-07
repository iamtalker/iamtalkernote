# iamtalkernote

![iamtalkernote 기능 한눈에 보기](docs/images/feature-overview.png)

Windows와 Android에서 함께 쓰는 로컬 마크다운 노트 앱입니다. 노트는 일반 `.md` 파일로 저장되며, 컴퓨터와 폰은 Syncthing으로 직접 동기화합니다.

> **휴대폰 공유로 바로 스크랩**  
> 웹페이지·글·사진·파일을 다른 앱에서 **공유 → iamtalkernote**로 보내면 에버노트처럼 새 노트로 저장할 수 있습니다. 저장된 스크랩은 컴퓨터와 자동 동기화되어 검색·태그·정리가 가능합니다.

## 빠른 시작

### Windows

1. [최신 릴리스](https://github.com/iamtalker/iamtalkernote/releases/latest)에서 `iamtalkernote.exe`를 받습니다.
2. 처음 실행할 때 노트 폴더를 고릅니다. 기본 폴더는 `문서\\iamtalkernote`입니다.
3. `Ctrl+N`으로 노트를 만들고 입력을 멈추면 자동 저장됩니다.

소스로 실행하려면 다음을 사용합니다.

```powershell
py -3 app/iamtalkernote.pyw
```

### Android

[Android 릴리스](https://github.com/iamtalker/iamtalkernote-android/releases/latest)에서 APK를 설치한 뒤 동기화된 노트 폴더를 한 번 고릅니다.

자세한 사용법은 [사용 설명서](docs/manual.md)를 보세요.

## 핵심 기능

- 노트북(폴더), 하위 노트북, 태그, 즐겨찾기
- Markdown 편집·렌더링, 표, 체크 목록, 코드, 수식, 각주
- `[[노트 제목]]` 링크와 `![[노트 제목]]` 포함
- 제목·본문·태그·기간 검색, 검색 저장, 정렬
- 자동 저장, 휴지통, 노트 버전, 복원 지점, 전체 변경 이력
- 중복 노트·웹 스크랩 군더더기·사용하지 않는 미디어 정리
- 웹 클리퍼(로컬 서버, `127.0.0.1`). 스크랩할 때 본문 맨 위에 노트 제목과 같은 제목 줄이 있으면 빼고 저장합니다
- Android 공유 메뉴를 이용한 에버노트식 웹·파일 스크랩
- PDF·TXT·Office·오디오·동영상 외부 폴더 가져오기
- 확장자별 연결 프로그램 지정(문서·이미지는 뷰어, MP3·MP4는 미디어 플레이어 권장)
- Android와의 Syncthing 동기화

## 노트와 파일

노트는 노트 폴더 안의 `.md` 파일입니다. 그림과 첨부는 기본적으로 `.resources`에 저장합니다.

| 폴더 | 용도 |
|---|---|
| `.resources` | 그림·첨부 |
| `.trash` | 휴지통 |
| `.history` | 변경 이력·이전 버전 |
| `.snapshots` | 복원 지점 |
| `.imported` | 가져온 파일의 폰용 요약 |
| `.sync` | 동기화 정보 |

앱을 지워도 `.md` 파일은 남습니다. 노트 폴더를 복사하면 기본 백업이 됩니다.

## 외부 폴더 가져오기

**설정 → 옵션 → 가져오기**에서 노트 폴더 밖의 폴더를 추가합니다. 원본은 수정하지 않고 읽기·색인만 합니다.

기본 확장자는 `pdf`, `txt`, `md`, `mp3`, `mp4`입니다. 다른 확장자는 옵션에서 선택하거나 직접 입력합니다. 가져온 파일의 태그와 메모는 색인에만 저장됩니다.

PDF·TXT·JPG·WEBP 같은 문서·이미지는 WaterView/NeeView 같은 뷰어를 연결하고, MP3·MP4는 Windows Media Player·VLC 같은 미디어 플레이어를 연결하는 구성이 안정적입니다. MP3·MP4를 열 때 같은 폴더의 미디어 파일을 함께 전달하므로, 여러 파일 열기나 재생목록을 지원하는 플레이어에서는 폴더 재생처럼 사용할 수 있습니다.

## 동기화

컴퓨터와 폰은 Syncthing으로 직접 연결합니다. 노트가 서버에 업로드되는 구조가 아니며, 컴퓨터 앱은 트레이에 있어도 동기화를 계속합니다.

1. 컴퓨터 **설정 → 동기화**에서 Syncthing을 설치하고 켭니다.
2. 폰 앱의 연결 마법사에서 컴퓨터를 등록합니다.
3. 컴퓨터에서 연결 요청을 허용합니다.
4. 폰에서 받을 노트 폴더를 확인합니다.

자세한 절차는 [사용 설명서](docs/manual.md)의 동기화 장을 참고하세요.

## 단축키

| 키 | 동작 |
|---|---|
| `Ctrl+N` | 새 노트 |
| `Ctrl+Shift+N` | 새 노트북 |
| `Ctrl+F` | 현재 노트에서 찾기 |
| `Ctrl+Shift+F` | 전체 검색 |
| `Ctrl+E` | 편집기 보기 전환 |
| `Ctrl+,` | 옵션 |
| `F1` | 사용 설명서 |
| `Delete` | 휴지통으로 이동 |

## 알려진 한계

- Windows 전용 기능(GDI+, Edge 재생 창, 트레이)이 있습니다.
- 스캔 PDF OCR과 오디오 음성 인식은 지원하지 않습니다.
- 가져온 원본 파일은 앱에서 편집·이동·삭제하지 않습니다.
- 유튜브는 노트 안에 직접 재생하지 않고 외부 창으로 엽니다.

## 다음 확인

1. 연결한 미디어 플레이어의 MP3·MP4 재생목록 확인
2. Android 실기기 동기화·배터리·대용량 폴더
3. 웹 클리퍼와 Android 공유
4. Play Store 배포용 빌드

## 개발

```powershell
py -3 -m pip install pyinstaller pillow pypdf tinytag
py -3 tools/build_exe.py
```

```text
app/       Windows 앱
tools/     빌드·시험 도구
docs/      사용 설명서와 설계 문서
clipper/   웹 클리퍼 확장
```

## 라이선스

프로젝트 라이선스와 제3자 고지는 `LICENSE` 및 `app/assets/THIRD_PARTY_NOTICES.md`를 확인하세요.
