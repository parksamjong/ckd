# Claude Code 글로벌 가이드라인 & 스킬 레지스트리

---

## 1. Karpathy 코딩 원칙 (andrej-karpathy-skills)

> 출처: https://github.com/multica-ai/andrej-karpathy-skills

### 코딩 전에 생각하기
- 가정을 명시적으로 표현하고, 불확실하면 질문
- 여러 해석이 있으면 모두 제시하고 조용히 선택하지 않기
- 더 간단한 방법이 있으면 먼저 언급
- 혼란스러운 부분이 있으면 멈추고 이름 붙이기

### 단순성 우선
- 최소 코드로 문제 해결. 추측성 기능 없음
- 요청 범위 밖의 기능 추가 금지
- 단일 용도 코드에 추상화 금지
- 불가능한 시나리오에 대한 오류 처리 금지

### 수술적 변경
기존 코드 편집 시 필요한 부분만 수정하고, 현존 스타일 유지. 자신의 변경으로 인해 불필요해진 항목만 제거.

### 목표 중심 실행
작업을 검증 가능한 목표로 변환하고, 각 단계마다 확인. 다단계 작업은 간단한 계획 수립.

### 한국어 마침표 규칙
한국어로 출력할 때 문장 끝에 콜론(`:`)을 쓰지 말 것. 마침표(`.`), 물음표(`?`), 느낌표(`!`)만 사용.

### 한국어 파일 헤더
새 소스 파일 첫 줄에 역할을 설명하는 한국어 주석 추가. 예: `// 사용자 인증 상태를 관리하는 Context Provider`

### 계획 + 체크리스트 + 컨텍스트 노트
비자명한 작업 전에 세 가지 산출물(plan, checklist, context-notes) 준비 후 시작.

### 완료 전 테스트 실행
코드 변경 후 반드시 테스트 실행 후 결과 보고. 테스트 없으면 최소한 빌드 확인.

### 의미론적 커밋
한 문장으로 설명 가능한 논리적 변경 단위로 커밋. 여러 개념을 섞지 말 것.

### 에러 직접 읽기
에러 메시지와 스택 트레이스를 정확히 읽고, 추측 기반 수정 대신 실제 원인 파악 후 대응.

---

## 2. Superpowers 스킬 세트 (obra/superpowers)

> 출처: https://github.com/obra/superpowers

### 테스팅
- `/test-driven-development` — 테스트 먼저 작성 후 구현

### 디버깅
- `/systematic-debugging` — 가설 수립 → 검증 → 범위 축소 순서로 디버깅
- `/verification-before-completion` — 완료 전 반드시 실제 동작 검증

### 계획 & 실행
- `/brainstorming` — 열린 탐색으로 솔루션 탐구
- `/writing-plans` — 구조화된 실행 계획 수립
- `/executing-plans` — 계획 단계별 실행 및 진행 추적

### 협업
- `/dispatching-parallel-agents` — 독립 태스크를 병렬 에이전트로 분배
- `/requesting-code-review` — 코드 리뷰 요청 형식화
- `/receiving-code-review` — 리뷰 피드백 체계적 처리
- `/using-git-worktrees` — 격리된 worktree로 병렬 작업
- `/finishing-a-development-branch` — 브랜치 정리 및 PR 준비
- `/subagent-driven-development` — 서브에이전트 기반 개발 분업

### 메타
- `/writing-skills` — 새 스킬 정의 작성
- `/using-superpowers` — superpowers 활용 가이드

---

## 3. Understand-Anything 코드 이해 스킬 (Egonex-AI)

> 출처: https://github.com/Egonex-AI/Understand-Anything

- `/understand` — 코드베이스 전체 분석 → 인터랙티브 대시보드 생성
- `/understand-chat` — 코드베이스에 대한 자연어 Q&A
- `/understand-diff` — 변경 사항(diff) 상세 분석
- `/understand-explain` — 특정 함수/모듈 심층 설명

**기술 스택:** TypeScript + React Flow + tree-sitter (WASM) + Zustand

---

## 4. claude-video 영상 분석 스킬 (bradautomates)

> 출처: https://github.com/bradautomates/claude-video

- `/watch <URL|파일>` — 영상 분석 (YouTube URL 또는 로컬 파일)

**동작 방식:**
1. `yt-dlp`로 캡션 먼저 추출 (없으면 Whisper API로 자막 생성)
2. `ffmpeg`로 키프레임 추출 (scene-aware)
3. 중복 프레임 제거 후 Claude에 전달

**세부도 모드:**
- `--detail efficient` — 빠른 요약
- `--detail balanced` — 균형 (기본값)
- `--detail token-burner` — 전체 프레임 커버

