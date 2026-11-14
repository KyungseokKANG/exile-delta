# Exile Delta

**Path of Exile 1** 아이템을 게임에서 `Ctrl+C` 하면, 지금 내 캐릭터에 끼웠을 때 **DPS · EHP · 최대 피격**이 얼마나 바뀌는지 바로 보여 주는 Windows 데스크톱 도구입니다.
계산은 [Path of Building Community](https://github.com/PathOfBuildingCommunity/PathOfBuilding)(PoB)의 원본 계산 코드를 그대로 돌려서 하기 때문에 **PoB 와 같은 숫자**가 나옵니다.
한국어 게임 클라이언트에서 복사한 아이템 텍스트도 그대로 쓸 수 있습니다.

> A Windows desktop tool for Path of Exile 1: press `Ctrl+C` on an item in game and see how DPS / EHP / max hit would change on your character, calculated with the original Path of Building engine. Korean game client text is supported.

---

## 주요 기능

### 아이템 비교 (게임에서 Ctrl+C)
- 게임에서 아이템 위에 마우스를 올리고 `Ctrl+C` → 게임 위에 비교 창이 뜹니다 (포커스를 빼앗지 않아 계속 다른 아이템을 `Ctrl+C` 할 수 있음)
- 끼울 수 있는 자리(반지 1/2, 주얼 칸 등)마다 **Full DPS · EHP · 최대 피격(물리/화염/냉기/번개/카오스)** 변화
- 저항 상한 미달 · 능력치 요구치 부족 경고, 순 생명력 재생(정의의 화염 같은 지속 피해를 뺀 값)
- **ⓘ 왜 이렇게 바뀌나?** — 마우스를 올리면 요약, 누르면 옵션 줄마다 DPS/EHP 기여도
- 옵션을 켜고 끄거나 수치를 고치고, 새 옵션(일반 · 총주교/포식자 · 타락 implicit)을 붙여 보며 바로 다시 계산
- 한국어 클라이언트 텍스트 → 영문 자동 변환 후 계산

### 캐릭터
- pathofexile.com 공개 프로필(계정 이름) 또는 PoB 코드/링크로 캐릭터 가져오기
- **1분마다 자동 갱신** (레벨업 · 장비 교체 · 패시브 반영, 사이트 요청 한도를 넘지 않게 조절)
- 스킬 젬/그룹 켜기·끄기, Full DPS 포함, 주 스킬, 계산 설정(Configuration), 플라스크 — 다시 가져와도 유지
- 장착 장비 · 주얼별 기여도, 젬 레벨/퀄리티별 효과, 패시브 트리 보기 · 찍어 보기
- 아이템 만들기(유니크 · 베이스 + 옵션), 슬롯별 DPS 최적 옵션 추천(Beta)

## 설치 · 실행

1. [Releases](../../releases/latest) 에서 `ExileDelta-<버전>.zip` 을 받아 원하는 폴더에 풉니다.
2. `ExileDelta.exe` 실행
   - 서명되지 않은 프로그램이라 처음에 Windows SmartScreen 경고가 뜰 수 있습니다 → **추가 정보 → 실행**
3. 처음 실행하면 알아서:
   1. 이 저장소의 최신 릴리스를 확인해 더 새 버전이 있으면 받아서 다시 시작하고
   2. **PoB 엔진**(계산용 파일 약 370MB)을 PoB 공식 GitHub 에서 받아 설치합니다.
4. 캐릭터 화면에서 `+` 로 캐릭터를 등록합니다. (pathofexile.com 프로필 → Privacy Settings 에서 **Characters 탭 공개** 필요)
5. 게임은 **창 모드 전체 화면(Windowed Fullscreen)** 이어야 비교 창이 게임 위에 보입니다.

### 업데이트
- 실행할 때마다 새 버전이 있는지 확인하고, 있으면 **업데이트할지 물어봅니다** (지금 업데이트 / 나중에 / 이 버전 건너뛰기).
  업데이트는 앱 코드(1~2MB)만 받아서 몇 초면 끝나고, exe 는 다시 받을 필요가 없습니다.
- 메뉴(☰) → **프로그램 업데이트 확인** 으로 직접 확인할 수도 있습니다.
- 새 버전이 시작에 실패하면 자동으로 이전 버전으로 돌아갑니다.
- 받은 코드는 `%LOCALAPPDATA%\ExileDelta\app\<버전>\` 에 있습니다.

## 저장 위치 · 네트워크

- 설정 · 등록한 캐릭터: `%APPDATA%\ExileDelta\`
- PoB 엔진 · 로그 · 캐시: `%LOCALAPPDATA%\ExileDelta\`
- 접속하는 곳: pathofexile.com(캐릭터 정보), github.com(PoB 엔진 · 프로그램 업데이트), repoe-fork.github.io(번역 데이터).
  그 밖의 곳으로 개인 정보를 보내지 않습니다.

## 직접 빌드하기 (개발자용)

```powershell
python -m pip install -r requirements.txt
python app\main.py                                         # 개발 모드로 실행
powershell -ExecutionPolicy Bypass -File .\build.ps1 -NoRun # dist\ExileDelta.exe 빌드
```

- Python 3.12, Windows 10/11
- `data/*.json`(옵션 · 번역 사전)은 `tools/build_data.py`, `tools/build_names.py` 로 다시 만들 수 있습니다 (`build.ps1 -RefreshData`).
- 구조: `app/` GUI(PySide6) · `app/pob/` PoB 엔진 연동(lupa/LuaJIT 로 PoB Lua 코드를 화면 없이 실행, 별도 워커 프로세스)
- exe 는 `launcher/launcher.py`(로더 + 실행 환경)이고, 앱 코드(`app/`, `data/`)는 exe 안 기본본 또는 릴리스에서 받은
  `app-<버전>.zip` 을 파일로 읽어 실행합니다 (`tools/pack_app.py`, 업데이트 로직은 `app/app_update.py`).
- 릴리스: `app/version.py` 의 VERSION 을 올리고 `release.ps1 -NotesFile 변경내용.md` (`-Pre` 는 시험판: 자동 업데이트 대상 아님)

## 사용한 것 · 감사

- [Path of Building Community](https://github.com/PathOfBuildingCommunity/PathOfBuilding) (MIT) — 모든 DPS/EHP 계산. 프로그램에 포함하지 않고 실행할 때 공식 릴리스를 내려받아 사용합니다.
- [RePoE fork](https://repoe-fork.github.io/) — 아이템 옵션 · 영문/한글 문장 데이터
- [Awakened PoE Trade](https://github.com/SnosMe/awakened-poe-trade) (MIT) — 한국어 클라이언트 문장 · 이름 데이터 보충
- [PySide6](https://doc.qt.io/qtforpython/), [lupa](https://github.com/scoder/lupa), [requests](https://github.com/psf/requests)

## 라이선스

[MIT](LICENSE) — 자유롭게 사용 · 수정 · 배포할 수 있습니다.

## 고지

**이 프로그램은 Grinding Gear Games 와 아무 관련이 없으며, Grinding Gear Games 가 승인하거나 보증한 것이 아닌 팬 제작 도구입니다.**
Path of Exile 및 관련 이름 · 데이터의 권리는 Grinding Gear Games 에 있습니다.

*This product isn't affiliated with or endorsed by Grinding Gear Games in any way.*
