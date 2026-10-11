# bluerskill

**Anti-slop 3D for Blender.** [taste-skill](https://github.com/growing7696-cmyk/taste-skill-v3)이 웹 페이지의 AI티를 없앤다면, bluerskill은 Claude Code가 만드는 **3D 모델링·렌더의 AI티**를 없앱니다.

| 흔한 AI식 bpy 출력 — audit **0/100** | bluerskill — audit **100/100** |
|---|---|
| ![before](assets/before.png) | ![after](assets/after.png) |

같은 요청("다이너 머그컵 정물")을 두 방식으로 만든 결과입니다. 재현: [`examples/mug_still_life.py`](skills/bluerskill/examples/mug_still_life.py)

### 모델링: 도형 쌓기가 아니라 실제로 만들기

AI 3D는 재질이나 조명 전에 **형태**에서 무너집니다. 큐브와 실린더를 대충 쌓기 때문입니다. bluerskill은 치수표를 먼저 쓰고, 실루엣을 그리고, 실제 제작 방식(톱으로 켜기, 선반 가공, 휜 막대, 기계 가공 블록)에 맞는 빌더로 부품을 만듭니다.

| 첫 시도 (개선 전 스킬) | 개선된 스킬 |
|---|---|
| ![rifle first try](assets/rifle-first-try.png) | ![rifle](assets/rifle.png) |

| 실루엣: 검은 단색으로도 알아볼 수 있는가 | 클레이: 재질 없이도 형태가 서는가 |
|---|---|
| ![silhouette](assets/rifle-silhouette.png) | ![clay](assets/rifle-clay.png) |

부품 35개로 된 볼트액션 소총 예제입니다. 재현: [`examples/rifle_prop.py`](skills/bluerskill/examples/rifle_prop.py)

## 설치

```bash
npx skills add growing7696-cmyk/bluerskill
```

전역 설치(모든 프로젝트에서 사용):

```bash
npx skills add growing7696-cmyk/bluerskill -g
```

필요한 것: [Node.js](https://nodejs.org), [Git](https://git-scm.com), [Claude Code](https://claude.com/claude-code), Blender 4.2 이상(5.x 권장)이 `PATH`에 있을 것.

> `Error: spawn git ENOENT`가 나오면 Git이 없는 것입니다. Windows는 `winget install --id Git.Git -e`로 설치한 뒤 터미널을 새로 열고 다시 실행하세요. [blender-mcp](https://github.com/ahujasid/blender-mcp)가 연결돼 있으면 열려 있는 Blender에서 실시간으로 작업합니다.

## 무엇을 하나

3D가 "AI가 만든 것처럼" 보이는 이유는 웹과 같습니다. 모든 게 기본값이고, 모든 게 완벽하고, 아무것도 역사가 없습니다. bluerskill은 기본값을 **결정**으로, 완벽함을 **그럴듯한 불완전함**으로 바꿉니다.

- **헤더와 다이얼**: 작업 전에 구체적 레퍼런스와 `WEAR / STYLIZATION / CLUTTER` 다이얼을 정합니다.
- **모델링 규칙**: 치수표 → 실루엣 → 제작 방식에 맞는 빌더 선택 → 큰/중간/작은 형태 순서. 기본 도형을 그대로 조립하는 것은 금지입니다.
- **필수 규칙 10개**: 베벨 없는 날카로운 모서리 금지, 실제 크기, 떠 있는 물체 금지, 기본 회색 재질 금지, 균일한 거칠기 금지, 시작 카메라·조명 금지, AgX 색 관리, 복제품 변화, 렌더를 직접 보고 확인, 기본 도형 조립 금지.
- **기본 금지 룩**: 어두운 배경의 네온 보라·청록 조명, 그라데이션 위에 떠 있는 크롬 공, 파스텔 클레이 아이소메트릭 방 등.

## 구성

```
skills/bluerskill/
├── SKILL.md                 # 규칙과 작업 순서
├── reference/
│   ├── modeling.md          # 모델링 플레이북: 치수표, 실루엣, 제작 방식별 빌더, 디테일 단계
│   ├── ai-tells.md          # 3D AI티 카탈로그 (형태·재질·조명·카메라·렌더) + 해결법
│   ├── materials.md         # 실제 재질의 albedo/roughness 표, 얼룩·마모 레시피
│   └── light-camera.md      # 조명 세팅, 색온도, 렌즈·조리개 기준
├── scripts/
│   ├── shapes.py            # 모델링 빌더 (profile_extrude+crown, lathe, sweep, rounded_box, cut, screw)
│   ├── humanize.py          # 마감 라이브러리 (bevel, ground, jitter, 재질 프리셋, 마모, 나뭇결, 조명, 카메라)
│   ├── audit.py             # 장면의 AI티를 0–100점으로 채점하고 해결법 출력 (기본 도형 조립 감지 포함)
│   └── preview.py           # silhouette / clay / beauty / wire 확인용 렌더 + 썸네일
└── examples/
    ├── mug_still_life.py    # 간단한 장면 before/after
    └── rifle_prop.py        # 하드서피스 소품 (부품 35개) 모델링 예제
```

스크립트는 단독으로도 쓸 수 있습니다.

```bash
blender -b scene.blend --python skills/bluerskill/scripts/audit.py
blender -b scene.blend --python skills/bluerskill/scripts/preview.py -- --out ./renders --views silhouette,clay,beauty
```

## 한계

- 떠 있는 물체·바닥 유무 검사는 바운딩 박스 기반 추정이라 오탐·누락이 있을 수 있습니다.
- 이야기, 형태 리듬, 레퍼런스 충실도는 자동으로 판단할 수 없습니다. 그래서 스킬은 렌더를 직접 열어 보고 고치는 단계를 필수로 둡니다.

## License

MIT