---

## 5. agentmemory 지속 메모리 스킬 (rohitg00)

> 출처: https://github.com/rohitg00/agentmemory

**설치:** `npx skills add rohitg00/agentmemory -y`

**핵심 기능:**
- 4단계 메모리 계층: 작업(Working) / 에피소드(Episodic) / 의미(Semantic) / 절차(Procedural)
- 검색: BM25 + 벡터 + 지식 그래프 하이브리드 (R@5 95.2%)
- 53개 MCP 도구 (메모리 저장, 검색, 세션 관리)
- 실시간 메모리 뷰어: `http://localhost:3113`
- 12개 자동 캡처 훅으로 도구 사용 자동 기록
- 다중 에이전트 간 메모리 공유 (MCP + REST)
- 연간 비용 ~$10 (170K 토큰)

---

## 6. Remotion 비디오 생성 스킬 (wshuyi)

> 출처: https://github.com/wshuyi/remotion-video-skill

- `/remotion <설명>` — Remotion 프레임워크로 프로그래매틱 비디오 생성
- React + TypeScript 기반 영상 컴포넌트 자동 생성
- 애니메이션, 자막, 장면 전환 포함 단편 영상 제작

---

## 7. Skill Creator 에이전트 스킬 제작 (FrancyJGLisboa)

> 출처: https://github.com/FrancyJGLisboa/agent-skill-creator

- 기존 워크플로우를 재사용 가능한 AI 에이전트 스킬로 변환
- 17개 플랫폼 (Claude Code, Cursor, Codex 등) 동시 배포 지원
- 스킬 템플릿 자동 생성, 테스트, 최적화

---

## 8. Korean Skills — 한국어 AI 글쓰기 교정 (DaleSeo)

> 출처: https://github.com/DaleSeo/korean-skills

**설치:**
```
npx skills add daleseo/korean-skills
# 또는 특정 스킬만:
npx skills add daleseo/korean-skills@humanizer
```

### `/humanizer` — AI 한국어 패턴 감지 및 교정

KatFishNet 논문(ArXiv 2503.00032v4) 기반, 실증적 언어학 분석 (쉼표 패턴 94.88% AUC).

**분석하는 40가지 패턴 (S1/S2/S3 심각도):**
- **S1 (고위험):** 쉼표 과다 사용, 번역투 (`에 대해`, `통해`, `되어진다`), AI 어휘 과용
- **S2 (중위험):** 띄어쓰기 경직성, 품사 다양성 부족, 대명사 과다
- **S3 (저위험):** 복수형 과다, 구조적 단조로움

**사용 시점:** ChatGPT/Claude/Gemini 생성 한국어 텍스트를 자연스럽게 만들 때.

### `/grammar-checker` — 한국어 문법·맞춤법·띄어쓰기·구두점 검사

### `/style-guide` — 한국어 문서 스타일 일관성 점검

---

## 9. oh-my-claudecode 다중 에이전트 오케스트레이션 (Yeachan-Heo)

> 출처: https://github.com/Yeachan-Heo/oh-my-claudecode

**설치:** `setup omc` 또는 `/oh-my-claudecode:omc-setup`

### 핵심 원칙
- 특화된 작업을 적절한 에이전트에 위임
- "증거 우선": 결론 전에 결과 검증 후 진행
- 품질 유지하며 최소 경로 선택
- 공식 문서 우선 참조

### 주요 슬래시 커맨드

| 커맨드 | 설명 |
|---|---|
| `/team` | 팀 오케스트레이션 (team-plan → team-prd → team-exec → team-verify → team-fix) |
| `/autopilot` | 자율 실행 모드 |
| `/ralph` | 검증/수정 루프가 있는 지속 모드 |
| `/deep-interview` | 소크라테스식 요구사항 명확화 |
| `/ask` | 멀티 프로바이더 어드바이저 |

### 20개+ 전문 에이전트 카탈로그
`explore` · `analyst` · `planner` · `architect` · `debugger` · `executor` · `verifier` · `code-reviewer` · `test-engineer` · `security-reviewer` 등

### 모델 라우팅 전략
- **Haiku**: 빠른 조회, 단순 작업
- **Sonnet**: 표준 개발 작업
- **Opus**: 복잡한 분석, 아키텍처 설계

### 실행 프로토콜
- 광범위 요청 → 먼저 탐색 후 계획 수립
- "저자 작성"과 "검토"를 반드시 별도 단계로 분리
- 완료 조건: 미완료 작업 0개 + 테스트 통과 + 검증 증거 수집
- 커스텀 스킬: `.omc/skills/` 또는 `~/.omc/skills/`에서 관리

