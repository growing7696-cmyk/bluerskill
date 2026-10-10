# bluerskill

**Anti-slop 3D for Blender.** [taste-skill](https://github.com/growing7696-cmyk/taste-skill-v3)이 웹 페이지의 AI티를 없앤다면, bluerskill은 Claude Code가 만드는 **3D 모델링·렌더의 AI티**를 없앱니다.

| 흔한 AI식 bpy 출력 — audit **0/100** | bluerskill — audit **100/100** |
|---|---|
| ![before](assets/before.png) | ![after](assets/after.png) |

같은 요청("다이너 머그컵 정물")을 두 방식으로 만든 결과입니다. 재현: [`examples/mug_still_life.py`](skills/bluerskill/examples/mug_still_life.py)

## 설치

```bash
npx skills add growing7696-cmyk/bluerskill
```

전역 설치(모든 프로젝트에서 사용):

```bash
npx skills add growing7696-cmyk/bluerskill -g
```

필요한 것: [Claude Code](https://claude.com/claude-code), Blender 4.2 이상(5.x 권장)이 `PATH`에 있을 것. [blender-mcp](https://github.com/ahujasid/blender-mcp)가 연결돼 있으면 열려 있는 Blender에서 실시간으로 작업합니다.

## 무엇을 하나

3D가 "AI가 만든 것처럼" 보이는 이유는 웹과 같습니다. 모든 게 기본값이고, 모든 게 완벽하고, 아무것도 역사가 없습니다. bluerskill은 기본값을 **결정**으로, 완벽함을 **그럴듯한 불완전함**으로 바꿉니다.

- **헤더와 다이얼**: 작업 전에 구체적 레퍼런스와 `WEAR / STYLIZATION / CLUTTER` 다이얼을 정합니다.
- **필수 규칙 9개**: 베벨 없는 날카로운 모서리 금지, 실제 크기, 떠 있는 물체 금지, 기본 회색 재질 금지, 균일한 거칠기 금지, 시작 카메라·조명 금지, AgX 색 관리, 복제품 변화, 렌더를 직접 보고 확인.
- **기본 금지 룩**: 어두운 배경의 네온 보라·청록 조명, 그라데이션 위에 떠 있는 크롬 공, 파스텔 클레이 아이소메트릭 방 등.

## 구성

```
skills/bluerskill/
├── SKILL.md                 # 규칙과 작업 순서
├── reference/
│   ├── ai-tells.md          # 3D AI티 카탈로그 (형태·재질·조명·카메라·렌더) + 해결법
│   ├── materials.md         # 실제 재질의 albedo/roughness 표, 얼룩·마모 레시피
│   └── light-camera.md      # 조명 세팅, 색온도, 렌즈·조리개 기준
├── scripts/
│   ├── humanize.py          # 교정 함수 라이브러리 (bevel, ground, jitter, 재질 프리셋, 마모, 나뭇결, 조명, 카메라)
│   ├── audit.py             # 장면의 AI티를 0–100점으로 채점하고 해결법 출력
│   └── preview.py           # clay / beauty / wire 확인용 렌더 + 썸네일
└── examples/
    └── mug_still_life.py    # before/after 예제
```

스크립트는 단독으로도 쓸 수 있습니다.

```bash
blender -b scene.blend --python skills/bluerskill/scripts/audit.py
blender -b scene.blend --python skills/bluerskill/scripts/preview.py -- --out ./renders
```

## 한계

- 떠 있는 물체·바닥 유무 검사는 바운딩 박스 기반 추정이라 오탐·누락이 있을 수 있습니다.
- 이야기, 형태 리듬, 레퍼런스 충실도는 자동으로 판단할 수 없습니다. 그래서 스킬은 렌더를 직접 열어 보고 고치는 단계를 필수로 둡니다.

## License

MIT