---

## 10. Fable 5 제품광고영상 자동완성 워크플로우

> 출처: https://challenzonedu.notion.site/Fable-5-3979d76136ea80c8b1ebf30df8504352
> 스킬 다운로드: Google Drive (Fable5로 만든 제품광고스튜디오 클로드 스킬)

**모델:** Claude Fable 5 (`claude-fable-5`)

### 실습1. 광고 스튜디오 개발
```
[Prompt]
제품명, 소구점, 광고 포맷, 무드를 입력하면 자동으로 광고 제작안을 생성하는
React Artifact를 만들어줘.

기능 구성:
- 씬별 스토리보드 생성 (스토리가 연결되도록)
- 광고 포맷별 최적화 (15초/30초/1분)
- 무드보드 시각화
```

**핵심 활용 패턴:**
- 제품명 + 소구점 + 포맷 + 무드 → React Artifact 자동 생성
- Fable 5의 멀티모달 + 장문 컨텍스트 활용
- 광고 스크립트 → 씬별 스토리보드 자동 분기

### `/ad-studio` 스킬 (설치 완료)

> 설치 경로: `~/.claude/skills/ad-studio/`
> 스킬 파일: Google Drive (Fable5로 만든 제품광고스튜디오 클로드 스킬)

**트리거**: "광고 제작안 만들어줘", "AD STUDIO 열어줘", "씬별 광고 프롬프트", "멀티샷 광고 프롬프트", 제품명 + 광고/스토리보드/씬/이미지 프롬프트/영상 프롬프트/부유샷/숏폼/TV CF 조합

**지원 포맷**:
- `float` — 프리미엄 부유샷 (럭셔리 매크로)
- `shortform` — 숏폼 광고 (릴스/틱톡)
- `tvcf` — TV CF (시네마틱)

**핵심 기능**: 씬별 스토리보드 + 자막 카피 + 이미지/영상 프롬프트(한글·영문) + 멀티샷 프롬프트 + 제품 이미지 분석 → 노텍스트 규칙 자동 적용

---

## 11. Agent Reach — AI 에이전트 인터넷 접근 능력 레이어 (Panniantong)

> 출처: https://github.com/Panniantong/Agent-Reach
> ⭐ 53k stars

AI 에이전트에게 인터넷 읽기/검색 능력을 한 번에 부여하는 **능력 레이어(capability layer)**.
Twitter, Reddit, YouTube, GitHub, Bilibili, 小红书, RSS, 일반 웹페이지를 API 비용 없이 접근 가능.

### 설치

에이전트에게 한 문장 전달:
```
帮我安装 Agent Reach：https://raw.githubusercontent.com/Panniantong/agent-reach/main/docs/install.md
```

안전 모드 (시스템 패키지 자동 설치 없이 안내만):
```
帮我安装 Agent Reach（安全模式）：... --safe
```

업데이트:
```
帮我更新 Agent Reach：https://raw.githubusercontent.com/Panniantong/agent-reach/main/docs/update.md
```

### 주요 능력

| 명령 예시 | 내부 도구 |
|---|---|
| "이 링크 내용 봐줘" | `curl https://r.jina.ai/URL` |
| "이 GitHub 레포 설명해줘" | `gh repo view owner/repo` |
| "이 YouTube 영상 요약해줘" | `yt-dlp` 자막 추출 |
| "Bilibili에서 AI 튜토리얼 찾아줘" | `bili search` (로그인 불필요) |
| "LLM 프레임워크 비교 검색해줘" | Exa 시맨틱 검색 |
| "이 RSS 구독해줘" | `feedparser` |

### 설계 철학
- 도구가 아닌 **능력 레이어** — 선정·설치·진단·라우팅만 담당, 실제 읽기는 상위 도구가 직접 호출
- SKILL.md를 읽은 에이전트가 상황에 맞는 도구를 자율 선택
- 로그인 필요 플랫폼(小红书, Twitter, Reddit 등)은 `帮我配 XXX`로 개별 설정

---

## 12. Agent Reachout — Claude Code → Telegram 알림 및 Human-in-the-Loop (vibe-with-me-tools)

> 출처: https://github.com/vibe-with-me-tools/agent-reachout

Claude Code 작업이 끝나거나 결정이 필요할 때 **Telegram으로 직접 알림**을 보내는 Claude Code 플러그인.
에이전트가 사용자에게 찾아오는 인터럽트 드리븐 워크플로우 구현.

### 흐름

```
Claude Code → Agent Reachout → Telegram → 사용자 답장 → 에이전트 재개
```

### 주요 기능

- 작업 완료 / 블로커 도달 / 결정 필요 시 Telegram 알림 발송
- 단방향 알림 + 양방향 대화 모두 지원
- 에이전트 **pause → 질문 → resume** 패턴
- Telegram에서 `/task` 명령으로 Claude Code 태스크 원격 시작

### 설치

**사전 조건:** Claude Code CLI, Bun, Telegram 계정

1. [@BotFather](https://t.me/botfather)에서 봇 토큰 발급
2. [@userinfobot](https://t.me/userinfobot)에서 본인 Chat ID 확인
3. 환경변수 설정 (`~/.claude/settings.json` 또는 쉘 프로파일):
   ```json
   { "env": { "AGENT_REACHOUT_TELEGRAM_BOT_TOKEN": "...", "AGENT_REACHOUT_TELEGRAM_CHAT_ID": "..." } }
   ```
4. Claude Code에서 플러그인 설치:
   ```
   /plugin marketplace add vibe-with-me-tools/agent-reachout
   /plugin install agent-reachout@agent-reachout
   ```

### Telegram 명령어

| 명령 | 설명 |
|---|---|
| `/task <설명>` | 새 작업 시작 (큐잉) |
| `/continue <설명>` | 최근 세션 이어서 |
| `/resume <id> <설명>` | 특정 세션 재개 |
| `/history` | 최근 작업 목록 |
| `/status` | 현재 작업 + 큐 상태 |
| `/cancel` | 현재 작업 취소 및 큐 비우기 |

### 환경변수 주요 설정

- `AGENT_REACHOUT_NOTIFY_DEFAULT_TIMEOUT_MS` — 응답 대기 시간 (기본: 300000ms / 5분)
- `AGENT_REACHOUT_ALLOWED_TOOLS` — 허용 도구 목록 (`--allowedTools` 전달)

---

## 13. BrowserAct — AI 웹 스크래핑 & 브라우저 자동화 플랫폼 (browser-act)

> 출처: https://github.com/browser-act/browseract-api-examples
> 공식 사이트: https://www.browseract.com/

**"Any Site, No Code, Zero Limits, Reliable Data"** — AI 기반 웹 스크래핑·자동화 클라우드 플랫폼.
Agent-Reach에서 "로그인 후 웹 조작, 폼 제출 등 '직접 손대는(手动)' 장면"에 추천하는 도구.

### 핵심 기능

- **AI-Workflow**: 사전 정의 템플릿 + 커스텀 워크플로우 + 배치 처리
- **Predefined Templates**: 공식 제공 워크플로우로 코드 없이 즉시 실행
- **REST API**: Python / Java / Node.js 모두 지원
- 30+ 플랫폼 스크래핑 스킬, Claude Code / Cursor 등 AI 에이전트 연동 가능

### 주요 API 엔드포인트

| 엔드포인트 | 설명 |
|---|---|
| `POST /v2/workflow/run-task` | 커스텀 워크플로우 태스크 시작 |
| `POST /v2/workflow/run-task-by-template` | 공식 템플릿으로 태스크 시작 |
| `GET /v2/workflow/get-task-status` | 태스크 상태 조회 |
| `PUT /v2/workflow/resume-task` | 일시정지된 태스크 재개 |
| `GET /v2/workflow/list-official-workflow-templates` | 공식 템플릿 목록 |

### 빠른 시작 (Python)

```bash
pip install requests
```
```python
import os, requests
headers = {"Authorization": os.getenv("BROWSERACT_API_KEY")}
# 템플릿으로 실행
requests.post("https://api.browseract.com/v2/workflow/run-task-by-template", headers=headers, json={"templateId": "...", "input": {...}})
```

### 설정

1. [BrowserAct Integrations](https://www.browseract.com/reception/integrations)에서 API 키 발급
2. 환경변수: `BROWSERACT_API_KEY=app-xxxxx`
3. [Workflow List](https://www.browseract.com/reception/workflow-list)에서 Workflow ID 확인

> **Agent-Reach와 함께 사용**: 읽기/검색은 Agent-Reach, 로그인 후 웹 조작·폼 제출 등 고마찰 구간은 BrowserAct로 역할 분담.

---

## AI의 3가지 고질병 — 항상 경계

1. **잘못된 가정** — 코드를 읽기 전에 작동 방식을 가정하지 말 것
2. **코드 부풀리기** — 요청받지 않은 기능, 추상화, 오류 처리 추가 금지
3. **멋대로 고치기** — 요청 범위 밖의 코드 수정 금지
